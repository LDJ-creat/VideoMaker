import type { TaskEvent, TaskStatus } from "@videomaker/contracts";

export type TaskEventWithId = TaskEvent & { eventId?: number };

export function extractEventId(event: TaskEvent): number | undefined {
  const withId = event as TaskEventWithId;
  return typeof withId.eventId === "number" ? withId.eventId : undefined;
}

/** True when status or stage changed; ignores first snapshot unless allowInitial. */
export function isTaskMilestone(
  previous: TaskEvent | null,
  next: TaskEvent,
  options?: { allowInitial?: boolean },
): boolean {
  if (!previous) return options?.allowInitial === true;
  if (previous.status !== next.status) return true;
  if (previous.stage !== next.stage) return true;
  return false;
}

export function isReviewMilestone(event: TaskEvent): boolean {
  return event.status === "awaiting_review";
}

export function applyTaskStatusOverride(
  event: TaskEvent,
  override?: TaskStatus,
): TaskEvent {
  if (!override || override === event.status) return event;
  return { ...event, status: override };
}

/** Review gate considering optimistic status overrides (e.g. after approve). */
export function isEffectiveReviewMilestone(
  event: TaskEvent | null | undefined,
  override?: TaskStatus,
): boolean {
  if (!event) return false;
  const status = override ?? event.status;
  if (status === "retrying" || status === "running") return false;
  return status === "awaiting_review";
}
