"use client";

import type { TaskEvent } from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { preferTaskError, shouldAcceptTaskEventUpdate, taskEventEquals } from "@/lib/taskEventMerge";
import { extractEventId, isTaskMilestone } from "@/lib/taskMilestones";
import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

import { startTaskWatch } from "@/features/tasks/startTaskWatch";
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";

export type MultiTaskSpec = {
  taskId: string;
  label?: string;
};

export type UseMultiTaskProgressOptions = {
  tasks: MultiTaskSpec[];
  enabled?: boolean;
  /** @deprecated Prefer taskWatchKeys for per-task retry reset. */
  watchKey?: number;
  taskWatchKeys?: Record<string, number>;
  onTaskTerminal?: (event: TaskEvent) => void;
  onTaskMilestone?: (event: TaskEvent, previous: TaskEvent | null) => void;
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

function resolveTaskWatchKey(
  taskId: string,
  taskWatchKeys: Record<string, number> | undefined,
  globalWatchKey: number,
): number {
  return taskWatchKeys?.[taskId] ?? globalWatchKey;
}

export function useMultiTaskProgress({
  tasks,
  enabled = true,
  watchKey = 0,
  taskWatchKeys,
  onTaskTerminal,
  onTaskMilestone,
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
  const onTaskMilestoneRef = useRef(onTaskMilestone);
  const onAllTerminalRef = useRef(onAllTerminal);
  onTaskTerminalRef.current = onTaskTerminal;
  onTaskMilestoneRef.current = onTaskMilestone;
  onAllTerminalRef.current = onAllTerminal;

  const eventsRef = useRef<Record<string, TaskEvent>>({});
  const lastEventIdByTaskRef = useRef<Record<string, number>>({});
  const notifiedTerminalRef = useRef<Set<string>>(new Set());
  const allTerminalNotifiedRef = useRef(false);
  const cleanupByTaskRef = useRef<Record<string, () => void>>({});
  const watchKeysByTaskRef = useRef<Record<string, number>>({});
  const prevTaskIdsKeyRef = useRef<string>("");

  const applyEvent = useCallback((next: TaskEvent) => {
    const previous = eventsRef.current[next.taskId] ?? null;
    if (!shouldAcceptTaskEventUpdate(previous, next)) {
      return;
    }
    const mergedEvent = preferTaskError(previous, next);
    if (previous && taskEventEquals(previous, mergedEvent)) {
      return;
    }
    const merged = { ...eventsRef.current, [next.taskId]: mergedEvent };
    eventsRef.current = merged;
    setEvents(merged);
    setError(null);

    const eventId = extractEventId(mergedEvent);
    if (eventId != null) {
      lastEventIdByTaskRef.current[next.taskId] = Math.max(
        lastEventIdByTaskRef.current[next.taskId] ?? 0,
        eventId,
      );
    }

    if (isTaskMilestone(previous, mergedEvent)) {
      onTaskMilestoneRef.current?.(mergedEvent, previous);
    }

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
      for (const cleanup of Object.values(cleanupByTaskRef.current)) {
        cleanup();
      }
      cleanupByTaskRef.current = {};
      watchKeysByTaskRef.current = {};
      const preservedTerminal: Record<string, TaskEvent> = {};
      for (const [taskId, event] of Object.entries(eventsRef.current)) {
        if (isTaskTerminalStatus(event.status)) {
          preservedTerminal[taskId] = event;
        }
      }
      eventsRef.current = preservedTerminal;
      setEvents(preservedTerminal);
      setModes((previous) => {
        const next: Record<string, TaskProgressMode> = {};
        for (const taskId of Object.keys(preservedTerminal)) {
          next[taskId] = previous[taskId] ?? "completed";
        }
        return next;
      });
      if (Object.keys(preservedTerminal).length === 0) {
        notifiedTerminalRef.current = new Set();
        allTerminalNotifiedRef.current = false;
      }
      setSseFailureCounts({});
      return;
    }

    let disposed = false;
    const isDisposed = () => disposed;

    if (prevTaskIdsKeyRef.current !== taskIdsKey) {
      prevTaskIdsKeyRef.current = taskIdsKey;
      for (const cleanup of Object.values(cleanupByTaskRef.current)) {
        cleanup();
      }
      cleanupByTaskRef.current = {};
      watchKeysByTaskRef.current = {};
      eventsRef.current = {};
      setEvents({});
      setModes({});
      notifiedTerminalRef.current = new Set();
      allTerminalNotifiedRef.current = false;
      setSseFailureCounts({});
    }

    const activeTaskIds = new Set(tasks.map((task) => task.taskId));
    for (const [taskId, cleanup] of Object.entries(cleanupByTaskRef.current)) {
      if (!activeTaskIds.has(taskId)) {
        cleanup();
        delete cleanupByTaskRef.current[taskId];
        delete watchKeysByTaskRef.current[taskId];
      }
    }

    for (const task of tasks) {
      const taskId = task.taskId;
      const watchKeyForTask = resolveTaskWatchKey(taskId, taskWatchKeys, watchKey);
      const existingEvent = eventsRef.current[taskId];
      if (
        existingEvent &&
        isTaskTerminalStatus(existingEvent.status) &&
        watchKeysByTaskRef.current[taskId] === watchKeyForTask &&
        cleanupByTaskRef.current[taskId]
      ) {
        continue;
      }

      if (
        watchKeysByTaskRef.current[taskId] === watchKeyForTask &&
        cleanupByTaskRef.current[taskId]
      ) {
        continue;
      }

      cleanupByTaskRef.current[taskId]?.();
      const previousWatchKey = watchKeysByTaskRef.current[taskId];
      if (previousWatchKey !== undefined && previousWatchKey !== watchKeyForTask) {
        notifiedTerminalRef.current.delete(taskId);
        allTerminalNotifiedRef.current = false;
      }
      watchKeysByTaskRef.current[taskId] = watchKeyForTask;
      cleanupByTaskRef.current[taskId] = startTaskWatch({
        taskId,
        applyEvent,
        setMode: () => {},
        setSseFailureCount: () => {},
        setError,
        isDisposed,
        setModes,
        setSseFailureCounts,
        initialAfterId: lastEventIdByTaskRef.current[taskId] ?? 0,
      });
    }

    return () => {
      disposed = true;
      for (const cleanup of Object.values(cleanupByTaskRef.current)) {
        cleanup();
      }
      cleanupByTaskRef.current = {};
    };
  }, [applyEvent, enabled, taskIdsKey, taskWatchKeys, watchKey]);

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
