import { describe, expect, it } from "vitest";

import { fixtureGenerationPlan } from "@/fixtures";
import type { GenerationResponse } from "@/lib/apiClient";
import { resolveRenderVideoUrl } from "@/lib/resolveRenderVideoUrl";

describe("resolveRenderVideoUrl", () => {
  it("prefers cached map entry over plan field", () => {
    const url = resolveRenderVideoUrl(fixtureGenerationPlan, {
      [fixtureGenerationPlan.id]: "/api/cached.mp4",
    });
    expect(url).toBe("/api/cached.mp4");
  });

  it("falls back to renderVideoUrl on plan payload", () => {
    const plan: GenerationResponse = {
      ...fixtureGenerationPlan,
      renderVideoUrl: "/api/plan.mp4",
    };
    const url = resolveRenderVideoUrl(plan, {});
    expect(url).toBe("/api/plan.mp4");
  });
});
