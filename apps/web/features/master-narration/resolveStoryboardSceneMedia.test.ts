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

  it("prefers finish completion action with artifactRef over stock action", () => {
    const scene = {
      id: "scene-2",
      slotId: "slot-2",
      startSec: 5,
      endSec: 19,
      visual: "文字包装描述",
      script: "口播",
      source: "packaging_completion" as const,
    };
    const plan = {
      ...fixtureGenerationPlan,
      storyboard: [scene],
      timeline: { durationSec: 19, tracks: [] },
      completionActions: [
        {
          id: "action-slot-2",
          slotId: "slot-2",
          provider: "stock_media_search",
          strategy: "stock_media_search",
          reason: "stock",
        },
        {
          id: "action-slot-2-finish",
          slotId: "slot-2",
          provider: "hyperframes_material",
          strategy: "hyperframes_material",
          reason: "finish",
          artifactRef: {
            id: "action-slot-2-finish",
            type: "video" as const,
            uri: "storage/projects/proj-demo-001/generations/gen-demo-001/generated/action-slot-2-finish.mp4",
            createdAt: "1970-01-01T00:00:00.000Z",
          },
        },
      ],
    };

    const media = resolveStoryboardSceneMedia(plan, scene);
    expect(media.kind).toBe("video");
    expect(media.provider).toBe("hyperframes_material");
    expect(media.url).toContain("action-slot-2-finish.mp4");
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
