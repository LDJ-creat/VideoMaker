import type {
  CompletionAction,
  GapReport,
  GenerationPlan,
  SlotMatch,
  StoryboardScene,
  VideoStructure,
} from "@videomaker/contracts";

import { structureSlotRoleLabel } from "@/lib/structureSlotLabels";

import { migrationStageGroup } from "@/features/structure-migration/generationMigrationStages";
import { pickVisualCompletionAction } from "@/features/structure-migration/pickVisualCompletionAction";
import { resolveStoryboardSceneMedia } from "@/features/master-narration/resolveStoryboardSceneMedia";

/** Mirrors worker slot_mapper thresholds. */
const MATCHED_THRESHOLD = 0.62;
const WEAK_THRESHOLD = 0.38;

export type SlotMigrationStatus =
  | "pending"
  | "mapping"
  | "planned"
  | "completing"
  | "resolved";

export type SlotMigrationRow = {
  slotId: string;
  role: string;
  roleLabel: string;
  visualIntent: string;
  scriptIntent: string;
  status: SlotMigrationStatus;
  userAssetId: string | null;
  userAssetSummary: string | null;
  gapSummary: string | null;
  completionProvider: string | null;
  completionStrategy: string | null;
  completionReason: string | null;
  resolvedVisual: string | null;
  script: string | null;
  timeRange: string | null;
};

function classifyMatch(match: SlotMatch | undefined): "matched" | "weak" | "none" {
  if (!match) return "none";
  const score = Number(match.matchScore ?? 0);
  if (score >= MATCHED_THRESHOLD) return "matched";
  if (score >= WEAK_THRESHOLD) return "weak";
  return "none";
}

function gapEntryForSlot(
  gapReport: GapReport | null | undefined,
  slotId: string,
): { reason: string; suggestedFixes: string[] } | null {
  if (!gapReport) return null;
  const weak = gapReport.weakSlots.find((entry) => entry.slotId === slotId);
  if (weak) {
    return { reason: weak.reason, suggestedFixes: weak.suggestedFixes };
  }
  const missing = gapReport.missingSlots.find((entry) => entry.slotId === slotId);
  if (missing) {
    return { reason: missing.reason, suggestedFixes: missing.suggestedFixes };
  }
  return null;
}

function resolveRowStatus(input: {
  mode: "result" | "progress";
  progressGroup?: ReturnType<typeof migrationStageGroup>;
  hasCompletion: boolean;
  hasGap: boolean;
  hasMatch: boolean;
  taskSucceeded?: boolean;
}): SlotMigrationStatus {
  if (input.mode === "result" || input.taskSucceeded) {
    return input.hasCompletion || input.hasMatch ? "resolved" : "planned";
  }
  switch (input.progressGroup) {
    case "pending":
      return "pending";
    case "mapping":
      return input.hasMatch || input.hasGap ? "mapping" : "pending";
    case "planning":
      return input.hasGap || input.hasCompletion ? "planned" : "mapping";
    case "completing":
      return input.hasCompletion || input.hasGap ? "completing" : "planned";
    case "done":
      return "resolved";
    default:
      return "pending";
  }
}

export function buildSlotMigrationRows(input: {
  structure: VideoStructure;
  gapReport?: GapReport | null;
  slotMatches?: SlotMatch[];
  completionActions?: CompletionAction[];
  storyboard?: StoryboardScene[];
  mode: "result" | "progress";
  progressGroup?: ReturnType<typeof migrationStageGroup>;
  taskSucceeded?: boolean;
}): SlotMigrationRow[] {
  const matchesBySlot = new Map(
    (input.slotMatches ?? input.gapReport?.slotMatches ?? []).map((match) => [
      match.slotId,
      match,
    ]),
  );
  const actionsBySlot = new Map<string, CompletionAction>();
  for (const action of input.completionActions ?? []) {
    if (
      action.provider === "tts" ||
      action.strategy === "tts"
    ) {
      continue;
    }
    if (!actionsBySlot.has(action.slotId)) {
      actionsBySlot.set(action.slotId, action);
    }
  }
  const scenesBySlot = new Map(
    (input.storyboard ?? []).map((scene) => [scene.slotId, scene]),
  );

  return input.structure.slots.map((slot) => {
    const match = matchesBySlot.get(slot.id);
    const matchClass = classifyMatch(match);
    const gap = gapEntryForSlot(input.gapReport ?? null, slot.id);
    const completion = actionsBySlot.get(slot.id);
    const scene = scenesBySlot.get(slot.id);

    const userAssetId =
      matchClass !== "none" && match?.assetId ? String(match.assetId) : null;
    const userAssetSummary =
      matchClass !== "none" && match?.matchReason
        ? match.matchReason
        : matchClass === "weak" && match?.matchReason
          ? match.matchReason
          : null;

    const gapSummary =
      gap?.reason ??
      (matchClass === "none" && match?.matchReason ? match.matchReason : null);

    return {
      slotId: slot.id,
      role: slot.role,
      roleLabel: structureSlotRoleLabel(slot.role),
      visualIntent: slot.visualIntent,
      scriptIntent: slot.scriptIntent,
      status: resolveRowStatus({
        mode: input.mode,
        progressGroup: input.progressGroup,
        hasCompletion: Boolean(completion),
        hasGap: Boolean(gap),
        hasMatch: matchClass !== "none",
        taskSucceeded: input.taskSucceeded,
      }),
      userAssetId,
      userAssetSummary,
      gapSummary,
      completionProvider:
        completion?.provider ??
        completion?.strategy ??
        gap?.suggestedFixes[0] ??
        null,
      completionStrategy: completion?.strategy ?? null,
      completionReason: completion?.reason ?? completion?.rationale ?? null,
      resolvedVisual: scene?.visual ?? null,
      script: scene?.script ?? null,
      timeRange:
        scene != null ? `${scene.startSec}–${scene.endSec}s` : null,
    };
  });
}

export function buildSlotMigrationRowsFromPlan(
  structure: VideoStructure,
  plan: GenerationPlan,
  gapReport?: GapReport | null,
): SlotMigrationRow[] {
  const rows = buildSlotMigrationRows({
    structure,
    gapReport: gapReport ?? null,
    slotMatches: gapReport?.slotMatches,
    completionActions: plan.completionActions,
    storyboard: plan.storyboard,
    mode: "result",
    taskSucceeded: true,
  });

  return rows.map((row) => {
    const scene = plan.storyboard.find((entry) => entry.slotId === row.slotId);
    if (!scene) return row;

    const media = resolveStoryboardSceneMedia(plan, scene);
    const visualAction = pickVisualCompletionAction(plan.completionActions, row.slotId);
    const visualProvider =
      media.provider && media.provider !== scene.source
        ? media.provider
        : visualAction?.provider ?? visualAction?.strategy ?? null;

    return {
      ...row,
      completionProvider: visualProvider,
      completionStrategy: visualAction?.strategy ?? null,
      completionReason:
        visualAction?.rationale ??
        visualAction?.reason ??
        row.gapSummary,
    };
  });
}

export function migrationSummaryFromRows(rows: SlotMigrationRow[]): string {
  const userReuse = rows.filter((row) => row.userAssetId).length;
  const autoCompleted = rows.filter(
    (row) => !row.userAssetId && row.completionProvider,
  ).length;
  const total = rows.length;
  if (total === 0) return "暂无结构槽位。";
  if (userReuse === 0 && autoCompleted === 0) {
    return `共 ${total} 个结构槽位，等待映射与补全。`;
  }
  const parts: string[] = [`共 ${total} 个结构槽位`];
  if (userReuse > 0) parts.push(`${userReuse} 个复用用户素材`);
  if (autoCompleted > 0) parts.push(`${autoCompleted} 个自动补全`);
  return `${parts.join("，")}。`;
}
