import { useEffect } from "react";
import { cn } from "../lib/cn";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  useEffect(() => {
    if (!open || loading) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, loading, onCancel]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/45 p-5 backdrop-blur-sm"
      role="presentation"
      onClick={loading ? undefined : onCancel}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-[1.25rem] border border-stone-900/10 bg-white shadow-[0_24px_60px_rgba(28,25,23,0.18)]"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-message"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-stone-900/8 px-5 py-4">
          <h3 id="confirm-modal-title" className="m-0 text-lg font-semibold">
            {title}
          </h3>
        </div>

        <p id="confirm-modal-message" className="m-0 px-5 py-5 text-stone-700">
          {message}
        </p>

        <div className="flex justify-end gap-2 border-t border-stone-900/8 px-5 py-4">
          <button
            type="button"
            className="btn"
            disabled={loading}
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={cn("btn btn-primary", loading && "opacity-70")}
            disabled={loading}
            onClick={onConfirm}
          >
            {loading ? "Deleting…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
