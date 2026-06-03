import type {
  AgentRunLog,
  EditIntentItem,
  GapReport,
  GenerationPlan,
  TaskEvent,
  UserBrief,
  VariantDefinition,
  VideoStructure,
} from "@videomaker/contracts";

import type { ApiMeta, ApiResult } from "@/lib/api-types";
import { metaFromResponse } from "@/lib/api-types";
import { setLastDataSource } from "@/lib/data-source-store";
import { ApiClientError, formatFastApiDetail } from "@/lib/errors";
import {
  getEnabledVariants,
  getVariantLabel,
  loadVariantRegistry as loadWebVariantRegistry,
} from "@/lib/variantRegistry";

export type { VariantDefinition };

export type ProviderStatus = {
  configured: boolean;
  hasApiKey?: boolean;
  model?: string;
  driver?: string;
  baseUrl?: string;
};

export type ProviderSettingsUpdate = {
  baseUrl?: string;
  apiKey?: string;
  model?: string;
  driver?: string;
};

export type ModelGatewaySettingsUpdate = {
  providers: Partial<
    Record<
      keyof ModelGatewayStatusResponse["providers"],
      ProviderSettingsUpdate
    >
  >;
};

export type ModelGatewayStatusResponse = {
  fixtureMode: boolean;
  providers: {
    text: ProviderStatus;
    vision: ProviderStatus;
    tts: ProviderStatus;
    image: ProviderStatus;
    video: ProviderStatus;
  };
};

export type GenerationPlanEntry = {
  generationId: string;
  variant: string;
  taskId: string;
  label?: string;
};

export type MultiVariantGenerationResponse = {
  generations: GenerationPlanEntry[];
};

export type CreateGenerationPlanBody = {
  variants?: string[];
  brief?: UserBrief;
};

export type ReviseGenerationResponse = {
  sourceGenerationId: string;
  generationId: string;
  taskId: string;
  intents: EditIntentItem[];
};

export function loadVariantRegistry(): VariantDefinition[] {
  return loadWebVariantRegistry();
}

export function getDefaultVariantIds(): string[] {
  return getEnabledVariants().map((variant) => variant.id);
}

function normalizeCreateGenerationPlanBody(
  body?: CreateGenerationPlanBody | UserBrief,
): CreateGenerationPlanBody {
  if (!body) return {};
  if ("sellingPoints" in body || "mustMention" in body || "avoidMention" in body) {
    return { brief: body as UserBrief };
  }
  return body as CreateGenerationPlanBody;
}

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
  renderVideoUrl?: string;
};

export type LatestGenerationEntry = {
  generationId: string;
  variant: string;
  plan: GenerationResponse;
  /** Present when renders/{generationId}/output.mp4 exists on the API storage volume. */
  renderVideoUrl?: string;
};

export type LatestGenerationsResponse = {
  generations: LatestGenerationEntry[];
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
      const parsed = JSON.parse(body) as {
        message?: string;
        detail?: unknown;
      };
      const fromDetail = formatFastApiDetail(parsed.detail);
      if (fromDetail) message = fromDetail;
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

export async function listProjects(): Promise<ApiResult<{ projects: ProjectSummary[] }>> {
  return apiFetch("/api/projects");
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
  sourceUrl?: string;
  fileName?: string;
  previewUrl?: string;
};

export type ProjectAsset = {
  id: string;
  type: string;
  uri: string;
  description?: string;
  tags?: string[];
  durationSec?: number;
  previewUrl?: string;
};

export async function getActiveSample(
  projectId: string,
): Promise<ApiResult<ActiveSampleSummary>> {
  return apiFetch(`/api/projects/${projectId}/samples/active`);
}

export async function listProjectSamples(
  projectId: string,
): Promise<ApiResult<{ samples: ActiveSampleSummary[] }>> {
  return apiFetch(`/api/projects/${projectId}/samples`);
}

export async function getBrief(
  projectId: string,
): Promise<ApiResult<{ brief: UserBriefRequest | null }>> {
  return apiFetch(`/api/projects/${projectId}/brief`);
}

export async function listProjectAssets(
  projectId: string,
): Promise<ApiResult<{ assets: ProjectAsset[] }>> {
  return apiFetch(`/api/projects/${projectId}/assets`);
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
  body?: CreateGenerationPlanBody | UserBriefRequest,
): Promise<ApiResult<MultiVariantGenerationResponse>> {
  const normalized = normalizeCreateGenerationPlanBody(body);
  const payload: CreateGenerationPlanBody = {
    ...normalized,
    variants: normalized.variants ?? getDefaultVariantIds(),
  };
  return apiFetch(`/api/projects/${projectId}/generation-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getModelGatewayStatus(): Promise<
  ApiResult<ModelGatewayStatusResponse>
> {
  return apiFetch("/api/settings/model-gateway");
}

export async function updateModelGatewaySettings(
  body: ModelGatewaySettingsUpdate,
): Promise<ApiResult<ModelGatewayStatusResponse>> {
  return apiFetch("/api/settings/model-gateway", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getGenerationAgentRuns(
  generationId: string,
): Promise<ApiResult<{ runs: AgentRunLog[] }>> {
  return apiFetch(`/api/generations/${generationId}/agent-runs`);
}

export async function reviseGeneration(
  generationId: string,
  instruction: string,
): Promise<ApiResult<ReviseGenerationResponse>> {
  return apiFetch(`/api/generations/${generationId}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
}

export { getVariantLabel };

export async function getGeneration(
  generationId: string,
): Promise<ApiResult<GenerationResponse>> {
  return apiFetch(`/api/generations/${generationId}`);
}

export async function getLatestGenerations(
  projectId: string,
): Promise<ApiResult<LatestGenerationsResponse>> {
  return apiFetch(`/api/projects/${projectId}/generations/latest`);
}

/** @deprecated Use getLatestGenerations — kept for callers migrating from P0 single-object shape. */
export async function getLatestGeneration(
  projectId: string,
): Promise<ApiResult<LatestGenerationsResponse>> {
  return getLatestGenerations(projectId);
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

export { artifactDisplayUrl } from "@/lib/artifactUrl";

export type { ApiMeta, ApiResult };
