import type { TaskEvent, ToolError } from "@videomaker/contracts";

function isGenericGenerationFailure(error: ToolError | undefined): boolean {
  if (!error) return false;
  return (
    error.code === "generation_failed" ||
    error.message === "Worker task failed" ||
    error.message === "Generation failed"
  );
}

/** Keep specific material-stage errors when the pipeline emits a generic wrapper. */
export function preferTaskError(
  previous: TaskEvent | null,
  next: TaskEvent,
): TaskEvent {
  if (!previous?.error || !next.error) return next;
  if (
    next.status === "failed" &&
    isGenericGenerationFailure(next.error) &&
    !isGenericGenerationFailure(previous.error)
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
