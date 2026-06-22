import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import { exportMinutes, downloadBlob } from "../api/client";
import remarkBreaks from "remark-breaks";

export type ExportFormat = "md" | "docx" | "pdf";

interface MinutesOutputProps {
  content: string;
  filename: string;
  loading?: boolean;
  loadingMessage?: string;
  emptyMessage?: string;
}

function downloadMarkdown(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  downloadBlob(blob, filename);
}

export function MinutesOutput({
  content,
  filename,
  loading = false,
  loadingMessage = "Loading…",
  emptyMessage = "Generated minutes will appear here.",
}: MinutesOutputProps) {
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async (format: ExportFormat) => {
    if (!content || !filename) {
      return;
    }

    setExportingFormat(format);
    setError(null);

    try {
      if (format === "md") {
        downloadMarkdown(content, filename);
        return;
      }

      const blob = await exportMinutes(content, filename, format);
      const extension = format === "docx" ? ".docx" : ".pdf";
      const stem = filename.replace(/\.[^.]+$/, "");
      downloadBlob(blob, `${stem}${extension}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportingFormat(null);
    }
  };

  const hasContent = Boolean(content);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-stone-900/8 px-4 py-3.5">
        <h3 className="m-0 font-semibold">{filename || "Output preview"}</h3>
        {hasContent && (
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => void navigator.clipboard.writeText(content)}
            >
              Copy
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={exportingFormat !== null}
              onClick={() => void handleExport("md")}
            >
              {exportingFormat === "md" ? "Downloading…" : "Download .md"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={exportingFormat !== null}
              onClick={() => void handleExport("docx")}
            >
              {exportingFormat === "docx" ? "Exporting…" : "Download .docx"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={exportingFormat !== null}
              onClick={() => void handleExport("pdf")}
            >
              {exportingFormat === "pdf" ? "Exporting…" : "Download .pdf"}
            </button>
          </div>
        )}
      </div>

      {error && <div className="banner-error mx-4 shrink-0">{error}</div>}

      <div className="grid min-h-0 flex-1 grid-cols-1 border-t border-stone-900/8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] max-md:grid-rows-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex min-h-0 min-w-0 flex-col border-stone-900/8 md:border-r max-md:border-b max-md:border-r-0">
          <div className="shrink-0 border-b border-stone-900/8 bg-stone-50 px-4 py-2.5 text-xs font-bold tracking-wider text-stone-500 uppercase">
            Source
          </div>
          <pre className="m-0 min-h-0 flex-1 overflow-auto p-4 font-mono text-[0.92rem] leading-relaxed break-words whitespace-pre-wrap">
            {loading ? loadingMessage : content || emptyMessage}
          </pre>
        </div>
        <div className="flex min-h-0 min-w-0 flex-col">
          <div className="shrink-0 border-b border-stone-900/8 bg-stone-50 px-4 py-2.5 text-xs font-bold tracking-wider text-stone-500 uppercase">
            Preview
          </div>
          <div className="markdown-preview">
            {loading ? (
              <p className="text-stone-600">{loadingMessage}</p>
            ) : hasContent ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                rehypePlugins={[rehypeRaw]}
              >
                {content}
              </ReactMarkdown>
            ) : (
              <p className="text-stone-600">{emptyMessage}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
