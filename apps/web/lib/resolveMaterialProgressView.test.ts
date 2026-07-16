import { describe, expect, it } from "vitest";

import {
  EMPTY_PARALLEL_MATERIAL_ACTIVITY,
  reduceParallelMaterialActivityFromMessages,
} from "@/lib/parallelMaterialActivity";
import { resolveMaterialProgressView } from "@/lib/resolveMaterialProgressView";

describe("resolveMaterialProgressView", () => {
  it("shows gate slot regen immediately before worker SSE and fresh snapshot", () => {
    const activity = EMPTY_PARALLEL_MATERIAL_ACTIVITY;
    const view = resolveMaterialProgressView({
      materialActivity: activity,
      regeneratingSlotIds: ["slot-2"],
      completionActions: [
        {
          id: "action-slot-2",
          slotId: "slot-2",
          provider: "hyperframes_material",
          strategy: "hyperframes_material",
          reason: "fill",
          outputRef: "x",
        },
      ],
      completedActionIds: ["action-slot-1", "action-slot-2"],
      diskCompletedSlotIds: ["slot-1", "slot-2", "slot-3"],
      progressGroup: "completing",
    });

    expect(view.activeSlotIds.has("slot-2")).toBe(true);
    expect(view.completedSlotIds.has("slot-2")).toBe(false);
    expect(view.completedSlotIds.has("slot-1")).toBe(true);
    expect(view.completedSlotIds.has("slot-3")).toBe(true);
  });

  it("prefers live SSE activity over optimistic regen seed", () => {
    const activity = reduceParallelMaterialActivityFromMessages([
      "Completing slot slot-2",
    ]);
    const view = resolveMaterialProgressView({
      materialActivity: activity,
      regeneratingSlotIds: ["slot-2"],
      completionActions: [],
      diskCompletedSlotIds: ["slot-2"],
      progressGroup: "completing",
    });

    expect(view.activeSlotIds.has("slot-2")).toBe(true);
    expect(view.completedSlotIds.has("slot-2")).toBe(false);
  });
});
