import type { TaskEvent, TaskStatus } from "@videomaker/contracts";

import type { WorkbenchPanel } from "@/features/workbench/workbenchTypes";
import {
  applyTaskStatusOverride,
  isEffectiveReviewMilestone,
  isReviewMilestone,
} from "@/lib/taskMilestones";

export const OUTPUT_RESULT_PANELS: WorkbenchPanel[] = ["narration", "result"];

export type LastPipelineAction = "analysis" | "generation" | "revise" | null;

export type NavIntent =
  | { type: "go_progress"; reason: string }
  | { type: "go_script_review"; reason: string }
  | { type: "go_analysis"; sampleId: string; reason: string }
  | { type: "go_result"; reason: string; reloadFailed?: boolean };

export type PipelineNavigationInput = {
  lastAction: LastPipelineAction;
  panel: WorkbenchPanel;
  autoNavEnabled: boolean;
  displayGenerationEvents: Record<string, TaskEvent>;
  activeGenerationTaskIds: string[];
  allGenerationTasksSucceeded: boolean;
  anyGenerationTaskFailed: boolean;
  anyGenerationAwaitingReview: boolean;
  singleTaskEvent: TaskEvent | null;
  sampleId: string | null;
  isBatchAnalysis: boolean;
};

export function buildGenerationSettlementKey(
  events: Record<string, TaskEvent>,
): string {
  return Object.entries(events)
    .map(
      ([taskId, entry]) =>
        `${taskId}:${entry.status}:${entry.stage ?? ""}:${entry.updatedAt ?? ""}`,
    )
    .sort()
    .join("|");
}

export function anyGenerationTaskFailedFromEvents(
  events: Record<string, TaskEvent>,
  taskIds: string[],
): boolean {
  return taskIds.some((taskId) => {
    const status = events[taskId]?.status;
    return status === "failed" || status === "cancelled";
  });
}

export function anyGenerationAwaitingReviewFromEvents(
  events: Record<string, TaskEvent>,
  taskIds: string[],
  statusOverrides?: Record<string, TaskStatus>,
): boolean {
  return taskIds.some((taskId) => {
    const event = events[taskId];
    return isEffectiveReviewMilestone(event, statusOverrides?.[taskId]);
  });
}

export function mergeGenerationEventsWithOverrides(
  events: Record<string, TaskEvent>,
  statusOverrides: Record<string, TaskStatus>,
): Record<string, TaskEvent> {
  const merged: Record<string, TaskEvent> = { ...events };
  for (const [taskId, override] of Object.entries(statusOverrides)) {
    const existing = merged[taskId];
    if (existing) {
      merged[taskId] = applyTaskStatusOverride(existing, override);
    }
  }
  return merged;
}

/** Milestone-driven navigation for a single generation task event. */
export function computeGenerationMilestoneIntent(
  event: TaskEvent,
  input: Pick<
    PipelineNavigationInput,
    "lastAction" | "panel" | "autoNavEnabled"
  >,
): NavIntent | null {
  if (!input.autoNavEnabled || input.lastAction !== "generation") {
    return null;
  }
  if (OUTPUT_RESULT_PANELS.includes(input.panel)) {
    return null;
  }

  if (event.status === "retrying" || event.status === "running") {
    if (input.panel === "script-review") {
      return { type: "go_progress", reason: "milestone:resumed-after-review" };
    }
    return null;
  }

  if (event.status === "awaiting_review" || isReviewMilestone(event)) {
    return { type: "go_script_review", reason: "milestone:awaiting-review" };
  }

  return null;
}

/** Settlement navigation after all generation tasks reach terminal status. */
export function computeGenerationSettlementIntent(
  input: PipelineNavigationInput & {
    reloadSucceeded: boolean;
    hydrateAwaitingReview: boolean;
    hydrateRunning: boolean;
    hydrateAllSucceeded: boolean;
  },
): NavIntent | null {
  if (!input.autoNavEnabled || input.lastAction !== "generation") {
    return null;
  }
  if (OUTPUT_RESULT_PANELS.includes(input.panel)) {
    return null;
  }

  if (input.anyGenerationTaskFailed) {
    return { type: "go_progress", reason: "generation-settlement:failed" };
  }

  if (input.hydrateAwaitingReview || input.anyGenerationAwaitingReview) {
    if (!input.allGenerationTasksSucceeded) {
      return { type: "go_script_review", reason: "generation-settlement:awaiting-review" };
    }
  }

  if (input.hydrateRunning && !input.allGenerationTasksSucceeded) {
    return { type: "go_progress", reason: "generation-settlement:running" };
  }

  if (
    input.allGenerationTasksSucceeded &&
    (input.reloadSucceeded || input.hydrateAllSucceeded)
  ) {
    return {
      type: "go_result",
      reason: input.reloadSucceeded
        ? "generation-settlement:reloaded"
        : "generation-settlement:all-succeeded",
      reloadFailed: !input.reloadSucceeded,
    };
  }

  if (input.allGenerationTasksSucceeded && !input.reloadSucceeded) {
    return {
      type: "go_result",
      reason: "generation-settlement:reload-pending",
      reloadFailed: true,
    };
  }

  return null;
}

/** Analysis pipeline completion navigation. */
export function computeAnalysisCompletionIntent(
  input: Pick<
    PipelineNavigationInput,
    "lastAction" | "panel" | "autoNavEnabled" | "sampleId" | "isBatchAnalysis"
  > & { eventStatus: TaskEvent["status"] | null },
): NavIntent | null {
  if (!input.autoNavEnabled || input.lastAction !== "analysis") {
    return null;
  }
  if (input.isBatchAnalysis || !input.sampleId) {
    return null;
  }
  if (input.eventStatus !== "succeeded") {
    return null;
  }
  if (OUTPUT_RESULT_PANELS.includes(input.panel)) {
    return null;
  }
  return {
    type: "go_analysis",
    sampleId: input.sampleId,
    reason: "analysis-terminal:succeeded",
  };
}

export function applyNavIntent(
  intent: NavIntent,
  setPanel: (panel: WorkbenchPanel, reason?: string) => void,
): WorkbenchPanel {
  switch (intent.type) {
    case "go_progress":
      setPanel("progress", intent.reason);
      return "progress";
    case "go_script_review":
      setPanel("script-review", intent.reason);
      return "script-review";
    case "go_analysis":
      setPanel("analysis", intent.reason);
      return "analysis";
    case "go_result":
      setPanel("result", intent.reason);
      return "result";
    default:
      return "progress";
  }
}
