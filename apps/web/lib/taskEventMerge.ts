import type { TaskEvent, ToolError } from "@videomaker/contracts";

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

/** Keep specific material-stage errors when the pipeline emits a generic wrapper. */
export function preferTaskError(
  previous: TaskEvent | null,
  next: TaskEvent,
): TaskEvent {
  if (
    next.status === "running" ||
    next.status === "retrying" ||
    next.status === "queued" ||
    next.status === "awaiting_review"
  ) {
    return next;
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
