import type {
  GapReport,
  GenerationPlan,
  TaskEvent,
  UserBrief,
  VideoStructure,
} from "@videomaker/contracts";

import type { ApiMeta, ApiResult } from "@/lib/api-types";
import { metaFromResponse } from "@/lib/api-types";
import { setLastDataSource } from "@/lib/data-source-store";
import { ApiClientError } from "@/lib/errors";

export type CreateSampleFromUrlRequest = {
  url: string;
};

export type UserBriefRequest = UserBrief;

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
};

export type CookieUploadMode = "merge" | "replace";

export type CookieStatus = {
  configured: boolean;
  updatedAt?: string | null;
  domains?: string[];
  uploadMode?: string | null;
};

export type UploadResponse = {
  id: string;
  taskId?: string;
};

export type GenerationResponse = GenerationPlan & {
  gapReport?: GapReport;
};

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  const response = await fetch(path, init);
  const meta = metaFromResponse(response);
  setLastDataSource(meta.dataSource);

  if (!response.ok) {
    const body = await response.text();
    let message = body || response.statusText;
    try {
      const parsed = JSON.parse(body) as { message?: string; detail?: string };
      if (parsed.detail) message = parsed.detail;
      else if (parsed.message) message = parsed.message;
    } catch {
      /* plain text */
    }
    throw new ApiClientError(message, "API_ERROR", response.status);
  }

  if (response.status === 204) {
    return { data: undefined as T, meta };
  }

  const data = (await response.json()) as T;
  return { data, meta };
}

export async function createProject(name: string): Promise<ApiResult<ProjectSummary>> {
  return apiFetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function getProject(
  projectId: string,
): Promise<ApiResult<ProjectSummary>> {
  return apiFetch(`/api/projects/${projectId}`);
}

export type ActiveSampleSummary = {
  id: string;
  status: string;
  sourceKind: string;
  hasStructure: boolean;
  videoUri?: string;
};

export async function getActiveSample(
  projectId: string,
): Promise<ApiResult<ActiveSampleSummary>> {
  return apiFetch(`/api/projects/${projectId}/samples/active`);
}

export async function uploadSampleVideo(
  projectId: string,
  file: File,
): Promise<ApiResult<UploadResponse>> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`/api/projects/${projectId}/samples/upload`, {
    method: "POST",
    body: form,
  });
}

/** URL import — backend runs yt-dlp; frontend only calls BFF/API. */
/** Global yt-dlp cookies (shared by all projects on this API instance). */
export async function getCookieStatus(): Promise<ApiResult<CookieStatus>> {
  return apiFetch("/api/settings/cookies");
}

export async function uploadCookies(
  file: File,
  mode: CookieUploadMode = "merge",
): Promise<
  ApiResult<{
    ok: boolean;
    configured: boolean;
    domains?: string[];
    mode?: string;
  }>
> {
  const form = new FormData();
  form.append("file", file);
  const query = new URLSearchParams({ mode });
  return apiFetch(`/api/settings/cookies/upload?${query}`, {
    method: "POST",
    body: form,
  });
}

export async function importSampleFromUrl(
  projectId: string,
  payload: CreateSampleFromUrlRequest,
): Promise<ApiResult<UploadResponse>> {
  return apiFetch(`/api/projects/${projectId}/samples/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadAsset(
  projectId: string,
  file: File,
): Promise<ApiResult<UploadResponse>> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`/api/projects/${projectId}/assets/upload`, {
    method: "POST",
    body: form,
  });
}

export async function saveBrief(
  projectId: string,
  brief: UserBriefRequest,
): Promise<ApiResult<{ ok: boolean }>> {
  return apiFetch(`/api/projects/${projectId}/brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
  });
}

export async function retryTask(taskId: string): Promise<ApiResult<TaskEvent>> {
  return apiFetch(`/api/tasks/${taskId}/retry`, { method: "POST" });
}

export async function startSampleAnalysis(
  sampleId: string,
): Promise<ApiResult<{ taskId: string }>> {
  return apiFetch(`/api/samples/${sampleId}/analyze`, { method: "POST" });
}

export async function getTask(taskId: string): Promise<ApiResult<TaskEvent>> {
  return apiFetch(`/api/tasks/${taskId}`);
}

export async function createGenerationPlan(
  projectId: string,
): Promise<ApiResult<{ generationId: string; taskId?: string; gapReport?: GapReport }>> {
  return apiFetch(`/api/projects/${projectId}/generation-plan`, {
    method: "POST",
  });
}

export async function getGeneration(
  generationId: string,
): Promise<ApiResult<GenerationResponse>> {
  return apiFetch(`/api/generations/${generationId}`);
}

export async function getSampleStructure(
  sampleId: string,
): Promise<ApiResult<VideoStructure>> {
  return apiFetch(`/api/samples/${sampleId}/structure`);
}

export async function getSampleAnalysis(
  sampleId: string,
): Promise<ApiResult<VideoStructure>> {
  return apiFetch(`/api/samples/${sampleId}/analysis`);
}

export function getTaskEventsUrl(taskId: string): string {
  return `/api/tasks/${taskId}/events`;
}

export type { ApiMeta, ApiResult };
