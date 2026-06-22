import { useEffect } from "react";
import { cn } from "../lib/cn";
import { MinutesOutput } from "./MinutesOutput";

interface GenerateResultModalProps {
  open: boolean;
  loading: boolean;
  error: string | null;
  content: string;
  filename: string;
  title?: string;
  onClose: () => void;
}

export function GenerateResultModal({
  open,
  loading,
  error,
  content,
  filename,
  title = "Meeting minutes",
  onClose,
}: GenerateResultModalProps) {
  const canClose = !loading;

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && canClose) {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, canClose, onClose]);

  if (!open) {
    return null;
  }

  const isFullScreen = !loading && !error && Boolean(content);

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex justify-center bg-stone-900/45 p-5 backdrop-blur-sm",
        isFullScreen ? "items-stretch" : "items-center",
      )}
      role="presentation"
      onClick={canClose ? onClose : undefined}
    >
      <div
        className={cn(
          "flex flex-col overflow-hidden rounded-[1.25rem] border border-stone-900/10 bg-white shadow-[0_24px_60px_rgba(28,25,23,0.18)]",
          isFullScreen ? "h-full w-full" : "w-full max-w-md",
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="generate-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-4 border-b border-stone-900/8 px-5 py-4">
          <h3 id="generate-modal-title" className="m-0 text-lg font-semibold">
            {loading ? "Loading result" : error ? "Task failed" : title}
          </h3>
          <button
            type="button"
            className="btn btn-ghost min-w-9 px-2 py-1 text-2xl leading-none"
            disabled={!canClose}
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {loading && (
          <div className="px-6 py-8 text-center">
            <p className="mb-5 text-stone-600">Calling Gemini… this may take a minute.</p>
            <div
              className="h-[0.45rem] overflow-hidden rounded-full bg-stone-200"
              role="progressbar"
              aria-label="Generating"
            >
              <div className="h-full w-[40%] animate-progress-indeterminate rounded-full bg-stone-900" />
            </div>
          </div>
        )}

        {error && !loading && <div className="banner-error m-5">{error}</div>}

        {!loading && !error && content && (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <MinutesOutput content={content} filename={filename} />
          </div>
        )}
      </div>
    </div>
  );
}
