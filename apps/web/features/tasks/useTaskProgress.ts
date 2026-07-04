"use client";

import type { TaskEvent } from "@videomaker/contracts";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  preferTaskError,
  shouldAcceptTaskEventUpdate,
  taskEventEquals,
} from "@/lib/taskEventMerge";
import { extractEventId, isTaskMilestone } from "@/lib/taskMilestones";
import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

import { startTaskWatch } from "@/features/tasks/startTaskWatch";

export type TaskProgressMode = "sse" | "polling" | "idle" | "completed";

export type UseTaskProgressOptions = {
  taskId: string | null;
  enabled?: boolean;
  /** Bump to re-subscribe after retrying a terminal task. */
  watchKey?: number;
  onTerminal?: (event: TaskEvent) => void;
  onMilestone?: (event: TaskEvent, previous: TaskEvent | null) => void;
};

export type UseTaskProgressResult = {
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
};

export function useTaskProgress({
  taskId,
  enabled = true,
  watchKey = 0,
  onTerminal,
  onMilestone,
}: UseTaskProgressOptions): UseTaskProgressResult {
  const [event, setEvent] = useState<TaskEvent | null>(null);
  const [mode, setMode] = useState<TaskProgressMode>("idle");
  const [sseFailureCount, setSseFailureCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const eventRef = useRef<TaskEvent | null>(null);
  const lastEventIdRef = useRef(0);
  const onTerminalRef = useRef(onTerminal);
  const onMilestoneRef = useRef(onMilestone);
  onTerminalRef.current = onTerminal;
  onMilestoneRef.current = onMilestone;

  const applyEvent = useCallback((next: TaskEvent): boolean => {
    const previous = eventRef.current;
    if (!shouldAcceptTaskEventUpdate(previous, next)) {
      return false;
    }
    const merged = preferTaskError(previous, next);
    if (previous && taskEventEquals(previous, merged)) {
      return false;
    }
    eventRef.current = merged;
    setEvent(merged);
    setError(null);

    const eventId = extractEventId(merged);
    if (eventId != null) {
      lastEventIdRef.current = Math.max(lastEventIdRef.current, eventId);
    }

    if (isTaskMilestone(previous, merged)) {
      onMilestoneRef.current?.(merged, previous);
    }

    if (
      isTaskTerminalStatus(merged.status) &&
      (!previous || !isTaskTerminalStatus(previous.status))
    ) {
      onTerminalRef.current?.(merged);
    }
    return true;
  }, []);

  const prevWatchKeyRef = useRef(watchKey);

  useEffect(() => {
    if (!enabled || !taskId) {
      eventRef.current = null;
      lastEventIdRef.current = 0;
      prevWatchKeyRef.current = watchKey;
      setEvent(null);
      setMode("idle");
      setSseFailureCount(0);
      return;
    }

    if (prevWatchKeyRef.current !== watchKey) {
      prevWatchKeyRef.current = watchKey;
      eventRef.current = null;
      lastEventIdRef.current = 0;
      setEvent(null);
    } else {
      setEvent((previous) => {
        if (previous && isTaskTerminalStatus(previous.status)) {
          eventRef.current = null;
          lastEventIdRef.current = 0;
          return null;
        }
        eventRef.current = previous;
        return previous;
      });
    }

    setSseFailureCount(0);

    let disposed = false;
    const cleanup = startTaskWatch({
      taskId,
      applyEvent,
      setMode,
      setSseFailureCount,
      setError,
      isDisposed: () => disposed,
      initialAfterId: lastEventIdRef.current,
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, [applyEvent, enabled, taskId, watchKey]);

  return { event, mode, sseFailureCount, error };
}
