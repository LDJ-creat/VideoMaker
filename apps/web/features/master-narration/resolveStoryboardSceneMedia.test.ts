import { describe, expect, it } from "vitest";

import { resolveStoryboardSceneMedia } from "@/features/master-narration/resolveStoryboardSceneMedia";
import { fixtureGenerationPlan } from "@/fixtures";

describe("resolveStoryboardSceneMedia", () => {
  it("resolves user asset clips from timeline sourceRef", () => {
    const scene = fixtureGenerationPlan.storyboard[0]!;
    const media = resolveStoryboardSceneMedia(fixtureGenerationPlan, scene);

    expect(media.kind).toBe("video");
    expect(media.url).toBe(
      "/api/projects/proj-demo-001/media/assets/asset-user-02",
    );
  });

  it("resolves generated image clips by slot id", () => {
    const scene = {
      ...fixtureGenerationPlan.storyboard[1]!,
      slotId: "slot-benefit",
      id: "scene-benefit",
    };
    const plan = {
      ...fixtureGenerationPlan,
      storyboard: [scene],
      timeline: {
        ...fixtureGenerationPlan.timeline,
        tracks: fixtureGenerationPlan.timeline.tracks.map((track) =>
          track.type === "image"
            ? {
                ...track,
                clips: [
                  {
                    id: "clip-slot-benefit",
                    startSec: 12,
                    endSec: 18,
                    sourceRef: "benefit-card.png",
                    generatedBy: { provider: "image_generation", model: "dall-e-3" },
                  },
                ],
              }
            : track,
        ),
      },
    };

    const media = resolveStoryboardSceneMedia(plan, scene);
    expect(media.kind).toBe("image");
    expect(media.url).toBe(
      "/api/projects/proj-demo-001/media/file/renders/gen-demo-001/benefit-card.png",
    );
    expect(media.provider).toBe("image_generation");
  });

  it("falls back to visual description placeholder when no media is resolvable", () => {
    const scene = {
      id: "scene-x",
      slotId: "slot-x",
      startSec: 0,
      endSec: 3,
      visual: "纯文字画面描述",
      script: "",
      source: "text_completion" as const,
    };
    const plan = {
      ...fixtureGenerationPlan,
      storyboard: [scene],
      timeline: { durationSec: 3, tracks: [] },
      completionActions: [],
    };

    const media = resolveStoryboardSceneMedia(plan, scene);
    expect(media.kind).toBe("placeholder");
    expect(media.url).toBeNull();
    expect(media.caption).toBe("纯文字画面描述");
  });
});
