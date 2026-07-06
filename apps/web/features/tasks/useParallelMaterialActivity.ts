"use client";

import type { TaskEvent } from "@videomaker/contracts";
import { useEffect, useRef, useState } from "react";

import { fetchTaskEventHistory } from "@/lib/apiClient";
import {
  EMPTY_PARALLEL_MATERIAL_ACTIVITY,
  type ParallelMaterialActivity,
  reduceParallelMaterialActivity,
  reduceParallelMaterialActivityFromMessages,
} from "@/lib/parallelMaterialActivity";
import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

type UseParallelMaterialActivityOptions = {
  /** Bump after cancel/retry to drop stale SSE-derived slot state for the same taskId. */
  resetKey?: number;
};

export function useParallelMaterialActivity(
  taskId: string | null | undefined,
  event: TaskEvent | null,
  options?: UseParallelMaterialActivityOptions,
): ParallelMaterialActivity {
  const resetKey = options?.resetKey ?? 0;
  const [activity, setActivity] = useState<ParallelMaterialActivity>(
    EMPTY_PARALLEL_MATERIAL_ACTIVITY,
  );
  const lastMessageRef = useRef<string | null>(null);
  const bootstrappedTaskIdRef = useRef<string | null>(null);
  const lastResetKeyRef = useRef(resetKey);

  useEffect(() => {
    if (!taskId) {
      bootstrappedTaskIdRef.current = null;
      lastResetKeyRef.current = resetKey;
      lastMessageRef.current = null;
      setActivity(EMPTY_PARALLEL_MATERIAL_ACTIVITY);
      return;
    }

    const isNewTask = bootstrappedTaskIdRef.current !== taskId;
    const isRetryReset = lastResetKeyRef.current !== resetKey;
    lastResetKeyRef.current = resetKey;

    if (!isNewTask && !isRetryReset) {
      return;
    }

    bootstrappedTaskIdRef.current = taskId;
    lastMessageRef.current = null;
    setActivity(EMPTY_PARALLEL_MATERIAL_ACTIVITY);

    let cancelled = false;
    void (async () => {
      try {
        const history = await fetchTaskEventHistory(taskId);
        if (cancelled) return;
        const messages = history.map((record) => record.message);
        setActivity(reduceParallelMaterialActivityFromMessages(messages));
        const latest = history.at(-1);
        lastMessageRef.current = latest?.message ?? null;
      } catch {
        // History bootstrap is best-effort; live SSE/polling still updates state.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [resetKey, taskId]);

  useEffect(() => {
    if (!taskId || !event || event.taskId !== taskId) {
      return;
    }
    if (event.message === lastMessageRef.current) {
      return;
    }
    lastMessageRef.current = event.message ?? null;
    setActivity((previous) =>
      reduceParallelMaterialActivity(previous, event.message),
    );
  }, [event?.message, event?.taskId, taskId]);

  useEffect(() => {
    if (event && isTaskTerminalStatus(event.status)) {
      setActivity(EMPTY_PARALLEL_MATERIAL_ACTIVITY);
      lastMessageRef.current = null;
    }
  }, [event?.status]);

  return activity;
}
