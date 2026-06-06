import { describe, expect, it } from "vitest";

import { NARRATIVE_ROLE_LABELS, narrativeRoleLabel } from "@/lib/narrativeRoleLabels";

describe("narrativeRoleLabel", () => {
  it("maps known narrative roles to Chinese labels", () => {
    expect(narrativeRoleLabel("hook")).toBe("开场钩子");
    expect(narrativeRoleLabel("problem")).toBe("痛点");
    expect(narrativeRoleLabel("cta")).toBe("行动号召");
    expect(Object.keys(NARRATIVE_ROLE_LABELS)).toHaveLength(8);
  });

  it("falls back to raw role for unknown values", () => {
    expect(narrativeRoleLabel("custom")).toBe("custom");
  });
});
