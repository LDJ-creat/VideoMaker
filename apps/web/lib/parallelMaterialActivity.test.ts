import { describe, expect, it } from "vitest";

import {
  EMPTY_PARALLEL_MATERIAL_ACTIVITY,
  buildParallelMaterialSummary,
  buildUnifiedMaterialProgressSummary,
  inferPostMaterialPipelineHint,
  mergeCompletedMaterialSlotIds,
  reconcileMaterialSlotProgress,
  reduceParallelMaterialActivity,
  reduceParallelMaterialActivityFromMessages,
  shouldInferDiskCompletedSlots,
} from "@/lib/parallelMaterialActivity";

describe("parallelMaterialActivity", () => {
  it("tracks multiple completing slots in parallel", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-1",
      "Completing slot slot-2",
      "Completing slot slot-3",
    ]);

    expect(activity.activeSlots.size).toBe(3);
    expect(buildParallelMaterialSummary(activity)).toBe(
      "并行处理 3 个槽位：slot-1、slot-2、slot-3",
    );
  });

  it("normalizes finish suffixes to the same structure slot", () => {
    let activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-1",
    ]);
    activity = reduceParallelMaterialActivity(
      activity,
      "Completing slot slot-1-finish",
    );

    expect(activity.activeSlots.size).toBe(1);
    expect(activity.activeSlots.get("slot-1")?.slotId).toBe("slot-1-finish");
    expect(activity.activeSlots.get("slot-1")?.actionLabel).toBe("素材补全");
  });

  it("marks slots completed after HyperFrames material ready", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-2",
      "Completing slot slot-3",
      "HyperFrames material ready for slot slot-2",
    ]);

    expect(activity.activeSlots.has("slot-2")).toBe(false);
    expect(activity.activeSlots.has("slot-3")).toBe(true);
    expect(activity.completedSlots.has("slot-2")).toBe(true);
    expect(buildParallelMaterialSummary(activity)).toBe(
      "正在处理：slot-3 · 素材补全",
    );
  });

  it("merges activity-completed slots with material-state ids", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "HyperFrames material ready for slot slot-1",
    ]);
    const merged = mergeCompletedMaterialSlotIds(
      activity,
      new Set(["slot-cta"]),
      ["slot-disk"],
      { includeDisk: true },
    );
    expect([...merged].sort()).toEqual(["slot-1", "slot-cta", "slot-disk"]);
  });

  it("skips disk-completed slots before material stage", () => {
    const merged = mergeCompletedMaterialSlotIds(
      EMPTY_PARALLEL_MATERIAL_ACTIVITY,
      new Set<string>(),
      ["slot-1", "slot-2"],
      { includeDisk: false },
    );
    expect([...merged]).toEqual([]);
  });

  it("drops active slots that are already completed on disk", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-1",
      "Completing slot slot-2",
      "Completing slot slot-3",
    ]);
    const resolved = reconcileMaterialSlotProgress(
      activity,
      new Set(["slot-1", "slot-2"]),
    );
    expect(resolved.activeSlots.has("slot-1")).toBe(false);
    expect(resolved.activeSlots.has("slot-2")).toBe(false);
    expect(resolved.activeSlots.has("slot-3")).toBe(true);
  });

  it("only infers disk completion during material/render stages", () => {
    expect(shouldInferDiskCompletedSlots("mapping")).toBe(false);
    expect(shouldInferDiskCompletedSlots("completing")).toBe(true);
    expect(shouldInferDiskCompletedSlots("done")).toBe(true);
  });

  it("builds unified summary with active and completed slots", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-1",
      "Completing slot slot-2",
      "Completing slot slot-3",
      "HyperFrames material ready for slot slot-1",
    ]);
    const summary = buildUnifiedMaterialProgressSummary(
      activity,
      "HyperFrames material ready for slot slot-1",
    );
    expect(summary.secondary).toContain("并行处理");
    expect(summary.secondary).toContain("已完成：slot-1");
  });

  it("shows post-material pipeline hint when slots done but stage still material", () => {
    const activity = reduceParallelMaterialActivity(
      EMPTY_PARALLEL_MATERIAL_ACTIVITY,
      "HyperFrames material ready for slot slot-6",
    );
    const hint = inferPostMaterialPipelineHint(
      activity,
      "rendering_material",
      "running",
    );
    expect(hint).toContain("合成完整视频");
  });
});
