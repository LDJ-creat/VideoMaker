"use client";

import type { TaskEvent, TaskStage } from "@videomaker/contracts";
import { useEffect, useRef, useState } from "react";

/** Server-reported progress band for direct multimodal model invocation. */
export const MODEL_CALL_SMOOTH_MIN = 55;
export const MODEL_CALL_SMOOTH_MAX = 72;
/** UI-only ceiling until the worker reports validation (>=72). */
export const MODEL_CALL_SMOOTH_CAP = 71;

const MODEL_CALL_STAGES = new Set<TaskStage>([
  "extracting_structure_direct",
  "running_agent",
]);

/** ~0.08% every 500ms → about 100s from 55 to 71. */
export const MODEL_CALL_SMOOTH_STEP = 0.08;
export const MODEL_CALL_SMOOTH_INTERVAL_MS = 500;

export function shouldSmoothModelCallProgress(event: TaskEvent | null): boolean {
  if (!event) return false;
  if (event.status !== "running") return false;
  if (!MODEL_CALL_STAGES.has(event.stage)) return false;
  return (
    event.progress >= MODEL_CALL_SMOOTH_MIN &&
    event.progress < MODEL_CALL_SMOOTH_MAX
  );
}

export function nextSmoothedModelCallProgress(
  current: number,
  realProgress: number,
  step: number = MODEL_CALL_SMOOTH_STEP,
): number {
  const floor = Math.max(current, realProgress);
  if (floor >= MODEL_CALL_SMOOTH_CAP) {
    return MODEL_CALL_SMOOTH_CAP;
  }
  return Math.min(MODEL_CALL_SMOOTH_CAP, floor + step);
}

export function useSmoothedModelCallProgress(event: TaskEvent | null): number {
  const realProgress = event?.progress ?? 0;
  const realProgressRef = useRef(realProgress);
  realProgressRef.current = realProgress;
  const [displayProgress, setDisplayProgress] = useState(realProgress);
  const smoothing = shouldSmoothModelCallProgress(event);

  useEffect(() => {
    if (!event) {
      setDisplayProgress(0);
      return;
    }

    if (!shouldSmoothModelCallProgress(event)) {
      setDisplayProgress(event.progress);
      return;
    }

    setDisplayProgress((current) => Math.max(current, event.progress));

    const timer = window.setInterval(() => {
      setDisplayProgress((current) =>
        nextSmoothedModelCallProgress(current, realProgressRef.current),
      );
    }, MODEL_CALL_SMOOTH_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [event?.taskId, event?.stage, event?.status, event?.progress, event]);

  if (!smoothing) {
    return realProgress;
  }

  return Math.round(displayProgress * 10) / 10;
}
