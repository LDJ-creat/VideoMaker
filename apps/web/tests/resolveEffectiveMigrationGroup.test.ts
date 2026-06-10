import { describe, expect, it } from "vitest";

import type { GenerationMigrationArtifacts } from "@/features/structure-migration/fetchGenerationMigrationArtifacts";
import {
  resolveEffectiveMigrationGroup,
  shouldPollMigrationArtifacts,
} from "@/features/structure-migration/resolveEffectiveMigrationGroup";

const emptyArtifacts: GenerationMigrationArtifacts = {
  slotMatches: [],
  gapReport: null,
  completionActions: [],
  materialState: null,
};

describe("resolveEffectiveMigrationGroup", () => {
  it("keeps stage-derived completing group", () => {
    expect(
      resolveEffectiveMigrationGroup("generating_material", undefined, null),
    ).toBe("completing");
  });

  it("infers completing from HyperFrames authoring message when stage is running_agent", () => {
    expect(
      resolveEffectiveMigrationGroup(
        "running_agent",
        "Authoring HyperFrames material spec for slot-2",
        null,
      ),
    ).toBe("completing");
  });

  it("infers planning when gap report exists but stage is pending", () => {
    const artifacts: GenerationMigrationArtifacts = {
      ...emptyArtifacts,
      gapReport: {
        id: "gap-1",
        projectId: "p1",
        structureId: "s1",
        inventoryId: "i1",
        summary: "gaps",
        slotMatches: [],
        weakSlots: [],
        missingSlots: [{ slotId: "slot-2", reason: "missing", impact: "high", suggestedFixes: [] }],
      },
    };
    expect(resolveEffectiveMigrationGroup("running_agent", undefined, artifacts)).toBe(
      "planning",
    );
  });
});

describe("shouldPollMigrationArtifacts", () => {
  it("polls during running_agent when material message is present", () => {
    expect(
      shouldPollMigrationArtifacts({
        enabled: true,
        generationId: "gen-1",
        event: {
          stage: "running_agent",
          status: "running",
          message: "Authoring HyperFrames material spec",
        },
        artifacts: null,
      }),
    ).toBe(true);
  });

  it("does not poll after task succeeded", () => {
    expect(
      shouldPollMigrationArtifacts({
        enabled: true,
        generationId: "gen-1",
        event: {
          stage: "generating_material",
          status: "succeeded",
          message: "Completing slot slot-1",
        },
        artifacts: {
          ...emptyArtifacts,
          completionActions: [
            {
              id: "action-1",
              slotId: "slot-1",
              provider: "hyperframes_material",
              strategy: "hyperframes_material",
              reason: "fill",
              outputRef: "x",
            },
          ],
        },
      }),
    ).toBe(false);
  });

  it("does not poll for unrelated running_agent without artifacts", () => {
    expect(
      shouldPollMigrationArtifacts({
        enabled: true,
        generationId: "gen-1",
        event: {
          stage: "running_agent",
          status: "running",
          message: "Running structure analyst",
        },
        artifacts: null,
      }),
    ).toBe(false);
  });
});
