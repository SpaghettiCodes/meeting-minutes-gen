from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection

from backend.models.task import (
    ConvertTemplateTaskPayload,
    GenerateTaskPayload,
    Task,
    TaskPayload,
    TranscribeTaskPayload,
)
from backend.services.exceptions import NotFoundError


class TaskStore:
    def __init__(self, uri: str, db_name: str, collection_name: str) -> None:
        self._client = MongoClient(uri)
        self._collection: Collection = self._client[db_name][collection_name]
        self._collection.create_index([("created_at", DESCENDING)])
        self._collection.create_index([("status", DESCENDING), ("created_at", DESCENDING)])
        self._collection.create_index([("output_name", DESCENDING)])
        self._collection.update_many({}, {"$unset": {"content": ""}})

    def close(self) -> None:
        self._client.close()

    def save(self, task: Task) -> None:
        self._collection.replace_one(
            {"id": task.id},
            self._to_doc(task),
            upsert=True,
        )

    def load(self, task_id: str) -> Task:
        if not task_id or task_id != task_id.strip():
            raise NotFoundError(f"Task not found: {task_id}")

        document = self._collection.find_one({"id": task_id})
        if document is None:
            raise NotFoundError(f"Task not found: {task_id}")
        return self._from_doc(document)

    def list_all(self) -> list[Task]:
        documents = self._collection.find().sort("created_at", DESCENDING)
        return [self._from_doc(document) for document in documents]

    def reset_running_tasks(self) -> None:
        self._collection.update_many(
            {"status": "running"},
            {"$set": {"status": "pending"}, "$unset": {"started_at": ""}},
        )

    @staticmethod
    def _to_doc(task: Task) -> dict:
        return {
            "id": task.id,
            "type": task.type,
            "status": task.status,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "payload": asdict(task.payload),
            "output_name": task.output_name,
            "error": task.error,
        }

    @staticmethod
    def _payload_from_doc(task_type: str, payload_data: dict) -> TaskPayload:
        if task_type == "convert_template":
            return ConvertTemplateTaskPayload(
                source_filename=payload_data["source_filename"],
                staging_name=payload_data["staging_name"],
            )
        if task_type == "transcribe":
            return TranscribeTaskPayload(
                source_filename=payload_data["source_filename"],
                staging_name=payload_data["staging_name"],
            )
        return GenerateTaskPayload(
            transcript_name=payload_data["transcript_name"],
            template_name=payload_data["template_name"],
        )

    @staticmethod
    def _from_doc(document: dict) -> Task:
        payload_data = document["payload"]
        created_at = document.get("created_at")
        if not isinstance(created_at, datetime):
            created_at = datetime.now()

        task_type = document.get("type", "generate")
        return Task(
            id=document["id"],
            type=task_type,
            status=document["status"],
            created_at=created_at,
            started_at=document.get("started_at"),
            finished_at=document.get("finished_at"),
            payload=TaskStore._payload_from_doc(task_type, payload_data),
            output_name=document.get("output_name"),
            error=document.get("error"),
        )

    def delete_by_output_name(self, output_name: str) -> int:
        result = self._collection.delete_many({"output_name": output_name})
        return result.deleted_count

    def find_for_template_delete(self, template_name: str) -> list[dict]:
        return list(
            self._collection.find(
                self._template_delete_filter(template_name),
                {"type": 1, "payload.staging_name": 1},
            )
        )

    def delete_by_template_name(self, template_name: str) -> int:
        result = self._collection.delete_many(self._template_delete_filter(template_name))
        return result.deleted_count

    def find_for_transcript_delete(self, transcript_name: str) -> list[dict]:
        return list(
            self._collection.find(
                self._transcript_delete_filter(transcript_name),
                {"type": 1, "payload.staging_name": 1},
            )
        )

    def delete_by_transcript_name(self, transcript_name: str) -> int:
        result = self._collection.delete_many(self._transcript_delete_filter(transcript_name))
        return result.deleted_count

    @staticmethod
    def _template_delete_filter(template_name: str) -> dict:
        return {
            "$or": [
                {"output_name": template_name},
                {"type": "generate", "payload.template_name": template_name},
            ]
        }

    @staticmethod
    def _transcript_delete_filter(transcript_name: str) -> dict:
        return {
            "$or": [
                {"type": "transcribe", "output_name": transcript_name},
                {"type": "generate", "payload.transcript_name": transcript_name},
            ]
        }
