from __future__ import annotations

from pathlib import Path

from backend.models.config import AppConfig
from backend.models.task import (
    ConvertTemplateTaskPayload,
    GenerateTaskPayload,
    Task,
    TranscribeTaskPayload,
)
from backend.services.exceptions import ValidationError
from backend.services.files.service import FileService
from backend.services.generation.output_names import (
    output_name_for_task,
    template_output_name_for_task,
    transcript_output_name_for_task,
)
from backend.services.tasks.store import TaskStore
from backend.services.tasks.mappers import task_to_summary
from backend.routers.http_errors import NotFoundError

import json
import redis

def broadcast_current_tasks(store, redis_client) -> None:
    tasks = store.list_all()
    payload = {
        "type": "snapshot",
        "tasks": [task_to_summary(t).model_dump(mode="json") for t in tasks]
    }
    redis_client.publish("task_updates", json.dumps(payload))

class TaskService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._store = TaskStore(
            config.mongodb_uri,
            config.mongodb_db,
            config.mongodb_tasks_collection,
        )
        self._transcript_files = FileService(config.transcript_dir)
        self._template_files = FileService(config.template_dir)
        self._output = FileService(config.output_dir)
        self._conversion_sources_dir = config.template_conversion_sources_dir
        self._transcription_sources_dir = config.transcription_sources_dir
        self.redis_client = redis.Redis('redis')

    async def broadcast_initial_values(self, websocket) -> None:
        initial_tasks = self._store.list_all()
        initial_payload = {
            "type": "snapshot",
            "tasks": [task_to_summary(t).model_dump(mode="json") for t in initial_tasks]
        }
        try:
            await websocket.send_text(json.dumps(initial_payload))
        except Exception:
            pass

    def list_tasks(self, *, active_only: bool = False) -> list[Task]:
        tasks = self._store.list_all()
        if active_only:
            return [task for task in tasks if task.status in ("pending", "running")]
        return tasks

    def _schedule_broadcast(self) -> None:
        broadcast_current_tasks(self._store, self.redis_client)

    def create_generate_task(self, *, transcript_name: str, template_name: str) -> Task:
        from backend.celery_w.app import run_generate_task
        self._transcript_files.resolve_path(transcript_name)
        self._template_files.resolve_path(template_name)

        task = Task.create_generate(
            GenerateTaskPayload(
                transcript_name=transcript_name,
                template_name=template_name,
            )
        )
        self._store.save(task)

        output_name = output_name_for_task(task_id=task.id, at=task.created_at)
        run_generate_task.delay(
            task_id=task.id,
            transcript_name=transcript_name,
            template_name=template_name,
            output_name=output_name
        )
        
        self._schedule_broadcast()
        return task

    def create_convert_template_task(self, *, source_filename: str, raw: bytes) -> Task:
        from backend.celery_w.app import run_convert_template_task

        if not source_filename:
            raise ValidationError("Filename is required.")
        if not raw:
            raise ValidationError("Uploaded file is empty.")

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
        
        run_convert_template_task.delay(
            task_id=task.id,
            source_filename=task.payload.source_filename,
            staging_name=staging_name,
            output_name=task.output_name
        )
        
        self._schedule_broadcast()
        return task

    def create_transcribe_task(self, *, source_filename: str, raw: bytes) -> Task:
        from backend.celery_w.app import run_transcribe_task

        if not source_filename:
            raise ValidationError("Filename is required.")
        if not raw:
            raise ValidationError("Uploaded file is empty.")

        source_name = Path(source_filename).name
        task = Task.create_transcribe(
            TranscribeTaskPayload(
                source_filename=source_name,
                staging_name="",
            )
        )
        task.output_name = transcript_output_name_for_task(task_id=task.id)
        
        staging_name = self._save_transcription_source(
            task_id=task.id,
            source_filename=source_name,
            raw=raw,
        )
        task.payload = TranscribeTaskPayload(
            source_filename=source_name,
            staging_name=staging_name,
        )
        self._store.save(task)
        
        run_transcribe_task.delay(
            task_id=task.id,
            source_filename=source_name,
            staging_name=staging_name,
            output_name=task.output_name
        )
        
        self._schedule_broadcast()
        return task
    
    
    def get_task(self, task_id: str) -> Task:
        return self._store.load(task_id)

    def get_task_output_content(self, task_id: str) -> str | None:
        task = self._store.load(task_id)
        if task.status != "completed" or not task.output_name:
            return None
        try:
            if task.type == "convert_template":
                return self._template_files.get_file(task.output_name).content
            if task.type == "transcribe":
                return self._transcript_files.get_file(task.output_name).content
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

    def delete_tasks_for_transcript(self, transcript_name: str) -> int:
        for document in self._store.find_for_transcript_delete(transcript_name):
            if document.get("type") != "transcribe":
                continue
            staging_name = document.get("payload", {}).get("staging_name")
            if staging_name:
                self._delete_transcription_source(staging_name)

        deleted = self._store.delete_by_transcript_name(transcript_name)
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

    def _save_transcription_source(
        self,
        *,
        task_id: str,
        source_filename: str,
        raw: bytes,
    ) -> str:
        suffix = Path(source_filename).suffix.lower()
        staging_name = f"{task_id}{suffix}"
        self._transcription_sources_dir.mkdir(parents=True, exist_ok=True)
        path = self._transcription_sources_dir / staging_name
        path.write_bytes(raw)
        return staging_name

    def _delete_transcription_source(self, staging_name: str) -> None:
        if not staging_name:
            return
        path = self._transcription_sources_dir / staging_name
        if path.is_file():
            path.unlink()

