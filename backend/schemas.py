from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    name: str
    size_bytes: int
    modified_at: datetime


class TextFileContent(BaseModel):
    name: str
    content: str


class UploadResponse(BaseModel):
    name: str
    message: str = "File uploaded successfully."


class DeleteResponse(BaseModel):
    name: str
    message: str = "File deleted successfully."


class GenerateRequest(BaseModel):
    transcript_name: str = Field(..., description="Filename of an uploaded transcript.")
    template_name: str = Field(..., description="Filename of an uploaded template.")
    output_name: str | None = Field(
        default=None,
        description="Optional output filename. Defaults to {date}-{id}.md.",
    )


class GenerateResponse(BaseModel):
    output_name: str
    content: str
    message: str = "Meeting minutes generated successfully."


class TranscribeResponse(BaseModel):
    name: str
    content: str
    message: str = "Transcript generated successfully."


class ConvertTemplateResponse(BaseModel):
    name: str
    content: str
    message: str = "Template generated successfully."


class ExportRequest(BaseModel):
    content: str = Field(..., description="Markdown content to export.")
    filename: str = Field(..., description="Base filename used for the download.")
    format: Literal["docx", "pdf"] = Field(..., description="Target export format.")


class CreateGenerateTaskRequest(BaseModel):
    transcript_name: str = Field(..., description="Filename of an uploaded transcript.")
    template_name: str = Field(..., description="Filename of an uploaded template.")


class CreateTaskResponse(BaseModel):
    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    message: str = "Task queued."


class TaskSummary(BaseModel):
    id: str
    type: Literal["generate", "convert_template"]
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    transcript_name: str | None = None
    template_name: str | None = None
    source_filename: str | None = None
    output_name: str | None = None
    error: str | None = None


class TaskDetail(TaskSummary):
    content: str | None = None
