"use client";

import type { TaskEvent, TaskStatus } from "@videomaker/contracts";
import { useCallback, useEffect, useRef, useState } from "react";

import { getTask, getTaskEventsUrl } from "@/lib/apiClient";

import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";

const SSE_FAILURE_THRESHOLD = 3;
const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES: TaskStatus[] = [
  "succeeded",
  "failed",
  "cancelled",
];

export type MultiTaskSpec = {
  taskId: string;
  label?: string;
};

export type UseMultiTaskProgressOptions = {
  tasks: MultiTaskSpec[];
  enabled?: boolean;
  watchKey?: number;
  onTaskTerminal?: (event: TaskEvent) => void;
  onAllTerminal?: (events: Record<string, TaskEvent>) => void;
};

export type UseMultiTaskProgressResult = {
  events: Record<string, TaskEvent>;
  modes: Record<string, TaskProgressMode>;
  sseFailureCount: number;
  error: string | null;
};

function isTerminal(status: TaskStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function useMultiTaskProgress({
  tasks,
  enabled = true,
  watchKey = 0,
  onTaskTerminal,
  onAllTerminal,
}: UseMultiTaskProgressOptions): UseMultiTaskProgressResult {
  const [events, setEvents] = useState<Record<string, TaskEvent>>({});
  const [modes, setModes] = useState<Record<string, TaskProgressMode>>({});
  const [sseFailureCount, setSseFailureCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onTaskTerminalRef = useRef(onTaskTerminal);
  const onAllTerminalRef = useRef(onAllTerminal);
  onTaskTerminalRef.current = onTaskTerminal;
  onAllTerminalRef.current = onAllTerminal;

  const eventsRef = useRef<Record<string, TaskEvent>>({});
  const notifiedTerminalRef = useRef<Set<string>>(new Set());
  const allTerminalNotifiedRef = useRef(false);

  const applyEvent = useCallback((next: TaskEvent) => {
    setEvents((prev) => {
      const merged = { ...prev, [next.taskId]: next };
      eventsRef.current = merged;
      return merged;
    });
    setError(null);

    if (isTerminal(next.status) && !notifiedTerminalRef.current.has(next.taskId)) {
      notifiedTerminalRef.current.add(next.taskId);
      onTaskTerminalRef.current?.(next);
    }

    const taskIds = tasks.map((task) => task.taskId);
    const allTerminal =
      taskIds.length > 0 &&
      taskIds.every((taskId) => {
        const event = eventsRef.current[taskId];
        return event && isTerminal(event.status);
      });
    if (allTerminal && !allTerminalNotifiedRef.current) {
      allTerminalNotifiedRef.current = true;
      onAllTerminalRef.current?.(eventsRef.current);
    }
  }, [tasks]);

  useEffect(() => {
    if (!enabled || tasks.length === 0) {
      setEvents({});
      setModes({});
      eventsRef.current = {};
      notifiedTerminalRef.current = new Set();
      allTerminalNotifiedRef.current = false;
      setSseFailureCount(0);
      return;
    }

    let disposed = false;
    const cleanups: Array<() => void> = [];
    notifiedTerminalRef.current = new Set();
    allTerminalNotifiedRef.current = false;
    eventsRef.current = {};
    setEvents({});
    setModes({});
    setSseFailureCount(0);

    for (const task of tasks) {
      const taskId = task.taskId;
      setModes((prev) => ({ ...prev, [taskId]: "sse" }));

      const pollOnce = async () => {
        if (disposed) return;
        try {
          const { data } = await getTask(taskId);
          applyEvent(data);
        } catch (err) {
          setError(err instanceof Error ? err.message : "轮询任务失败");
        }
      };

      void pollOnce();

      const source = new EventSource(getTaskEventsUrl(taskId));
      let failures = 0;
      let pollTimer: ReturnType<typeof setInterval> | undefined;

      const switchToPolling = () => {
        if (disposed) return;
        source.close();
        setModes((prev) => ({ ...prev, [taskId]: "polling" }));
        void pollOnce();
        pollTimer = setInterval(() => {
          void pollOnce();
        }, POLL_INTERVAL_MS);
      };

      const registerSseFailure = () => {
        failures += 1;
        setSseFailureCount((count) => count + 1);
        if (failures >= SSE_FAILURE_THRESHOLD) {
          switchToPolling();
        }
      };

      source.addEventListener("task", (message: MessageEvent) => {
        try {
          const parsed = JSON.parse(message.data as string) as TaskEvent;
          applyEvent(parsed);
          failures = 0;
        } catch {
          registerSseFailure();
        }
      });
      source.onerror = () => {
        registerSseFailure();
      };

      cleanups.push(() => {
        source.close();
        if (pollTimer) clearInterval(pollTimer);
      });
    }

    return () => {
      disposed = true;
      for (const cleanup of cleanups) cleanup();
    };
  }, [applyEvent, enabled, tasks, watchKey]);

  return { events, modes, sseFailureCount, error };
}
