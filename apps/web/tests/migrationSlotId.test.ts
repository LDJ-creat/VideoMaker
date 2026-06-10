import { describe, expect, it } from "vitest";

import { deriveCompletedSlotIds } from "@/lib/deriveCompletedSlotIds";
import { normalizeMigrationSlotId } from "@/lib/migrationSlotId";

describe("normalizeMigrationSlotId", () => {
  it("strips finish and ken-burns suffixes", () => {
    expect(normalizeMigrationSlotId("slot-1-finish")).toBe("slot-1");
    expect(normalizeMigrationSlotId("slot-cta-ken-burns")).toBe("slot-cta");
    expect(normalizeMigrationSlotId("slot-1")).toBe("slot-1");
  });
});

describe("deriveCompletedSlotIds", () => {
  it("maps completed action ids to structure slot ids", () => {
    const completed = deriveCompletedSlotIds(
      [
        {
          id: "action-slot-1-finish",
          slotId: "slot-1-finish",
          provider: "hyperframes_material",
          strategy: "hyperframes_material",
          reason: "polish",
          outputRef: "x",
        },
        {
          id: "action-slot-6",
          slotId: "slot-6",
          provider: "image_generation",
          strategy: "image_generation",
          reason: "fill",
          outputRef: "y",
        },
      ],
      ["action-slot-1-finish"],
    );
    expect([...completed]).toEqual(["slot-1"]);
  });
});
