from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from backend.models.config import AppConfig
from backend.models.task import ConvertTemplateTaskPayload, GenerateTaskPayload, Task
from backend.services.exceptions import NotFoundError, ServiceError, ValidationError
from backend.services.files.service import FileService
from backend.services.generation.service import GenerationService
from backend.services.generation.output_names import (
    output_name_for_task,
    template_output_name_for_task,
)
from backend.services.tasks.broadcaster import TaskBroadcaster
from backend.services.tasks.mappers import task_to_summary
from backend.services.tasks.store import TaskStore
from backend.services.templates.conversion import TemplateConversionService
from backend.services.templates.service import TemplateService


class TaskService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._store = TaskStore(
            config.mongodb_uri,
            config.mongodb_db,
            config.mongodb_tasks_collection,
        )
        self._generation = GenerationService(config)
        self._templates = TemplateService(config)
        self._transcripts = FileService(config.transcript_dir)
        self._template_files = FileService(config.template_dir)
        self._output = FileService(config.output_dir)
        self._conversion_sources_dir = config.template_conversion_sources_dir
        self._broadcaster = TaskBroadcaster()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()
        self._last_reconcile = 0.0
        self._recover_tasks()

    @property
    def max_concurrent_generations(self) -> int:
        return self._config.max_concurrent_generations

    @property
    def broadcaster(self) -> TaskBroadcaster:
        return self._broadcaster

    async def broadcast_tasks(self) -> None:
        summaries = [task_to_summary(task) for task in self.list_tasks()]
        await self._broadcaster.broadcast_snapshot(summaries)

    def _schedule_broadcast(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.broadcast_tasks())

    def _recover_tasks(self) -> None:
        self._store.reset_running_tasks()
        for task in self._store.list_all():
            if task.status == "pending":
                self._enqueue(task.id)

    def _enqueue(self, task_id: str) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._queue.put_nowait, task_id)
            return
        self._queue.put_nowait(task_id)

    def close(self) -> None:
        self._store.close()

    async def start_worker(self) -> None:
        if self._worker_task is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._shutdown.clear()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop_worker(self) -> None:
        self._shutdown.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def create_generate_task(
        self,
        *,
        transcript_name: str,
        template_name: str,
    ) -> Task:
        self._transcripts.resolve_path(transcript_name)
        self._template_files.resolve_path(template_name)

        task = Task.create_generate(
            GenerateTaskPayload(
                transcript_name=transcript_name,
                template_name=template_name,
            )
        )
        self._store.save(task)
        self._enqueue(task.id)
        self._schedule_broadcast()
        return task

    def create_convert_template_task(self, *, source_filename: str, raw: bytes) -> Task:
        if not source_filename:
            raise ValidationError("Filename is required.")
        if not raw:
            raise ValidationError("Uploaded file is empty.")
        if not TemplateConversionService.is_convertible_filename(source_filename):
            extensions = ", ".join(sorted(TemplateConversionService.supported_extensions()))
            raise ValidationError(
                f"Unsupported template source type. Supported extensions: {extensions}"
            )

        task = Task.create_convert_template(
            ConvertTemplateTaskPayload(
                source_filename=Path(source_filename).name,
                staging_name="",
            )
        )
        task.output_name = template_output_name_for_task(task_id=task.id)
        staging_name = self._save_conversion_source(
            task_id=task.id,
            source_filename=source_filename,
            raw=raw,
        )
        task.payload = ConvertTemplateTaskPayload(
            source_filename=Path(source_filename).name,
            staging_name=staging_name,
        )
        self._store.save(task)
        self._enqueue(task.id)
        self._schedule_broadcast()
        return task

    def list_tasks(self, *, active_only: bool = False) -> list[Task]:
        tasks = self._store.list_all()
        if active_only:
            return [task for task in tasks if task.status in ("pending", "running")]
        return tasks

    def get_task(self, task_id: str) -> Task:
        return self._store.load(task_id)

    def get_task_output_content(self, task_id: str) -> str | None:
        task = self._store.load(task_id)
        if task.status != "completed" or not task.output_name:
            return None
        try:
            if task.type == "convert_template":
                return self._template_files.get_file(task.output_name).content
            return self._output.get_file(task.output_name).content
        except NotFoundError:
            return None

    def delete_tasks_for_output(self, output_name: str) -> int:
        deleted = self._store.delete_by_output_name(output_name)
        if deleted:
            self._schedule_broadcast()
        return deleted

    def delete_tasks_for_template(self, template_name: str) -> int:
        for document in self._store.find_for_template_delete(template_name):
            if document.get("type") != "convert_template":
                continue
            staging_name = document.get("payload", {}).get("staging_name")
            if staging_name:
                self._delete_conversion_source(staging_name)

        deleted = self._store.delete_by_template_name(template_name)
        if deleted:
            self._schedule_broadcast()
        return deleted

    def _save_conversion_source(
        self,
        *,
        task_id: str,
        source_filename: str,
        raw: bytes,
    ) -> str:
        suffix = Path(source_filename).suffix.lower()
        staging_name = f"{task_id}{suffix}"
        self._conversion_sources_dir.mkdir(parents=True, exist_ok=True)
        path = self._conversion_sources_dir / staging_name
        path.write_bytes(raw)
        return staging_name

    def _delete_conversion_source(self, staging_name: str) -> None:
        if not staging_name:
            return
        path = self._conversion_sources_dir / staging_name
        if path.is_file():
            path.unlink()

    async def _worker_loop(self) -> None:
        while not self._shutdown.is_set():
            await self._reconcile_pending_tasks()
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if self._shutdown.is_set():
                break

            try:
                await self._run_task(task_id)
            except Exception:
                continue

    async def _reconcile_pending_tasks(self) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        if now - self._last_reconcile < 30.0:
            return
        self._last_reconcile = now

        for task in self._store.list_all():
            if task.status == "pending":
                self._enqueue(task.id)

    async def _run_task(self, task_id: str) -> None:
        try:
            task = self._store.load(task_id)
        except NotFoundError:
            return

        if task.status != "pending":
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.error = None
        self._store.save(task)
        await self.broadcast_tasks()

        try:
            if task.type == "generate":
                await self._run_generate_task(task)
            elif task.type == "convert_template":
                await self._run_convert_template_task(task)
            else:
                raise ValidationError(f"Unsupported task type: {task.type}")
            task.status = "completed"
        except ServiceError as exc:
            task.status = "failed"
            task.error = str(exc)
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
        finally:
            task.finished_at = datetime.now(timezone.utc)
            self._store.save(task)
            await self.broadcast_tasks()

    async def _run_generate_task(self, task: Task) -> None:
        if not isinstance(task.payload, GenerateTaskPayload):
            raise ValidationError("Invalid generate task payload.")

        output_name = output_name_for_task(task_id=task.id, at=task.started_at)
        result = await asyncio.to_thread(
            self._generation.generate,
            transcript_name=task.payload.transcript_name,
            template_name=task.payload.template_name,
            output_name=output_name,
        )
        task.output_name = result.output_name

    async def _run_convert_template_task(self, task: Task) -> None:
        if not isinstance(task.payload, ConvertTemplateTaskPayload):
            raise ValidationError("Invalid convert-template task payload.")

        staging_path = self._conversion_sources_dir / task.payload.staging_name
        if not staging_path.is_file():
            raise NotFoundError(
                f"Conversion source file not found: {task.payload.source_filename}"
            )

        try:
            raw = staging_path.read_bytes()
            if not task.output_name:
                raise ValidationError("Convert task is missing output_name.")
            await asyncio.to_thread(
                self._templates.convert_from_document,
                task.payload.source_filename,
                raw,
                task.output_name,
            )
        finally:
            self._delete_conversion_source(task.payload.staging_name)
