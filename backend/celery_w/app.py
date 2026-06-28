from celery import Celery
from backend.models.config import load_config
from backend.services.generation.service import GenerationService
from backend.services.templates.service import TemplateService
from backend.services.transcripts.service import TranscriptService
from backend.services.tasks.store import TaskStore
from datetime import datetime, timezone
import pathlib
import redis

celery_app = Celery(
    "tasks",
    broker="redis://redis:6379/0"
)

config = load_config()
store = TaskStore(config.mongodb_uri, config.mongodb_db, config.mongodb_tasks_collection)
generation_service = GenerationService(config)
template_service = TemplateService(config)
transcript_service = TranscriptService(config)
sync_redis = redis.Redis.from_url("redis://redis:6379/0")

def update_task_status(task_id: str, status: str, error: str = None, output_name: str = None):
    from backend.services.tasks.service import broadcast_current_tasks

    task = store.load(task_id)
    task.status = status
    if status == "running":
        task.started_at = datetime.now(timezone.utc)
        task.error = None
    elif status in ("completed", "failed"):
        task.finished_at = datetime.now(timezone.utc)
        if error:
            task.error = error
        if output_name:
            task.output_name = output_name

    store.save(task)
    broadcast_current_tasks(store, sync_redis)

@celery_app.task(name="tasks.run_generate")
def run_generate_task(task_id: str, transcript_name: str, template_name: str, output_name: str):
    update_task_status(task_id, "running")
    try:
        result = generation_service.generate(
            transcript_name=transcript_name,
            template_name=template_name,
            output_name=output_name,
        )
        update_task_status(task_id, "completed", output_name=result.output_name)
    except Exception as exc:
        update_task_status(task_id, "failed", error=str(exc))


@celery_app.task(name="tasks.run_convert_template")
def run_convert_template_task(task_id: str, source_filename: str, staging_name: str, output_name: str):
    update_task_status(task_id, "running")
    
    conversion_dir = pathlib.Path(config.template_conversion_sources_dir)
    staging_path = conversion_dir / staging_name
    
    try:
        if not staging_path.is_file():
            raise FileNotFoundError(f"Conversion source file not found: {source_filename}")
            
        raw = staging_path.read_bytes()
        template_service.convert_from_document(source_filename, raw, output_name)
        update_task_status(task_id, "completed")
    except Exception as exc:
        update_task_status(task_id, "failed", error=str(exc))
    finally:
        if staging_path.is_file():
            staging_path.unlink()

@celery_app.task(name="tasks.run_transcribe")
def run_transcribe_task(task_id: str, source_filename: str, staging_name: str, output_name: str):
    update_task_status(task_id, "running")
    
    transcription_dir = pathlib.Path(config.transcription_sources_dir)
    staging_path = transcription_dir / staging_name
    
    try:
        if not staging_path.is_file():
            raise FileNotFoundError(f"Transcription source file not found: {source_filename}")
            
        raw = staging_path.read_bytes()
        saved = transcript_service.transcribe_to_file(source_filename, raw, output_name=output_name)
        update_task_status(task_id, "completed", output_name=saved.name)
    except Exception as exc:
        update_task_status(task_id, "failed", error=str(exc))
    finally:
        if staging_path.is_file():
            staging_path.unlink()