import type { TaskEvent, UserBrief } from "@videomaker/contracts";

import { shouldUseFixtureFallback } from "@/lib/config";
import {
  fixtureGenerationPlan,
  fixtureGapReport,
  fixtureProject,
  fixtureTaskEvent,
  fixtureVideoStructure,
} from "@/fixtures";

export type CreateSampleFromUrlRequest = {
  url: string;
};

export type UserBriefRequest = UserBrief;

export type ApiError = {
  code: string;
  message: string;
  status?: number;
};

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
};

export type UploadResponse = {
  id: string;
  taskId?: string;
};

async function apiFetch<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    throw {
      code: "API_ERROR",
      message: body || response.statusText,
      status: response.status,
    } satisfies ApiError;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function withFixture<T>(fallback: T, error: unknown): T {
  if (!shouldUseFixtureFallback()) {
    throw error;
  }
  return fallback;
}

export async function createProject(
  apiBaseUrl: string,
  name: string,
): Promise<ProjectSummary> {
  try {
    return await apiFetch(apiBaseUrl, "/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch (error) {
    return withFixture(
      { ...fixtureProject, name },
      error,
    );
  }
}

export async function getProject(
  apiBaseUrl: string,
  projectId: string,
): Promise<ProjectSummary> {
  try {
    return await apiFetch(apiBaseUrl, `/api/projects/${projectId}`);
  } catch (error) {
    return withFixture({ ...fixtureProject, id: projectId }, error);
  }
}

export async function uploadSampleVideo(
  apiBaseUrl: string,
  projectId: string,
  file: File,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/projects/${projectId}/samples/upload`,
      { method: "POST", body: form },
    );
  } catch (error) {
    return withFixture(
      { id: "sample-fixture-local", taskId: fixtureTaskEvent.taskId },
      error,
    );
  }
}

/** URL import — backend runs yt-dlp; frontend never calls yt-dlp directly. */
export async function importSampleFromUrl(
  apiBaseUrl: string,
  projectId: string,
  payload: CreateSampleFromUrlRequest,
): Promise<UploadResponse> {
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/projects/${projectId}/samples/from-url`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
  } catch (error) {
    return withFixture(
      { id: "sample-fixture-url", taskId: fixtureTaskEvent.taskId },
      error,
    );
  }
}

export async function uploadAsset(
  apiBaseUrl: string,
  projectId: string,
  file: File,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/projects/${projectId}/assets/upload`,
      { method: "POST", body: form },
    );
  } catch (error) {
    return withFixture({ id: `asset-${file.name}` }, error);
  }
}

export async function saveBrief(
  apiBaseUrl: string,
  projectId: string,
  brief: UserBriefRequest,
): Promise<{ ok: boolean }> {
  try {
    return await apiFetch(apiBaseUrl, `/api/projects/${projectId}/brief`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(brief),
    });
  } catch (error) {
    return withFixture({ ok: true }, error);
  }
}

export async function startSampleAnalysis(
  apiBaseUrl: string,
  sampleId: string,
): Promise<{ taskId: string }> {
  try {
    return await apiFetch(apiBaseUrl, `/api/samples/${sampleId}/analyze`, {
      method: "POST",
    });
  } catch (error) {
    return withFixture({ taskId: fixtureTaskEvent.taskId }, error);
  }
}

export async function getTask(
  apiBaseUrl: string,
  taskId: string,
): Promise<TaskEvent> {
  try {
    return await apiFetch(apiBaseUrl, `/api/tasks/${taskId}`);
  } catch (error) {
    return withFixture({ ...fixtureTaskEvent, taskId }, error);
  }
}

export async function createGenerationPlan(
  apiBaseUrl: string,
  projectId: string,
): Promise<{ generationId: string; taskId?: string }> {
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/projects/${projectId}/generation-plan`,
      { method: "POST" },
    );
  } catch (error) {
    return withFixture(
      { generationId: fixtureGenerationPlan.id, taskId: fixtureTaskEvent.taskId },
      error,
    );
  }
}

export async function getGeneration(
  apiBaseUrl: string,
  generationId: string,
) {
  try {
    return await apiFetch(apiBaseUrl, `/api/generations/${generationId}`);
  } catch (error) {
    return withFixture(
      { ...fixtureGenerationPlan, id: generationId },
      error,
    );
  }
}

export async function getSampleStructure(apiBaseUrl: string, sampleId: string) {
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/samples/${sampleId}/structure`,
    );
  } catch (error) {
    return withFixture(
      { ...fixtureVideoStructure, sourceVideoId: sampleId },
      error,
    );
  }
}

export async function getSampleAnalysis(apiBaseUrl: string, sampleId: string) {
  try {
    return await apiFetch(
      apiBaseUrl,
      `/api/samples/${sampleId}/analysis`,
    );
  } catch (error) {
    return withFixture(fixtureVideoStructure, error);
  }
}

export function getTaskEventsUrl(apiBaseUrl: string, taskId: string): string {
  return `${apiBaseUrl}/api/tasks/${taskId}/events`;
}

export { fixtureGapReport, fixtureVideoStructure, fixtureGenerationPlan };
