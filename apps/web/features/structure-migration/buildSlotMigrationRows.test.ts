import { describe, expect, it } from "vitest";

import {
  buildSlotMigrationRows,
  buildSlotMigrationRowsFromPlan,
  migrationSummaryFromRows,
} from "@/features/structure-migration/buildSlotMigrationRows";
import {
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureVideoStructure,
} from "@/fixtures";
import type { CompletionAction } from "@videomaker/contracts";

describe("buildSlotMigrationRows", () => {
  it("ignores per-scene TTS actions when resolving visual completion", () => {
    const ttsAction: CompletionAction = {
      id: "action-slot-hook-visual-tts",
      slotId: "slot-hook-visual",
      strategy: "tts",
      provider: "tts",
      reason: "分镜口播合成",
      outputRef: "completion://slot-hook-visual/tts",
    };
    const rows = buildSlotMigrationRows({
      structure: fixtureVideoStructure,
      gapReport: fixtureGapReport,
      completionActions: [...fixtureGenerationPlan.completionActions, ttsAction],
      storyboard: fixtureGenerationPlan.storyboard,
      mode: "result",
      taskSucceeded: true,
    });
    const hookRow = rows.find((row) => row.slotId === "slot-hook-visual");
    expect(hookRow?.completionProvider).not.toBe("tts");
  });

  it("builds per-slot migration rows for result view", () => {
    const rows = buildSlotMigrationRowsFromPlan(
      fixtureVideoStructure,
      fixtureGenerationPlan,
      fixtureGapReport,
    );

    expect(rows.length).toBe(fixtureVideoStructure.slots.length);
    expect(rows.every((row) => row.status === "resolved")).toBe(true);

    const hookRow = rows.find((row) => row.slotId === "slot-hook-visual");
    expect(hookRow?.userAssetId).toBe("asset-user-01");
    expect(hookRow?.resolvedVisual).toContain("用户痛点开场");

    const ctaRow = rows.find((row) => row.slotId === "slot-cta");
    expect(ctaRow?.completionProvider).toBe("hyperframes_material");
    expect(ctaRow?.gapSummary).toMatch(/CTA|结尾/);
  });

  it("marks only the active slot as completing during material stage", () => {
    const rows = buildSlotMigrationRows({
      structure: fixtureVideoStructure,
      gapReport: fixtureGapReport,
      completionActions: fixtureGenerationPlan.completionActions,
      mode: "progress",
      progressGroup: "completing",
      activeSlotId: "slot-benefit",
      completedActionIds: ["action-cta"],
    });

    const ctaRow = rows.find((row) => row.slotId === "slot-cta");
    const benefitRow = rows.find((row) => row.slotId === "slot-benefit");
    const productRow = rows.find((row) => row.slotId === "slot-product");

    expect(ctaRow?.status).toBe("completed");
    expect(benefitRow?.status).toBe("completing");
    expect(productRow?.status).toBe("planned");
  });

  it("summarizes user reuse and auto completion counts", () => {
    const rows = buildSlotMigrationRowsFromPlan(
      fixtureVideoStructure,
      fixtureGenerationPlan,
      fixtureGapReport,
    );
    expect(migrationSummaryFromRows(rows)).toMatch(/复用用户素材/);
    expect(migrationSummaryFromRows(rows)).toMatch(/自动补全/);
  });
});
