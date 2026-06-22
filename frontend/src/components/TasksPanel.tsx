import { useState } from "react";
import { formatDate, getTask } from "../api/client";
import { cn } from "../lib/cn";
import type { TaskStatus, TaskSummary, TaskType } from "../types";
import { useTasks } from "../context/TaskContext";
import { GenerateResultModal } from "./GenerateResultModal";

const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

const TASK_TYPE_LABEL: Record<TaskType, string> = {
  generate: "Generate minutes",
  convert_template: "Convert template",
};

function formatDuration(startedAt: string | null, finishedAt: string | null): string | null {
  if (!startedAt || !finishedAt) {
    return null;
  }
  const seconds = Math.max(
    0,
    Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000),
  );
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

function taskDescription(task: TaskSummary): string {
  if (task.type === "convert_template") {
    return task.source_filename ?? "Template conversion";
  }
  return `${task.transcript_name ?? "?"} · ${task.template_name ?? "?"}`;
}

function resultTitle(taskType: TaskType): string {
  return taskType === "convert_template" ? "Template" : "Meeting minutes";
}

interface TasksPanelProps {
  onGenerated: () => void;
}

export function TasksPanel({ onGenerated }: TasksPanelProps) {
  const { tasks, loading, error, refreshTasks } = useTasks();
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [resultContent, setResultContent] = useState("");
  const [outputName, setOutputName] = useState("");
  const [modalTitle, setModalTitle] = useState("Meeting minutes");

  const activeTasks = tasks.filter(
    (task) => task.status === "pending" || task.status === "running",
  );
  const recentTasks = tasks.filter(
    (task) => task.status === "completed" || task.status === "failed",
  );

  const openCompletedTask = async (task: TaskSummary) => {
    if (task.status !== "completed") {
      return;
    }

    setModalOpen(true);
    setModalLoading(true);
    setModalError(null);
    setResultContent("");
    setOutputName("");
    setModalTitle(resultTitle(task.type));

    try {
      const detail = await getTask(task.id);
      if (!detail.output_name) {
        throw new Error("Task completed but output filename is missing.");
      }
      if (!detail.content) {
        throw new Error("The output file was deleted.");
      }
      setResultContent(detail.content);
      setOutputName(detail.output_name);
      onGenerated();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to load result");
    } finally {
      setModalLoading(false);
    }
  };

  const renderTaskRow = (task: TaskSummary) => {
    const duration = formatDuration(task.started_at, task.finished_at);
    const isClickable = task.status === "completed";

    return (
      <div
        key={task.id}
        className={cn(
          "rounded-[0.85rem] border border-stone-900/8 bg-white px-4 py-3.5",
          isClickable && "cursor-pointer hover:bg-stone-50",
        )}
        onClick={isClickable ? () => void openCompletedTask(task) : undefined}
        onKeyDown={
          isClickable
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  void openCompletedTask(task);
                }
              }
            : undefined
        }
        role={isClickable ? "button" : undefined}
        tabIndex={isClickable ? 0 : undefined}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="truncate font-semibold">
              {task.output_name ?? `${TASK_TYPE_LABEL[task.type]} ${task.id.slice(0, 8)}…`}
            </div>
            <div className="mt-1 truncate text-sm text-stone-600">
              {TASK_TYPE_LABEL[task.type]} · {taskDescription(task)}
            </div>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full px-2.5 py-1 text-xs font-medium",
              task.status === "pending" && "bg-stone-100 text-stone-700",
              task.status === "running" && "bg-stone-900 text-white",
              task.status === "completed" && "bg-stone-200 text-stone-800",
              task.status === "failed" && "bg-red-50 text-red-800",
            )}
          >
            {STATUS_LABEL[task.status]}
          </span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-500">
          <span>Created {formatDate(task.created_at)}</span>
          {duration && <span>Duration {duration}</span>}
          {task.output_name && <span>{task.output_name}</span>}
        </div>
        {task.error && (
          <p className="mt-2 text-sm text-red-800">{task.error}</p>
        )}
        {isClickable && (
          <p className="mt-2 text-sm text-stone-600">Click to view result</p>
        )}
      </div>
    );
  };

  return (
    <>
      <section className="panel panel-fill">
        <div className="flex shrink-0 items-start justify-between gap-4">
          <div>
            <h2 className="m-0 text-xl font-semibold">Tasks</h2>
            <p className="m-0 text-stone-600">
              Track background generation and template conversion jobs. You can leave this page while they run.
            </p>
          </div>
          <button type="button" className="btn" onClick={() => void refreshTasks()}>
            Refresh
          </button>
        </div>

        {error && <div className="banner-error">{error}</div>}

        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-auto">
          <div>
            <h3 className="m-0 mb-3 text-sm font-semibold tracking-wide text-stone-500 uppercase">
              Active ({activeTasks.length})
            </h3>
            {loading && tasks.length === 0 ? (
              <p className="text-stone-600">Loading tasks…</p>
            ) : activeTasks.length === 0 ? (
              <p className="text-stone-600">No active tasks.</p>
            ) : (
              <div className="flex flex-col gap-2">{activeTasks.map(renderTaskRow)}</div>
            )}
          </div>

          <div>
            <h3 className="m-0 mb-3 text-sm font-semibold tracking-wide text-stone-500 uppercase">
              Recent ({recentTasks.length})
            </h3>
            {recentTasks.length === 0 ? (
              <p className="text-stone-600">Completed and failed tasks will appear here.</p>
            ) : (
              <div className="flex flex-col gap-2">{recentTasks.map(renderTaskRow)}</div>
            )}
          </div>
        </div>
      </section>

      <GenerateResultModal
        open={modalOpen}
        loading={modalLoading}
        error={modalError}
        content={resultContent}
        filename={outputName}
        title={modalTitle}
        onClose={() => {
          if (modalLoading) {
            return;
          }
          setModalOpen(false);
          setModalError(null);
        }}
      />
    </>
  );
}
