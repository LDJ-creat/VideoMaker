import { normalizeMigrationSlotId } from "@/lib/migrationSlotId";
import { parseTaskMaterialProgress } from "@/lib/parseTaskMaterialProgress";

export type SlotMaterialActivity = {
  slotId: string;
  actionLabel: string;
};

export type ParallelMaterialActivity = {
  activeSlots: Map<string, SlotMaterialActivity>;
  completedSlots: Set<string>;
};

const COMPLETING_SLOT = /Completing slot\s+(\S+)/i;
const AUTHORING_HF =
  /Authoring HyperFrames material spec(?:\s+for\s+(\S+))?/i;
const HF_READY = /HyperFrames material ready for slot\s+(\S+)/i;
const FALLBACK_SLOT = /Fallback\s+\S+\s+for slot\s+(\S+)/i;

export const EMPTY_PARALLEL_MATERIAL_ACTIVITY: ParallelMaterialActivity = {
  activeSlots: new Map(),
  completedSlots: new Set(),
};

function slotKey(rawSlotId: string): string {
  return normalizeMigrationSlotId(rawSlotId) ?? rawSlotId;
}

export function reduceParallelMaterialActivity(
  state: ParallelMaterialActivity,
  message: string | undefined,
): ParallelMaterialActivity {
  if (!message) {
    return state;
  }

  const completing = message.match(COMPLETING_SLOT);
  if (completing?.[1]) {
    const rawSlotId = completing[1];
    const key = slotKey(rawSlotId);
    const activeSlots = new Map(state.activeSlots);
    activeSlots.set(key, { slotId: rawSlotId, actionLabel: "素材补全" });
    return { ...state, activeSlots };
  }

  const authoring = message.match(AUTHORING_HF);
  if (authoring) {
    const rawSlotId = authoring[1];
    if (!rawSlotId) {
      return state;
    }
    const key = slotKey(rawSlotId);
    const activeSlots = new Map(state.activeSlots);
    activeSlots.set(key, { slotId: rawSlotId, actionLabel: "HyperFrames 包装" });
    return { ...state, activeSlots };
  }

  const fallback = message.match(FALLBACK_SLOT);
  if (fallback?.[1]) {
    const rawSlotId = fallback[1];
    const key = slotKey(rawSlotId);
    const activeSlots = new Map(state.activeSlots);
    activeSlots.set(key, { slotId: rawSlotId, actionLabel: "降级补全" });
    return { ...state, activeSlots };
  }

  const hfReady = message.match(HF_READY);
  if (hfReady?.[1]) {
    const rawSlotId = hfReady[1];
    const key = slotKey(rawSlotId);
    const activeSlots = new Map(state.activeSlots);
    activeSlots.delete(key);
    const completedSlots = new Set(state.completedSlots);
    completedSlots.add(key);
    return { activeSlots, completedSlots };
  }

  return state;
}

export function reduceParallelMaterialActivityFromMessages(
  messages: Iterable<string | undefined>,
): ParallelMaterialActivity {
  let state = EMPTY_PARALLEL_MATERIAL_ACTIVITY;
  for (const message of messages) {
    state = reduceParallelMaterialActivity(state, message);
  }
  return state;
}

export function getActiveMaterialSlotIds(
  activity: ParallelMaterialActivity,
): Set<string> {
  return new Set(activity.activeSlots.keys());
}

export function shouldInferDiskCompletedSlots(
  progressGroup: import("@/features/structure-migration/generationMigrationStages").MigrationStageGroup,
): boolean {
  return progressGroup === "completing" || progressGroup === "done";
}

export function mergeCompletedMaterialSlotIds(
  activity: ParallelMaterialActivity,
  completedActionSlotIds: Set<string>,
  diskCompletedSlotIds?: Iterable<string>,
  options?: { includeDisk?: boolean },
): Set<string> {
  const merged = new Set(completedActionSlotIds);
  for (const slotId of activity.completedSlots) {
    merged.add(slotId);
  }
  if (options?.includeDisk !== false && diskCompletedSlotIds) {
    for (const slotId of diskCompletedSlotIds) {
      const normalized = normalizeMigrationSlotId(slotId) ?? slotId;
      merged.add(normalized);
    }
  }
  return merged;
}

export function reconcileMaterialSlotProgress(
  activity: ParallelMaterialActivity,
  completedSlotIds: Set<string>,
): ParallelMaterialActivity {
  const activeSlots = new Map(activity.activeSlots);
  for (const slotId of completedSlotIds) {
    const key = normalizeMigrationSlotId(slotId) ?? slotId;
    activeSlots.delete(key);
  }
  const completedSlots = new Set(activity.completedSlots);
  for (const slotId of completedSlotIds) {
    const key = normalizeMigrationSlotId(slotId) ?? slotId;
    completedSlots.add(key);
  }
  return { activeSlots, completedSlots };
}

export function buildParallelMaterialSummary(
  activity: ParallelMaterialActivity,
): string | null {
  const entries = [...activity.activeSlots.values()];
  if (entries.length === 0) {
    return null;
  }
  if (entries.length === 1) {
    const entry = entries[0]!;
    return `正在处理：${entry.slotId} · ${entry.actionLabel}`;
  }
  const slotLabels = entries.map((entry) => entry.slotId).join("、");
  return `并行处理 ${entries.length} 个槽位：${slotLabels}`;
}

export function buildCompletedMaterialSummary(
  activity: ParallelMaterialActivity,
): string | null {
  if (activity.completedSlots.size === 0) {
    return null;
  }
  const labels = [...activity.completedSlots]
    .map((slotId) => normalizeMigrationSlotId(slotId) ?? slotId)
    .join("、");
  return `已完成：${labels}`;
}

export function buildUnifiedMaterialProgressSummary(
  activity: ParallelMaterialActivity,
  latestMessage?: string,
): { primary: string | null; secondary: string | null } {
  const activeSummary = buildParallelMaterialSummary(activity);
  const completedSummary = buildCompletedMaterialSummary(activity);
  const latest = parseTaskMaterialProgress(latestMessage);

  const secondaryParts = [activeSummary, completedSummary].filter(Boolean);
  if (
    latest.kind === "completed" &&
    latest.summary &&
    !secondaryParts.some((part) => part?.includes(latest.slotId ?? ""))
  ) {
    secondaryParts.push(latest.summary);
  }

  const primary =
    latest.kind === "active"
      ? latest.summary
      : latest.kind === "completed" && !activeSummary
        ? latest.summary
        : null;

  return {
    primary,
    secondary: secondaryParts.length > 0 ? secondaryParts.join("；") : null,
  };
}
