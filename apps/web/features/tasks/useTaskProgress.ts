"use client";

import type { TaskEvent } from "@videomaker/contracts";
import { useCallback, useEffect, useRef, useState } from "react";

import { getTask, getTaskEventsUrl } from "@/lib/apiClient";

const SSE_FAILURE_THRESHOLD = 3;
const POLL_INTERVAL_MS = 3000;

export type TaskProgressMode = "sse" | "polling" | "idle";

export type UseTaskProgressOptions = {
  apiBaseUrl: string;
  taskId: string | null;
  enabled?: boolean;
};

export type UseTaskProgressResult = {
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
};

export function useTaskProgress({
  apiBaseUrl,
  taskId,
  enabled = true,
}: UseTaskProgressOptions): UseTaskProgressResult {
  const [event, setEvent] = useState<TaskEvent | null>(null);
  const [mode, setMode] = useState<TaskProgressMode>("idle");
  const [sseFailureCount, setSseFailureCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const failuresRef = useRef(0);

  const applyEvent = useCallback((next: TaskEvent) => {
    setEvent(next);
    setError(null);
  }, []);

  const pollOnce = useCallback(async () => {
    if (!taskId) return;
    try {
      const task = await getTask(apiBaseUrl, taskId);
      applyEvent(task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "轮询任务失败");
    }
  }, [apiBaseUrl, applyEvent, taskId]);

  useEffect(() => {
    if (!enabled || !taskId) {
      setMode("idle");
      return;
    }

    failuresRef.current = 0;
    setSseFailureCount(0);
    setMode("sse");

    let disposed = false;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    const source = new EventSource(getTaskEventsUrl(apiBaseUrl, taskId));

    const switchToPolling = () => {
      if (disposed) return;
      source.close();
      setMode("polling");
      void pollOnce();
      pollTimer = setInterval(() => {
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

    source.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data) as TaskEvent;
        applyEvent(parsed);
        failuresRef.current = 0;
        setSseFailureCount(0);
      } catch {
        registerSseFailure();
      }
    };

    source.onerror = () => {
      registerSseFailure();
    };

    return () => {
      disposed = true;
      source.close();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [apiBaseUrl, applyEvent, enabled, pollOnce, taskId]);

  return { event, mode, sseFailureCount, error };
}
