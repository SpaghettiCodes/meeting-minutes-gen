import type {
  CreateTaskResponse,
  DeleteResponse,
  ExportFormat,
  FileMetadata,
  GenerateResponse,
  LibraryKind,
  TaskDetail,
  TaskSummary,
  TextFileContent,
  UploadResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export function getTasksWebSocketUrl(): string {
  if (API_BASE) {
    const url = new URL(API_BASE);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/api/tasks/ws";
    url.search = "";
    url.hash = "";
    return url.toString();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/tasks/ws`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail.map((item) => item.msg ?? "Request failed").join(", ");
      }
    } catch {
      // Keep default status text.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function listFiles(kind: LibraryKind): Promise<FileMetadata[]> {
  return request<FileMetadata[]>(`/api/${kind}`);
}

export function getFile(kind: LibraryKind, name: string): Promise<TextFileContent> {
  return request<TextFileContent>(`/api/${kind}/${encodeURIComponent(name)}`);
}

export function deleteFile(kind: LibraryKind, name: string): Promise<DeleteResponse> {
  return request<DeleteResponse>(`/api/${kind}/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export async function uploadFile(
  kind: "transcripts" | "templates",
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadResponse>(`/api/${kind}`, {
    method: "POST",
    body: formData,
  });
}

export async function createTranscribeTask(
  file: File,
): Promise<CreateTaskResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<CreateTaskResponse>("/api/tasks/transcribe", {
    method: "POST",
    body: formData,
  });
}

export async function createConvertTemplateTask(
  file: File,
): Promise<CreateTaskResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<CreateTaskResponse>("/api/tasks/convert-template", {
    method: "POST",
    body: formData,
  });
}

export function generateMinutes(
  transcriptName: string,
  templateName: string,
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript_name: transcriptName,
      template_name: templateName,
    }),
  });
}

export function createGenerateTask(
  transcriptName: string,
  templateName: string,
): Promise<CreateTaskResponse> {
  return request<CreateTaskResponse>("/api/tasks/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript_name: transcriptName,
      template_name: templateName,
    }),
  });
}

export function listTasks(activeOnly = false): Promise<TaskSummary[]> {
  const query = activeOnly ? "?active_only=true" : "";
  return request<TaskSummary[]>(`/api/tasks${query}`);
}

export function getTask(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export async function exportMinutes(
  content: string,
  filename: string,
  format: ExportFormat,
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, filename, format }),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail.map((item) => item.msg ?? "Request failed").join(", ");
      }
    } catch {
      // Keep default status text.
    }
    throw new Error(detail);
  }
  return response.blob();
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}
