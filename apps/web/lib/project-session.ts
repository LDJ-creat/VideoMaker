const STORAGE_PREFIX = "videomaker:project:";

export type ProjectSessionState = {
  taskId: string | null;
  sampleId: string | null;
  generationId: string | null;
  lastAction: "analysis" | "generation" | null;
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
