import type { AgentRunLog } from "@videomaker/contracts";

export const fixtureAgentRuns: AgentRunLog[] = [
  {
    id: "run-structure-001",
    generationId: "gen-demo-001",
    agentName: "structure_analyst",
    promptVersion: "a1b2c3d4",
    model: "gpt-4o",
    task: "extract_structure",
    inputSummary: "sample video + ASR transcript",
    outputValid: true,
    latencyMs: 1200,
    tokenUsage: { prompt: 800, completion: 400 },
    createdAt: "2026-05-29T12:00:00Z",
  },
  {
    id: "run-gap-001",
    generationId: "gen-demo-001",
    agentName: "gap_planner",
    promptVersion: "e5f6g7h8",
    model: "gpt-4o",
    task: "plan_completion",
    inputSummary: "structure slots + asset inventory",
    outputValid: true,
    latencyMs: 980,
    createdAt: "2026-05-29T12:01:30Z",
  },
];
