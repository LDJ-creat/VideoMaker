import type { GenerationPlan } from "@videomaker/contracts";

export const fixtureGenerationPlan: GenerationPlan = {
  id: "gen-demo-001",
  projectId: "proj-demo-001",
  structureId: "vs-demo-001",
  inventoryId: "inv-demo-001",
  gapReportId: "gap-demo-001",
  variant: "high_conversion",
  masterNarration:
    "夏天出门还在被晒黑？轻薄 SPF50+，一喷成膜不黏腻。限时第二件半价，评论区领券。",
  storyboard: [
    {
      id: "scene-1",
      slotId: "slot-hook-visual",
      startSec: 0,
      endSec: 3,
      visual: "用户痛点开场 + 大字标题",
      script: "夏天出门还在被晒黑？",
      source: "user_asset",
    },
    {
      id: "scene-2",
      slotId: "slot-product",
      startSec: 3,
      endSec: 12,
      visual: "产品喷雾特写与上手演示",
      script: "轻薄 SPF50+，一喷成膜不黏腻",
      source: "user_asset",
    },
    {
      id: "scene-3",
      slotId: "slot-cta",
      startSec: 18,
      endSec: 28,
      visual: "价格贴纸 + 购买引导",
      script: "限时第二件半价，评论区领券",
      source: "packaging_completion",
    },
  ],
  timeline: {
    durationSec: 28,
    tracks: [
      {
        id: "track-video",
        type: "video",
        clips: [
          {
            id: "clip-slot-hook-visual",
            startSec: 0,
            endSec: 3,
            sourceRef: "asset-user-02",
          },
          {
            id: "clip-slot-product",
            startSec: 3,
            endSec: 12,
            sourceRef: "asset-user-02",
          },
        ],
      },
      {
        id: "track-text",
        type: "text",
        clips: [
          {
            id: "clip-t1",
            startSec: 0,
            endSec: 3,
            content: "夏天出门还在被晒黑？",
            styleRef: "bold_hook",
            generatedBy: {
              provider: "hyperframes_material",
              template: "title-lower-third",
            },
          },
          {
            id: "clip-t2",
            startSec: 18,
            endSec: 28,
            content: "限时第二件半价",
            styleRef: "cta_card",
            generatedBy: {
              provider: "hyperframes_material",
              template: "benefit-card",
            },
          },
        ],
      },
      {
        id: "track-voice",
        type: "voiceover",
        clips: [
          {
            id: "clip-vo1",
            startSec: 0,
            endSec: 28,
            sourceRef: "tts-narration-001",
            generatedBy: {
              provider: "tts",
              model: "tts-1",
            },
          },
        ],
      },
      {
        id: "track-bgm",
        type: "bgm",
        clips: [
          {
            id: "clip-bgm1",
            startSec: 0,
            endSec: 28,
            sourceRef: "bgm-upbeat-01",
          },
        ],
      },
      {
        id: "track-image",
        type: "image",
        clips: [
          {
            id: "clip-img1",
            startSec: 12,
            endSec: 18,
            sourceRef: "benefit-card.png",
            generatedBy: {
              provider: "image_generation",
              model: "dall-e-3",
            },
          },
          {
            id: "clip-slot-cta",
            startSec: 18,
            endSec: 28,
            sourceRef: "cta-card.png",
            generatedBy: {
              provider: "hyperframes_material",
              template: "benefit-card",
            },
          },
        ],
      },
      {
        id: "track-effect",
        type: "effect",
        clips: [
          {
            id: "clip-fx1",
            startSec: 3,
            endSec: 3.5,
            content: "zoom_punch",
          },
        ],
      },
      {
        id: "track-transition",
        type: "transition",
        clips: [
          {
            id: "clip-tr1",
            startSec: 12,
            endSec: 12.4,
            content: "wipe_left",
          },
        ],
      },
    ],
  },
  packagingPlan: {
    styleSummary: "高对比字幕 + 底部价格贴纸",
    subtitle: { font: "bold", position: "bottom" },
    titleCards: [{ template: "hook_lower_third" }],
    transitions: [{ type: "zoom_punch" }],
  },
  completionActions: [
    {
      id: "action-cta",
      slotId: "slot-cta",
      strategy: "packaging_completion",
      reason: "缺少 CTA 包装素材",
      outputRef: "pack-cta-001",
      provider: "hyperframes_material",
      rationale: "HyperFrames benefit-card 模板补全 CTA 贴纸",
      artifactRef: {
        id: "art-cta-card",
        type: "image",
        uri: "storage/projects/proj-demo-001/renders/gen-demo-001/materials/cta-card.png",
        createdAt: "2026-05-29T12:00:00.000Z",
      },
    },
    {
      id: "action-2",
      slotId: "slot-benefit",
      strategy: "image_generation",
      reason: "缺少利益点配图",
      outputRef: "img-benefit-001",
      provider: "image_generation",
      rationale: "DALL-E 生成三要点配图",
    },
  ],
};
