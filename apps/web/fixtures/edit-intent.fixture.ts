import type { EditIntent } from "@videomaker/contracts";

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
