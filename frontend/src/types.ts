export interface FileMetadata {
  name: string;
  size_bytes: number;
  modified_at: string;
}

export interface TextFileContent {
  name: string;
  content: string;
}

export interface UploadResponse {
  name: string;
  message: string;
}

export interface DeleteResponse {
  name: string;
  message: string;
}

export interface GenerateResponse {
  output_name: string;
  content: string;
  message: string;
}

export interface TranscribeResponse {
  name: string;
  content: string;
  message: string;
}

export interface ConvertTemplateResponse {
  name: string;
  content: string;
  message: string;
}

export type LibraryKind = "transcripts" | "templates" | "minutes";

export type ExportFormat = "docx" | "pdf";

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export type TaskType = "generate" | "convert_template";

export interface TaskSummary {
  id: string;
  type: TaskType;
  status: TaskStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  transcript_name: string | null;
  template_name: string | null;
  source_filename: string | null;
  output_name: string | null;
  error: string | null;
}

export interface TaskDetail extends TaskSummary {
  content: string | null;
}

export interface CreateTaskResponse {
  task_id: string;
  status: TaskStatus;
  message: string;
}

export type AppView = "generate" | "tasks" | LibraryKind;
