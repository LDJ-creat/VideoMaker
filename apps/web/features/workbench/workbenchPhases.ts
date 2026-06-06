import type { WorkbenchPanel } from "@/features/workbench/workbenchTypes";

export type WorkbenchPhase = "prepare" | "generate" | "output";

export const PHASE_PANELS: Record<WorkbenchPhase, WorkbenchPanel[]> = {
  prepare: ["input", "analysis", "knowledge"],
  generate: ["progress", "script-review"],
  output: ["gap", "timeline", "narration", "result"],
};

export const PHASE_LABELS: Record<WorkbenchPhase, string> = {
  prepare: "准备",
  generate: "生成",
  output: "产出",
};

export const PHASE_ORDER: WorkbenchPhase[] = ["prepare", "generate", "output"];

export function getPhaseForPanel(panel: WorkbenchPanel): WorkbenchPhase {
  for (const phase of PHASE_ORDER) {
    if (PHASE_PANELS[phase].includes(panel)) {
      return phase;
    }
  }
  return "prepare";
}

export type WorkbenchPhaseState = {
  activePhase: WorkbenchPhase;
  completedPhases: WorkbenchPhase[];
};

export function computeWorkbenchPhaseState(input: {
  hasAnalyzedSample: boolean;
  hasActiveTask: boolean;
  hasGenerationPlan: boolean;
  panel: WorkbenchPanel;
}): WorkbenchPhaseState {
  const completed: WorkbenchPhase[] = ["prepare"];
  if (input.hasAnalyzedSample) {
    completed.push("prepare");
  }
  if (input.hasActiveTask || input.hasGenerationPlan) {
    completed.push("generate");
  }
  if (input.hasGenerationPlan) {
    completed.push("output");
  }

  const uniqueCompleted = PHASE_ORDER.filter((phase) => {
    if (phase === "prepare") return input.hasAnalyzedSample || input.panel !== "input";
    if (phase === "generate") return input.hasActiveTask || input.hasGenerationPlan;
    if (phase === "output") return input.hasGenerationPlan;
    return false;
  });

  let activePhase = getPhaseForPanel(input.panel);
  if (input.hasGenerationPlan) {
    activePhase = getPhaseForPanel(input.panel);
  } else if (input.hasActiveTask) {
    activePhase = "generate";
  } else if (input.hasAnalyzedSample && PHASE_PANELS.prepare.includes(input.panel)) {
    activePhase = "prepare";
  }

  return {
    activePhase,
    completedPhases: uniqueCompleted,
  };
}
