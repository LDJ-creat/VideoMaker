import { describe, expect, it } from "vitest";

import { parseTaskMaterialProgress } from "@/lib/parseTaskMaterialProgress";

describe("parseTaskMaterialProgress", () => {
  it("parses completing slot messages", () => {
    const result = parseTaskMaterialProgress("Completing slot slot-1-finish");
    expect(result.slotId).toBe("slot-1-finish");
    expect(result.summary).toContain("slot-1-finish");
  });

  it("parses HyperFrames authoring messages", () => {
    const result = parseTaskMaterialProgress(
      "Authoring HyperFrames material spec for slot-2",
    );
    expect(result.actionLabel).toBe("HyperFrames 包装");
    expect(result.summary).toContain("HyperFrames");
  });

  it("returns empty hint for unrelated messages", () => {
    const result = parseTaskMaterialProgress("Queued generation");
    expect(result.summary).toBeNull();
  });
});
