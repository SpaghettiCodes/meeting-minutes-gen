import { useCallback, useEffect, useRef, useState } from "react";
import {
  createConvertTemplateTask,
  createTranscribeTask,
  deleteFile,
  formatBytes,
  formatDate,
  getFile,
  listFiles,
  uploadFile,
} from "../api/client";
import { useTasks } from "../context/TaskContext";
import { cn } from "../lib/cn";
import type { FileMetadata, LibraryKind } from "../types";
import { ConfirmModal } from "./ConfirmModal";
import { MinutesOutput } from "./MinutesOutput";

const LIBRARY_COPY: Record<
  LibraryKind,
  { title: string; subtitle: string; uploadLabel: string; empty: string }
> = {
  transcripts: {
    title: "Transcripts",
    subtitle: "Upload text transcripts or transcribe video/audio with local Whisper.",
    uploadLabel: "Upload text",
    empty: "No transcripts yet. Upload text or transcribe a meeting recording.",
  },
  templates: {
    title: "Templates",
    subtitle: "Upload markdown templates or convert an example PDF/Word doc with the LLM.",
    uploadLabel: "Upload markdown",
    empty: "No templates yet. Upload markdown or convert an example PDF/DOCX.",
  },
  minutes: {
    title: "Generated Minutes",
    subtitle: "Previously generated meeting minutes.",
    uploadLabel: "",
    empty: "No minutes generated yet. Use the Generate tab to create one.",
  },
};

const MEDIA_EXTENSIONS = new Set([
  ".mp4", ".mkv", ".mov", ".webm", ".avi", ".mpeg", ".mpg",
  ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus",
]);

const TEMPLATE_SOURCE_EXTENSIONS = new Set([".docx", ".pdf"]);

function isMediaFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return Array.from(MEDIA_EXTENSIONS).some((ext) => name.endsWith(ext));
}

function isTemplateSourceFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return Array.from(TEMPLATE_SOURCE_EXTENSIONS).some((ext) => name.endsWith(ext));
}

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  );
}

interface FileLibraryProps {
  kind: LibraryKind;
  refreshToken?: number;
  onFilesChanged?: () => void;
  onViewTasks?: () => void;
}

export function FileLibrary({
  kind,
  refreshToken = 0,
  onFilesChanged,
  onViewTasks,
}: FileLibraryProps) {
  const copy = LIBRARY_COPY[kind];
  const { refreshTasks } = useTasks();
  const inputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);
  const templateSourceInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<FileMetadata[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const loadFiles = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const data = await listFiles(kind);
      setFiles(data);
      if (data.length === 0) {
        setSelectedName(null);
        setPreview("");
      } else if (!data.some((file) => file.name === selectedName)) {
        setSelectedName(data[0].name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load files");
    } finally {
      setLoadingList(false);
    }
  }, [kind, selectedName]);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles, refreshToken]);

  useEffect(() => {
    if (!selectedName) {
      setPreview("");
      return;
    }

    let cancelled = false;
    setLoadingPreview(true);
    setError(null);

    void getFile(kind, selectedName)
      .then((file) => {
        if (!cancelled) {
          setPreview(file.content);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load file");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPreview(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [kind, selectedName]);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList?.length || kind === "minutes") {
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      for (const file of Array.from(fileList)) {
        if (kind === "transcripts" && isMediaFile(file)) {
          await createTranscribeTask(file);
          await refreshTasks();
          setSuccess(
            `Queued transcription for "${file.name}". Track progress in Tasks.`,
          );
          onViewTasks?.();
        } else if (kind === "templates" && isTemplateSourceFile(file)) {
          await createConvertTemplateTask(file);
          await refreshTasks();
          setSuccess(
            `Queued conversion for "${file.name}". Track progress in Tasks.`,
          );
          onViewTasks?.();
        } else {
          await uploadFile(kind, file);
        }
      }
      await loadFiles();
      onFilesChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
      if (mediaInputRef.current) {
        mediaInputRef.current.value = "";
      }
      if (templateSourceInputRef.current) {
        templateSourceInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (filename: string) => {
    setDeletingName(filename);
    setError(null);
    try {
      await deleteFile(kind, filename);
      if (selectedName === filename) {
        setSelectedName(null);
        setPreview("");
      }
      setPendingDelete(null);
      await loadFiles();
      onFilesChanged?.();
      if (kind === "minutes" || kind === "templates") {
        await refreshTasks();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingName(null);
    }
  };

  const canUpload = kind !== "minutes";

  return (
    <>
    <section className="panel panel-fill">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="m-0 text-xl font-semibold">{copy.title}</h2>
          <p className="m-0 text-stone-600">{copy.subtitle}</p>
        </div>
        {canUpload && (
          <div className="flex flex-wrap justify-end gap-2">
            <input
              ref={inputRef}
              type="file"
              accept={
                kind === "transcripts"
                  ? ".txt,.md,.markdown,.text"
                  : ".txt,.md,.markdown,.text"
              }
              multiple
              hidden
              onChange={(event) => void handleUpload(event.target.files)}
            />
            {kind === "transcripts" && (
              <input
                ref={mediaInputRef}
                type="file"
                accept=".mp4,.mkv,.mov,.webm,.avi,.mpeg,.mpg,.mp3,.wav,.m4a,.flac,.ogg,.aac,.opus"
                hidden
                onChange={(event) => void handleUpload(event.target.files)}
              />
            )}
            {kind === "templates" && (
              <input
                ref={templateSourceInputRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                hidden
                onChange={(event) => void handleUpload(event.target.files)}
              />
            )}
            <button
              type="button"
              className="btn btn-primary"
              disabled={uploading}
              onClick={() => inputRef.current?.click()}
            >
              {uploading ? "Working…" : copy.uploadLabel}
            </button>
            {kind === "transcripts" && (
              <button
                type="button"
                className="btn"
                disabled={uploading}
                onClick={() => mediaInputRef.current?.click()}
              >
                {uploading ? "Queuing…" : "Transcribe video/audio"}
              </button>
            )}
            {kind === "templates" && (
              <button
                type="button"
                className="btn"
                disabled={uploading}
                onClick={() => templateSourceInputRef.current?.click()}
              >
                {uploading ? "Queuing…" : "Convert PDF/DOCX"}
              </button>
            )}
          </div>
        )}
      </div>

      {canUpload && (
        <div
          className={cn(
            "shrink-0 rounded-2xl border border-dashed border-stone-900/25 bg-stone-100 px-5 py-4 text-center text-stone-900",
            dragActive && "bg-stone-200",
          )}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            void handleUpload(event.dataTransfer.files);
          }}
        >
          Drop{" "}
          {kind === "transcripts"
            ? "text or media files"
            : "markdown, PDF, or Word files"}{" "}
          here
        </div>
      )}

      {error && <div className="banner-error">{error}</div>}
      {success && <div className="rounded-2xl border border-stone-900/10 bg-stone-100 px-4 py-3 text-stone-800">{success}</div>}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[minmax(240px,320px)_minmax(0,1fr)] max-md:grid-rows-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="flex min-h-0 flex-1 flex-col overflow-auto rounded-2xl border border-stone-900/8 bg-white p-2">
          {loadingList ? (
            <p className="text-stone-600">Loading files…</p>
          ) : files.length === 0 ? (
            <p className="text-stone-600">{copy.empty}</p>
          ) : (
            files.map((file) => (
              <div
                key={file.name}
                className={cn(
                  "group flex items-center rounded-[0.85rem] border border-transparent",
                  selectedName === file.name
                    ? "border-stone-900/15 bg-stone-100"
                    : "hover:bg-stone-100",
                )}
              >
                <button
                  type="button"
                  className="flex min-w-0 flex-1 cursor-pointer flex-col items-start gap-0.5 bg-transparent px-3.5 py-3.5 text-left"
                  onClick={() => setSelectedName(file.name)}
                >
                  <span className="w-full truncate font-semibold" title={file.name}>
                    {file.name}
                  </span>
                  <span className="text-stone-600">
                    {formatBytes(file.size_bytes)} · {formatDate(file.modified_at)}
                  </span>
                </button>
                <button
                  type="button"
                  className={cn(
                    "mr-2 shrink-0 rounded-md p-1.5 text-stone-500 opacity-0 transition-opacity",
                    "hover:bg-red-50 hover:text-red-800 group-hover:opacity-100 focus:opacity-100",
                    deletingName === file.name && "opacity-100",
                  )}
                  aria-label={`Delete ${file.name}`}
                  disabled={deletingName === file.name}
                  onClick={() => setPendingDelete(file.name)}
                >
                  <TrashIcon />
                </button>
              </div>
            ))
          )}
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-stone-900/8 bg-white">
          {kind === "minutes" ? (
            <MinutesOutput
              content={preview}
              filename={selectedName ?? ""}
              loading={loadingPreview}
              loadingMessage="Loading preview…"
              emptyMessage="Select a file to preview its contents."
            />
          ) : (
            <>
              <div className="flex shrink-0 items-center justify-between gap-4 border-b border-stone-900/8 px-4 py-3.5">
                <h3 className="m-0 font-semibold">{selectedName ?? "Preview"}</h3>
                {selectedName && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      void navigator.clipboard.writeText(preview);
                    }}
                  >
                    Copy
                  </button>
                )}
              </div>
              <pre className="m-0 min-h-0 flex-1 overflow-auto p-4 font-mono text-[0.92rem] leading-relaxed break-words whitespace-pre-wrap">
                {loadingPreview
                  ? "Loading preview…"
                  : preview || "Select a file to preview its contents."}
              </pre>
            </>
          )}
        </div>
      </div>
    </section>

    <ConfirmModal
      open={pendingDelete !== null}
      title="Delete file?"
      message={
        pendingDelete
          ? `Delete "${pendingDelete}"? This cannot be undone.`
          : ""
      }
      loading={deletingName !== null}
      onCancel={() => {
        if (!deletingName) {
          setPendingDelete(null);
        }
      }}
      onConfirm={() => {
        if (pendingDelete) {
          void handleDelete(pendingDelete);
        }
      }}
    />
    </>
  );
}
