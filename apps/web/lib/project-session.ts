import type { EditIntentItem } from "@videomaker/contracts";

import type { GenerationPlanEntry } from "@/lib/apiClient";

const STORAGE_PREFIX = "videomaker:project:";

export type ProjectSessionState = {
  taskId: string | null;
  sampleId: string | null;
  generationId: string | null;
  activeGenerationRunId?: string | null;
  lastAction: "analysis" | "generation" | "revise" | null;
  activeGenerations?: GenerationPlanEntry[];
  activeVariantGenerationId?: string | null;
  reviseIntents?: EditIntentItem[] | null;
  reviseSessionId?: string | null;
  preReviseGenerationId?: string | null;
  analysisBatch?: {
    tasks: Array<{ sampleId: string; taskId: string }>;
    maxConcurrent: number;
  } | null;
};

export function loadProjectSession(projectId: string): ProjectSessionState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(`${STORAGE_PREFIX}${projectId}`);
    if (!raw) return null;
    return JSON.parse(raw) as ProjectSessionState;
  } catch {
    return null;
  }
}

export function saveProjectSession(
  projectId: string,
  state: ProjectSessionState,
): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(`${STORAGE_PREFIX}${projectId}`, JSON.stringify(state));
}
