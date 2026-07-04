import type { TaskEvent } from "@videomaker/contracts";
import type { Dispatch, SetStateAction } from "react";

import { getTask, getTaskEventsUrl } from "@/lib/apiClient";
import { recordDevProgressMetric } from "@/lib/devProgressMetrics";
import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";
import {
  POLL_INTERVAL_MS,
  SSE_ACTIVE_POLL_INTERVAL_MS,
  SSE_FAILURE_THRESHOLD,
} from "@/features/tasks/taskProgressConstants";

export type TaskWatchStopReason = "terminal" | "dispose" | "fallback";

export type StartTaskWatchOptions = {
  taskId: string;
  /** Returns true when the snapshot was applied to client state. */
  applyEvent: (event: TaskEvent) => boolean;
  setMode: Dispatch<SetStateAction<TaskProgressMode>>;
  setSseFailureCount: Dispatch<SetStateAction<number>>;
  setError: Dispatch<SetStateAction<string | null>>;
  isDisposed: () => boolean;
  /** Optional multi-task mode setter keyed by taskId. */
  setModes?: Dispatch<SetStateAction<Record<string, TaskProgressMode>>>;
  setSseFailureCounts?: Dispatch<SetStateAction<Record<string, number>>>;
  initialAfterId?: number;
};

function setTaskMode(
  taskId: string,
  mode: TaskProgressMode,
  setMode: Dispatch<SetStateAction<TaskProgressMode>>,
  setModes?: Dispatch<SetStateAction<Record<string, TaskProgressMode>>>,
): void {
  if (setModes) {
    setModes((prev) => ({ ...prev, [taskId]: mode }));
    return;
  }
  setMode(mode);
}

function incrementSseFailure(
  taskId: string,
  setSseFailureCount: Dispatch<SetStateAction<number>>,
  setSseFailureCounts?: Dispatch<SetStateAction<Record<string, number>>>,
): number {
  if (setSseFailureCounts) {
    let nextCount = 0;
    setSseFailureCounts((prev) => {
      nextCount = (prev[taskId] ?? 0) + 1;
      return { ...prev, [taskId]: nextCount };
    });
    return nextCount;
  }
  let nextCount = 0;
  setSseFailureCount((prev) => {
    nextCount = prev + 1;
    return nextCount;
  });
  return nextCount;
}

function resetSseFailure(
  taskId: string,
  setSseFailureCount: Dispatch<SetStateAction<number>>,
  setSseFailureCounts?: Dispatch<SetStateAction<Record<string, number>>>,
): void {
  if (setSseFailureCounts) {
    setSseFailureCounts((prev) => ({ ...prev, [taskId]: 0 }));
    return;
  }
  setSseFailureCount(0);
}

export function startTaskWatch({
  taskId,
  applyEvent,
  setMode,
  setSseFailureCount,
  setError,
  isDisposed,
  setModes,
  setSseFailureCounts,
  initialAfterId = 0,
}: StartTaskWatchOptions): () => void {
  let source: EventSource | undefined;
  let failures = 0;
  let pollTimer: ReturnType<typeof setInterval> | undefined;
  let fallbackPollTimer: ReturnType<typeof setInterval> | undefined;
  let taskStopped = false;
  let lastEventId = initialAfterId;
  let intentionalClose = false;

  const stopTaskWatch = (reason: TaskWatchStopReason = "dispose") => {
    if (taskStopped) return;
    taskStopped = true;
    if (reason === "terminal") {
      intentionalClose = true;
    }
    source?.close();
    source = undefined;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = undefined;
    }
    if (fallbackPollTimer) {
      clearInterval(fallbackPollTimer);
      fallbackPollTimer = undefined;
    }
    if (reason !== "dispose") {
      setTaskMode(taskId, "completed", setMode, setModes);
    }
  };

  const pollOnce = async () => {
    if (isDisposed() || taskStopped) return false;
    recordDevProgressMetric("taskPoll");
    try {
      const { data } = await getTask(taskId);
      const applied = applyEvent(data);
      if (isTaskTerminalStatus(data.status) && applied) {
        stopTaskWatch("terminal");
        return true;
      }
      return applied;
    } catch (err) {
      setError(err instanceof Error ? err.message : "轮询任务失败");
      return false;
    }
  };

  const switchToPolling = () => {
    if (isDisposed() || taskStopped) return;
    intentionalClose = true;
    source?.close();
    source = undefined;
    intentionalClose = false;
    if (fallbackPollTimer) {
      clearInterval(fallbackPollTimer);
      fallbackPollTimer = undefined;
    }
    setTaskMode(taskId, "polling", setMode, setModes);
    void pollOnce();
    pollTimer = setInterval(() => {
      void pollOnce();
    }, POLL_INTERVAL_MS);
  };

  const registerSseFailure = () => {
    if (taskStopped || intentionalClose) return;
    failures += 1;
    recordDevProgressMetric("sseReconnect");
    incrementSseFailure(taskId, setSseFailureCount, setSseFailureCounts);
    if (failures >= SSE_FAILURE_THRESHOLD) {
      switchToPolling();
    }
  };

  const openEventSource = () => {
    if (isDisposed() || taskStopped) return;
    source = new EventSource(getTaskEventsUrl(taskId, lastEventId));
    source.addEventListener("task", (message: MessageEvent) => {
      if (taskStopped) return;
      try {
        const parsed = JSON.parse(message.data as string) as TaskEvent & {
          eventId?: number;
        };
        if (typeof parsed.eventId === "number") {
          lastEventId = Math.max(lastEventId, parsed.eventId);
        }
        const applied = applyEvent(parsed);
        failures = 0;
        resetSseFailure(taskId, setSseFailureCount, setSseFailureCounts);
        if (isTaskTerminalStatus(parsed.status) && applied) {
          stopTaskWatch("terminal");
        }
      } catch {
        registerSseFailure();
      }
    });
    source.onerror = () => {
      if (intentionalClose) return;
      registerSseFailure();
    };
  };

  setTaskMode(taskId, "sse", setMode, setModes);

  void (async () => {
    await pollOnce();
    if (isDisposed() || taskStopped) return;

    openEventSource();

    fallbackPollTimer = setInterval(() => {
      void pollOnce();
    }, SSE_ACTIVE_POLL_INTERVAL_MS);
  })();

  return () => stopTaskWatch("dispose");
}
