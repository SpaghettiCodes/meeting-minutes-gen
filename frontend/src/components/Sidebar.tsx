import { cn } from "../lib/cn";
import { useTasks } from "../context/TaskContext";
import type { AppView } from "../types";

const NAV_ITEMS: { id: AppView; label: string; description: string }[] = [
  { id: "generate", label: "Generate", description: "Create minutes" },
  { id: "tasks", label: "Tasks", description: "Track background jobs" },
  { id: "transcripts", label: "Transcripts", description: "Upload & review" },
  { id: "templates", label: "Templates", description: "Minute formats" },
  { id: "minutes", label: "Minutes", description: "Saved output" },
];

interface SidebarProps {
  activeView: AppView;
  onChange: (view: AppView) => void;
}

export function Sidebar({ activeView, onChange }: SidebarProps) {
  const { activeCount } = useTasks();

  return (
    <nav
      className="flex flex-col gap-3 max-md:grid max-md:grid-cols-2 max-sm:grid-cols-1"
      aria-label="Main navigation"
    >
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={cn(
            "relative flex cursor-pointer flex-col items-start gap-0.5 rounded-2xl border border-transparent bg-white/55 px-4 py-4 text-left transition-[background,border-color,transform] duration-150 hover:-translate-y-px hover:bg-white/90",
            activeView === item.id &&
              "border-stone-900/20 bg-white shadow-[0_10px_30px_rgba(0,0,0,0.06)]",
          )}
          onClick={() => onChange(item.id)}
        >
          <span className="flex w-full items-center gap-2 font-semibold">
            {item.label}
            {item.id === "tasks" && activeCount > 0 && (
              <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-stone-900 px-1.5 py-0.5 text-xs font-medium text-white">
                {activeCount}
              </span>
            )}
          </span>
          <span className="text-stone-600">{item.description}</span>
        </button>
      ))}
    </nav>
  );
}
