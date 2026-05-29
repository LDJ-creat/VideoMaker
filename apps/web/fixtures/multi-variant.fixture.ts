import type { GenerationPlan } from "@videomaker/contracts";

import { fixtureGenerationPlan } from "./generation-plan.fixture";
import { fixtureTaskEvent } from "./task-event.fixture";

export type MultiVariantGenerationFixtureEntry = {
  generationId: string;
  variant: string;
  taskId: string;
  label: string;
};

export const fixtureMultiVariantGenerations: MultiVariantGenerationFixtureEntry[] =
  [
    {
      generationId: "gen-demo-high-click",
      variant: "high_click",
      taskId: "task-fixture-high-click",
      label: "高点击版",
    },
    {
      generationId: fixtureGenerationPlan.id,
      variant: "high_conversion",
      taskId: fixtureTaskEvent.taskId,
      label: "高转化版",
    },
  ];

export const fixtureGenerationPlanHighClick: GenerationPlan = {
  ...fixtureGenerationPlan,
  id: "gen-demo-high-click",
  variant: "high_click",
  storyboard: fixtureGenerationPlan.storyboard.map((scene, index) =>
    index === 0
      ? {
          ...scene,
          script: "还在被晒黑？3 秒告诉你答案",
          visual: "快切痛点 + 大字 hook",
        }
      : scene,
  ),
  packagingPlan: {
    ...fixtureGenerationPlan.packagingPlan,
    styleSummary: "快节奏 hook 字幕 + 强对比转场",
  },
};
