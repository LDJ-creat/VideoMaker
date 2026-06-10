"use client";

import type { TaskEvent, TaskStatus } from "@videomaker/contracts";
import { useCallback, useEffect, useRef, useState } from "react";

import { getTask, getTaskEventsUrl } from "@/lib/apiClient";
import {
  preferTaskError,
  shouldAcceptTaskEventUpdate,
  taskEventEquals,
} from "@/lib/taskEventMerge";

const SSE_FAILURE_THRESHOLD = 3;
const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES: TaskStatus[] = [
  "succeeded",
  "failed",
  "cancelled",
];

export type TaskProgressMode = "sse" | "polling" | "idle" | "completed";

export type UseTaskProgressOptions = {
  taskId: string | null;
  enabled?: boolean;
  /** Bump to re-subscribe after retrying a terminal task. */
  watchKey?: number;
  onTerminal?: (event: TaskEvent) => void;
};

export type UseTaskProgressResult = {
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
};

function isTerminal(status: TaskStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function useTaskProgress({
  taskId,
  enabled = true,
  watchKey = 0,
  onTerminal,
}: UseTaskProgressOptions): UseTaskProgressResult {
  const [event, setEvent] = useState<TaskEvent | null>(null);
  const [mode, setMode] = useState<TaskProgressMode>("idle");
  const [sseFailureCount, setSseFailureCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const failuresRef = useRef(0);
  const onTerminalRef = useRef(onTerminal);
  onTerminalRef.current = onTerminal;

  const cleanupRef = useRef<{
    source?: EventSource;
    pollTimer?: ReturnType<typeof setInterval>;
    disposed: boolean;
  }>({ disposed: false });

  const stopAll = useCallback(() => {
    const state = cleanupRef.current;
    state.disposed = true;
    state.source?.close();
    state.source = undefined;
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = undefined;
    }
  }, []);

  const handleTerminal = useCallback(
    (next: TaskEvent) => {
      if (!isTerminal(next.status)) return;
      stopAll();
      setMode("completed");
      onTerminalRef.current?.(next);
    },
    [stopAll],
  );

  const applyEvent = useCallback(
    (next: TaskEvent) => {
      setEvent((previous) => {
        if (!shouldAcceptTaskEventUpdate(previous, next)) {
          return previous;
        }
        const merged = preferTaskError(previous, next);
        if (previous && taskEventEquals(previous, merged)) {
          return previous;
        }
        return merged;
      });
      setError(null);
      handleTerminal(next);
    },
    [handleTerminal],
  );

  const pollOnce = useCallback(async () => {
    if (!taskId || cleanupRef.current.disposed) return;
    try {
      const { data: task } = await getTask(taskId);
      applyEvent(task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "轮询任务失败");
    }
  }, [applyEvent, taskId]);

  useEffect(() => {
    if (!enabled || !taskId) {
      stopAll();
      cleanupRef.current.disposed = false;
      setEvent(null);
      setMode("idle");
      return;
    }

    cleanupRef.current = { disposed: false };
    failuresRef.current = 0;
    setSseFailureCount(0);
    setMode("sse");
    setEvent((previous) => {
      if (previous && isTerminal(previous.status)) {
        return null;
      }
      return previous;
    });
    void pollOnce();

    const source = new EventSource(getTaskEventsUrl(taskId));
    cleanupRef.current.source = source;

    const switchToPolling = () => {
      if (cleanupRef.current.disposed) return;
      source.close();
      cleanupRef.current.source = undefined;
      setMode("polling");
      void pollOnce();
      cleanupRef.current.pollTimer = setInterval(() => {
        void pollOnce();
      }, POLL_INTERVAL_MS);
    };

    const registerSseFailure = () => {
      failuresRef.current += 1;
      const count = failuresRef.current;
      setSseFailureCount(count);
      if (count >= SSE_FAILURE_THRESHOLD) {
        switchToPolling();
      }
    };

    const handleTaskEvent = (message: MessageEvent) => {
      try {
        const parsed = JSON.parse(message.data as string) as TaskEvent;
        applyEvent(parsed);
        failuresRef.current = 0;
        setSseFailureCount(0);
      } catch {
        registerSseFailure();
      }
    };

    source.addEventListener("task", handleTaskEvent);
    source.onerror = () => {
      registerSseFailure();
    };

    return () => {
      stopAll();
      cleanupRef.current.disposed = false;
    };
  }, [applyEvent, enabled, pollOnce, stopAll, taskId, watchKey]);

  return { event, mode, sseFailureCount, error };
}
