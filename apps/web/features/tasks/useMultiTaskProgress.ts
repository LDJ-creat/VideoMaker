"use client";

import type { TaskEvent, TaskStatus } from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getTask, getTaskEventsUrl } from "@/lib/apiClient";
import { preferTaskError } from "@/lib/taskEventMerge";
import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";

const SSE_FAILURE_THRESHOLD = 3;
const POLL_INTERVAL_MS = 3000;

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

export type MultiTaskProgressSlice = {
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
};

export type UseMultiTaskProgressResult = {
  events: Record<string, TaskEvent>;
  modes: Record<string, TaskProgressMode>;
  /** @deprecated Prefer `sseFailureCounts` or `byTaskId`. */
  sseFailureCount: number;
  sseFailureCounts: Record<string, number>;
  byTaskId: Record<string, MultiTaskProgressSlice>;
  error: string | null;
  allTerminal: boolean;
  anyFailed: boolean;
};

function buildTaskIdsKey(tasks: MultiTaskSpec[]): string {
  return tasks
    .map((task) => task.taskId)
    .sort()
    .join("|");
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
  const [sseFailureCounts, setSseFailureCounts] = useState<
    Record<string, number>
  >({});
  const [error, setError] = useState<string | null>(null);

  const taskIdsKey = useMemo(() => buildTaskIdsKey(tasks), [tasks]);
  const tasksRef = useRef(tasks);
  tasksRef.current = tasks;

  const onTaskTerminalRef = useRef(onTaskTerminal);
  const onAllTerminalRef = useRef(onAllTerminal);
  onTaskTerminalRef.current = onTaskTerminal;
  onAllTerminalRef.current = onAllTerminal;

  const eventsRef = useRef<Record<string, TaskEvent>>({});
  const notifiedTerminalRef = useRef<Set<string>>(new Set());
  const allTerminalNotifiedRef = useRef(false);

  const applyEvent = useCallback((next: TaskEvent) => {
    const previous = eventsRef.current[next.taskId] ?? null;
    const mergedEvent = preferTaskError(previous, next);
    const merged = { ...eventsRef.current, [next.taskId]: mergedEvent };
    eventsRef.current = merged;
    setEvents(merged);
    setError(null);

    if (
      isTaskTerminalStatus(next.status) &&
      !notifiedTerminalRef.current.has(next.taskId)
    ) {
      notifiedTerminalRef.current.add(next.taskId);
      onTaskTerminalRef.current?.(next);
    }

    const tracked = tasksRef.current;
    const allTerminal =
      tracked.length > 0 &&
      tracked.every((task) => {
        const event = eventsRef.current[task.taskId];
        return event && isTaskTerminalStatus(event.status);
      });
    if (allTerminal && !allTerminalNotifiedRef.current) {
      allTerminalNotifiedRef.current = true;
      onAllTerminalRef.current?.(eventsRef.current);
    }
  }, []);

  useEffect(() => {
    if (!enabled || tasks.length === 0) {
      setEvents({});
      setModes({});
      eventsRef.current = {};
      notifiedTerminalRef.current = new Set();
      allTerminalNotifiedRef.current = false;
      setSseFailureCounts({});
      return;
    }

    let disposed = false;
    const cleanups: Array<() => void> = [];
    notifiedTerminalRef.current = new Set();
    allTerminalNotifiedRef.current = false;
    eventsRef.current = {};
    setEvents({});
    setModes({});
    setSseFailureCounts({});

    for (const task of tasks) {
      const taskId = task.taskId;
      setModes((prev) => ({ ...prev, [taskId]: "sse" }));

      let source: EventSource | undefined;
      let failures = 0;
      let pollTimer: ReturnType<typeof setInterval> | undefined;
      let taskStopped = false;

      const stopTaskWatch = () => {
        if (taskStopped) return;
        taskStopped = true;
        source?.close();
        source = undefined;
        if (pollTimer) {
          clearInterval(pollTimer);
          pollTimer = undefined;
        }
        setModes((prev) => ({ ...prev, [taskId]: "completed" }));
      };

      const pollOnce = async () => {
        if (disposed || taskStopped) return;
        try {
          const { data } = await getTask(taskId);
          applyEvent(data);
          if (isTaskTerminalStatus(data.status)) {
            stopTaskWatch();
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "轮询任务失败");
        }
      };

      void pollOnce();

      source = new EventSource(getTaskEventsUrl(taskId));

      const switchToPolling = () => {
        if (disposed || taskStopped) return;
        source?.close();
        source = undefined;
        setModes((prev) => ({ ...prev, [taskId]: "polling" }));
        void pollOnce();
        pollTimer = setInterval(() => {
          void pollOnce();
        }, POLL_INTERVAL_MS);
      };

      const registerSseFailure = () => {
        if (taskStopped) return;
        failures += 1;
        setSseFailureCounts((prev) => ({
          ...prev,
          [taskId]: (prev[taskId] ?? 0) + 1,
        }));
        if (failures >= SSE_FAILURE_THRESHOLD) {
          switchToPolling();
        }
      };

      source.addEventListener("task", (message: MessageEvent) => {
        if (taskStopped) return;
        try {
          const parsed = JSON.parse(message.data as string) as TaskEvent;
          applyEvent(parsed);
          failures = 0;
          if (isTaskTerminalStatus(parsed.status)) {
            stopTaskWatch();
          }
        } catch {
          registerSseFailure();
        }
      });
      source.onerror = () => {
        registerSseFailure();
      };

      cleanups.push(() => {
        stopTaskWatch();
      });
    }

    return () => {
      disposed = true;
      for (const cleanup of cleanups) cleanup();
    };
  }, [applyEvent, enabled, taskIdsKey, watchKey]);

  const allTerminal = useMemo(() => {
    if (tasks.length === 0) return false;
    return tasks.every((task) => {
      const event = events[task.taskId];
      return event && isTaskTerminalStatus(event.status);
    });
  }, [events, tasks]);

  const anyFailed = useMemo(
    () =>
      Object.values(events).some(
        (event) => event.status === "failed" || event.status === "cancelled",
      ),
    [events],
  );

  const byTaskId = useMemo(() => {
    const slices: Record<string, MultiTaskProgressSlice> = {};
    for (const task of tasks) {
      slices[task.taskId] = {
        event: events[task.taskId] ?? null,
        mode: modes[task.taskId] ?? "idle",
        sseFailureCount: sseFailureCounts[task.taskId] ?? 0,
        error,
      };
    }
    return slices;
  }, [error, events, modes, sseFailureCounts, tasks]);

  const sseFailureCount = useMemo(
    () => Math.max(0, ...Object.values(sseFailureCounts)),
    [sseFailureCounts],
  );

  return {
    events,
    modes,
    sseFailureCount,
    sseFailureCounts,
    byTaskId,
    error,
    allTerminal,
    anyFailed,
  };
}
