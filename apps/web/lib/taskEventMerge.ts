import type { TaskEvent, TaskStatus, ToolError } from "@videomaker/contracts";

import { isTaskTerminalStatus } from "@/lib/taskStatusLabels";

function toolErrorEquals(
  left: ToolError | undefined,
  right: ToolError | undefined,
): boolean {
  if (!left && !right) return true;
  if (!left || !right) return false;
  return left.code === right.code && left.message === right.message;
}

/** Semantic equality for task progress snapshots (ignores artifactRefs churn). */
export function taskEventEquals(left: TaskEvent, right: TaskEvent): boolean {
  return (
    left.taskId === right.taskId &&
    left.status === right.status &&
    left.stage === right.stage &&
    left.progress === right.progress &&
    left.message === right.message &&
    left.updatedAt === right.updatedAt &&
    toolErrorEquals(left.error, right.error)
  );
}

/** Patch settled events only when at least one task snapshot changed. */
export function mergeTaskEventsIfChanged(
  previous: Record<string, TaskEvent>,
  patch: Record<string, TaskEvent>,
): Record<string, TaskEvent> | null {
  let changed = false;
  const merged = { ...previous };
  for (const [taskId, event] of Object.entries(patch)) {
    const existing = merged[taskId];
    if (existing && taskEventEquals(existing, event)) {
      continue;
    }
    merged[taskId] = event;
    changed = true;
  }
  return changed ? merged : null;
}

/** Merge settled + live task events; newer updatedAt wins per taskId. */
export function mergeTaskEvents(
  settled: Record<string, TaskEvent>,
  live: Record<string, TaskEvent>,
): Record<string, TaskEvent> {
  const merged: Record<string, TaskEvent> = { ...settled };
  for (const [taskId, event] of Object.entries(live)) {
    const existing = merged[taskId];
    if (!existing) {
      merged[taskId] = event;
      continue;
    }
    const eventTime = new Date(event.updatedAt).getTime();
    const existingTime = new Date(existing.updatedAt).getTime();
    const newer = eventTime >= existingTime ? event : existing;
    const older = newer === event ? existing : event;
    merged[taskId] = preferTaskError(older, newer);
  }
  return merged;
}

function isGenericGenerationFailure(error: ToolError | undefined): boolean {
  if (!error) return false;
  return (
    error.code === "generation_failed" ||
    error.message === "Worker task failed" ||
    error.message === "Generation failed"
  );
}

/** Generic wrapper events should only inherit a specific error from the same crash cascade. */
const GENERIC_ERROR_INHERIT_MAX_MS = 60_000;

function shouldInheritSpecificError(previous: TaskEvent, next: TaskEvent): boolean {
  if (previous.status !== "failed" || !previous.error) return false;
  if (isGenericGenerationFailure(previous.error)) return false;
  const gapMs =
    new Date(next.updatedAt).getTime() - new Date(previous.updatedAt).getTime();
  return gapMs >= 0 && gapMs <= GENERIC_ERROR_INHERIT_MAX_MS;
}

const ACTIVE_TASK_STATUSES = new Set<TaskStatus>([
  "running",
  "retrying",
  "queued",
  "awaiting_review",
]);

function withoutTaskError(event: TaskEvent): TaskEvent {
  if (!event.error) return event;
  const { error: _removed, ...rest } = event;
  return rest as TaskEvent;
}

/** Terminal events may arrive with slightly older timestamps than the last running tick. */
const STALE_TERMINAL_GRACE_MS = 5_000;

/** Ignore stale snapshots that would rewind live progress (except near-simultaneous terminal failures). */
export function shouldAcceptTaskEventUpdate(
  previous: TaskEvent | null,
  next: TaskEvent,
): boolean {
  if (!previous) return true;
  const nextTime = new Date(next.updatedAt).getTime();
  const previousTime = new Date(previous.updatedAt).getTime();
  if (nextTime >= previousTime) return true;
  const gapMs = previousTime - nextTime;
  return (
    isTaskTerminalStatus(next.status) &&
    !isTaskTerminalStatus(previous.status) &&
    gapMs <= STALE_TERMINAL_GRACE_MS
  );
}

/** Keep specific material-stage errors when the pipeline emits a generic wrapper. */
export function preferTaskError(
  previous: TaskEvent | null,
  next: TaskEvent,
): TaskEvent {
  if (ACTIVE_TASK_STATUSES.has(next.status)) {
    return withoutTaskError(next);
  }
  if (!previous?.error || !next.error) return next;
  if (
    next.status === "failed" &&
    isGenericGenerationFailure(next.error) &&
    shouldInheritSpecificError(previous, next)
  ) {
    return {
      ...next,
      error: previous.error,
      stage: previous.stage,
      message: previous.message,
    };
  }
  return next;
}
