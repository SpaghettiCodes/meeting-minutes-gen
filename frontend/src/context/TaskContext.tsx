import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getTasksWebSocketUrl, listTasks } from "../api/client";
import type { TaskSummary } from "../types";

interface TaskContextValue {
  tasks: TaskSummary[];
  activeCount: number;
  loading: boolean;
  error: string | null;
  refreshTasks: () => Promise<void>;
}

const TaskContext = createContext<TaskContextValue | null>(null);

const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;

interface TaskSnapshotMessage {
  type: "snapshot";
  tasks: TaskSummary[];
}

function isTaskSnapshotMessage(value: unknown): value is TaskSnapshotMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    value.type === "snapshot" &&
    "tasks" in value &&
    Array.isArray(value.tasks)
  );
}

export function TaskProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const retryDelayRef = useRef(INITIAL_RETRY_MS);

  const refreshTasks = useCallback(async () => {
    try {
      const data = await listTasks();
      setTasks(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  const activeCount = useMemo(
    () => tasks.filter((task) => task.status === "pending" || task.status === "running").length,
    [tasks],
  );

  useEffect(() => {
    let cancelled = false;

    const clearRetryTimer = () => {
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (cancelled) {
        return;
      }

      clearRetryTimer();
      retryTimerRef.current = window.setTimeout(() => {
        retryDelayRef.current = Math.min(retryDelayRef.current * 2, MAX_RETRY_MS);
        connect();
      }, retryDelayRef.current);
    };

    const connect = () => {
      if (cancelled) {
        return;
      }

      clearRetryTimer();
      socketRef.current?.close();

      const socket = new WebSocket(getTasksWebSocketUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        retryDelayRef.current = INITIAL_RETRY_MS;
        setError(null);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data as string) as unknown;
          if (isTaskSnapshotMessage(payload)) {
            setTasks(payload.tasks);
            setError(null);
            setLoading(false);
          }
        } catch {
          setError("Received invalid task update");
        }
      };

      socket.onerror = () => {
        setError("Task connection error");
      };

      socket.onclose = () => {
        if (cancelled) {
          return;
        }
        setLoading(false);
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearRetryTimer();
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const value = useMemo(
    () => ({
      tasks,
      activeCount,
      loading,
      error,
      refreshTasks,
    }),
    [tasks, activeCount, loading, error, refreshTasks],
  );

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>;
}

export function useTasks() {
  const context = useContext(TaskContext);
  if (!context) {
    throw new Error("useTasks must be used within TaskProvider");
  }
  return context;
}
