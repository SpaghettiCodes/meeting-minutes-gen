import { useEffect, useState } from "react";
import { createGenerateTask, listFiles } from "../api/client";
import { useTasks } from "../context/TaskContext";

interface GeneratePanelProps {
  refreshToken: number;
  onViewTasks: () => void;
}

export function GeneratePanel({ refreshToken, onViewTasks }: GeneratePanelProps) {
  const { refreshTasks } = useTasks();
  const [transcripts, setTranscripts] = useState<string[]>([]);
  const [templates, setTemplates] = useState<string[]>([]);
  const [transcriptName, setTranscriptName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queuedMessage, setQueuedMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadOptions() {
      setLoadingOptions(true);
      setError(null);
      try {
        const [transcriptFiles, templateFiles] = await Promise.all([
          listFiles("transcripts"),
          listFiles("templates"),
        ]);
        if (cancelled) {
          return;
        }
        const transcriptNames = transcriptFiles.map((file) => file.name);
        const templateNames = templateFiles.map((file) => file.name);
        setTranscripts(transcriptNames);
        setTemplates(templateNames);
        setTranscriptName((current) =>
          current && transcriptNames.includes(current)
            ? current
            : transcriptNames[0] ?? "",
        );
        setTemplateName((current) =>
          current && templateNames.includes(current) ? current : templateNames[0] ?? "",
        );
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load options");
        }
      } finally {
        if (!cancelled) {
          setLoadingOptions(false);
        }
      }
    }

    void loadOptions();
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  const handleGenerate = async () => {
    if (!transcriptName || !templateName) {
      setError("Select both a transcript and a template.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setQueuedMessage(null);

    try {
      const response = await createGenerateTask(transcriptName, templateName);
      setQueuedMessage(`Generation queued (task ${response.task_id.slice(0, 8)}…).`);
      await refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to queue generation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="panel w-full">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="m-0 text-xl font-semibold">Generate Minutes</h2>
          <p className="m-0 text-stone-600">
            Pick a transcript and template, then queue generation. Track progress in Tasks.
          </p>
        </div>
      </div>

      {error && <div className="banner-error">{error}</div>}

      {queuedMessage && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[0.85rem] border border-stone-900/12 bg-stone-100 px-4 py-3.5">
          <span>{queuedMessage}</span>
          <button type="button" className="btn btn-primary" onClick={onViewTasks}>
            View in Tasks
          </button>
        </div>
      )}

      <div className="grid shrink-0 grid-cols-1 items-end gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">Transcript</span>
          <select
            className="rounded-[0.85rem] border border-stone-900/12 bg-white px-3.5 py-3"
            value={transcriptName}
            disabled={loadingOptions || transcripts.length === 0}
            onChange={(event) => setTranscriptName(event.target.value)}
          >
            {transcripts.length === 0 ? (
              <option value="">No transcripts uploaded</option>
            ) : (
              transcripts.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))
            )}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="font-semibold">Template</span>
          <select
            className="rounded-[0.85rem] border border-stone-900/12 bg-white px-3.5 py-3"
            value={templateName}
            disabled={loadingOptions || templates.length === 0}
            onChange={(event) => setTemplateName(event.target.value)}
          >
            {templates.length === 0 ? (
              <option value="">No templates uploaded</option>
            ) : (
              templates.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))
            )}
          </select>
        </label>

        <button
          type="button"
          className="btn btn-primary col-span-full justify-self-start"
          disabled={loadingOptions || submitting || !transcriptName || !templateName}
          onClick={() => void handleGenerate()}
        >
          {submitting ? "Queueing…" : "Generate meeting minutes"}
        </button>
      </div>
    </section>
  );
}
