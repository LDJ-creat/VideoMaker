import type { EditIntent, GenerationPlan, TaskEvent } from "@videomaker/contracts";

import { fixtureGenerationPlan } from "./generation-plan.fixture";

export const fixtureEditIntent: EditIntent = {
  intents: [
    {
      target: "generation_plan.storyboard",
      operation: "adjust_hook",
      params: { strength: "high" },
      rationale: "用户希望开头更抓人",
    },
    {
      target: "generation_plan.packaging",
      operation: "reduce_subtitles",
      params: {},
      rationale: "用户希望减少字幕",
    },
  ],
};

export const fixtureReviseGenerationResponse = {
  sourceGenerationId: "gen-demo-001",
  generationId: "gen-demo-revise-001",
  taskId: "task-fixture-revise",
  intents: fixtureEditIntent.intents,
};

export const fixtureReviseTaskEvent: TaskEvent = {
  taskId: "task-fixture-revise",
  status: "succeeded",
  stage: "completed",
  progress: 100,
  message: "改片已完成，正在应用新计划…",
  updatedAt: "2026-05-29T12:00:00.000Z",
};

export const fixtureGenerationPlanRevised: GenerationPlan = {
  ...fixtureGenerationPlan,
  id: "gen-demo-revise-001",
  masterNarration:
    "3 秒 hook：还在被晒黑？轻薄 SPF50+，一喷成膜不黏腻。限时第二件半价，评论区领券。",
  storyboard: fixtureGenerationPlan.storyboard.map((scene, index) =>
    index === 0
      ? {
          ...scene,
          script: "3 秒 hook：还在被晒黑？",
          visual: "强对比快切开场 + 大字标题",
        }
      : index === 2
        ? {
            ...scene,
            visual: "精简 CTA 卡片，减少字幕密度",
          }
        : scene,
  ),
  timeline: {
    ...fixtureGenerationPlan.timeline,
    durationSec: 26,
  },
  packagingPlan: {
    ...fixtureGenerationPlan.packagingPlan,
    styleSummary: "轻字幕 + 强 hook 开场",
  },
};
