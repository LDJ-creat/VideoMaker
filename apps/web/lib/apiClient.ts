import type {
  AgentRunLog,
  EditIntentItem,
  GapReport,
  GenerationPlan,
  RevisePlan,
  ReviseSession,
  KnowledgeEntry,
  KnowledgeRecommendation,
  KnowledgeCategorySummary,
  KnowledgeCategoryEntryCard,
  KnowledgeCategoryDetail,
  CreateProjectFromKnowledgeTemplateRequest,
  CreateProjectFromKnowledgeTemplateResponse,
  ProjectSummary,
  ProjectKnowledgeSelection,
  ScriptDraft,
  TaskEvent,
  UserBrief,
  SampleAnalysisFacts,
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

export type { SampleAnalysisFacts, VariantDefinition };

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

export type TtsPreferences = {
  resourceId: string;
  speaker: string;
  modelVariant: string;
  speechRate: number;
  loudnessRate: number;
  emotion: string | null;
  emotionScale: number;
  contextTexts: string;
  explicitLanguage: string;
  format: string;
  sampleRate: number;
  chunkCharLimit: number;
};

export type ModelGatewayPreferences = {
  directMultimodalAnalysisEnabled: boolean;
  tts?: Partial<TtsPreferences>;
};

export type StructureAnalysisRoutePreview = "direct_multimodal" | "map_reduce";

export type ModelGatewaySettingsUpdate = {
  providers?: Partial<
    Record<
      keyof ModelGatewayStatusResponse["providers"],
      ProviderSettingsUpdate
    >
  >;
  preferences?: Partial<ModelGatewayPreferences>;
};

export type ModelGatewayProviderProbeRequest = {
  provider: "text" | "videoUnderstanding";
  baseUrl?: string;
  model?: string;
  apiKey?: string;
};

export type ModelGatewayProviderProbeResponse = {
  provider: "text" | "videoUnderstanding";
  ok: boolean;
  latencyMs: number;
  message: string;
  detail?: string | null;
  replyPreview?: string | null;
};

export type ModelGatewayStatusResponse = {
  fixtureMode: boolean;
  providers: {
    text: ProviderStatus;
    vision: ProviderStatus;
    videoUnderstanding: ProviderStatus;
    tts: ProviderStatus;
    image: ProviderStatus;
    video: ProviderStatus;
  };
  preferences: ModelGatewayPreferences;
  ttsPreferences: TtsPreferences;
  analysisRoutePreview: StructureAnalysisRoutePreview;
};

export type GenerationPlanEntry = {
  generationId: string;
  variant: string;
  taskId: string;
  label?: string;
};

export type MultiVariantGenerationResponse = {
  generationRunId?: string;
  generations: GenerationPlanEntry[];
};

export type SampleSelectionOverride = {
  primarySampleId: string;
  referenceSampleIds?: string[];
};

export type CreateGenerationPlanBody = {
  variants?: string[];
  brief?: UserBrief;
  sampleSelection?: SampleSelectionOverride;
};

export type UploadBatchSummary = {
  id: string;
  projectId: string;
  status: string;
  sampleIds: string[];
  createdAt: string;
  updatedAt: string;
  samples?: Array<{
    id: string;
    status: string;
    hasStructure: boolean;
    uploadBatchId?: string | null;
  }>;
};

export type ProjectSampleSelection = {
  projectId: string;
  primarySampleId: string | null;
  referenceSampleIds: string[];
  activeUploadBatchId?: string | null;
  mode: "auto" | "user_override" | "none";
  updatedAt: string;
};

export type SampleRecommendation = {
  projectId: string;
  suggestedPrimaryId: string;
  suggestedReferenceIds: string[];
  candidates: Array<{
    sampleId: string;
    score: number;
    reasons: string[];
    summary?: string;
    uploadBatchId?: string | null;
    hasStructure: boolean;
    status: string;
  }>;
  computedAt: string;
};

export type GenerationRunSummary = {
  id: string;
  projectId: string;
  status: string;
  variantIds: string[];
  generationIds: string[];
  synthesizedStructureId?: string | null;
  provenanceId?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type StructureProvenanceSummary = {
  id: string;
  projectId: string;
  generationRunId: string;
  primarySampleId: string;
  referenceSampleIds: string[];
  slotAttribution: Array<{
    slotId: string;
    sourceSampleId: string;
    sourceSlotId?: string;
    rationale: string;
  }>;
  fallback?: boolean;
  createdAt: string;
};

export type ReviseGenerationResponse = {
  sourceGenerationId: string;
  generationId: string;
  taskId: string;
  intents: EditIntentItem[];
  plan?: RevisePlan;
  executionMode?: "in_place" | "fork";
};

export type RevisePlanResponse = {
  plan: RevisePlan;
  sessionId: string;
};

export type ReviseExecuteResponse = {
  sourceGenerationId: string;
  generationId: string;
  taskId: string;
  executionMode: "in_place" | "fork";
  plan: RevisePlan;
};

export type ReviseSessionResponse = {
  session: ReviseSession | null;
  plans: RevisePlan[];
  pendingPlan?: RevisePlan | null;
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

export type { ProjectSummary };

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
  /** Absent when generation failed before a plan artifact was persisted. */
  plan?: GenerationResponse;
  taskId?: string;
  status?: string;
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

export async function updateProject(
  projectId: string,
  payload: { name: string },
): Promise<ApiResult<ProjectSummary>> {
  return apiFetch(`/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteProject(projectId: string): Promise<ApiResult<void>> {
  return apiFetch(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
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
  /** Sharp keyframe JPEG; preferred over video for list thumbnails */
  posterUrl?: string;
  uploadBatchId?: string | null;
  batchCreatedAt?: string | null;
  taskId?: string | null;
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
  uploadBatchId?: string,
): Promise<ApiResult<UploadResponse>> {
  const form = new FormData();
  form.append("file", file);
  const query = uploadBatchId
    ? `?uploadBatchId=${encodeURIComponent(uploadBatchId)}`
    : "";
  return apiFetch(`/api/projects/${projectId}/samples/upload${query}`, {
    method: "POST",
    body: form,
  });
}

export async function uploadSampleBatch(
  projectId: string,
  files: File[],
): Promise<ApiResult<{ batchId: string; samples: UploadResponse[] }>> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return apiFetch(`/api/projects/${projectId}/samples/upload-batch`, {
    method: "POST",
    body: form,
  });
}

export async function listUploadBatches(
  projectId: string,
): Promise<ApiResult<{ batches: UploadBatchSummary[] }>> {
  return apiFetch(`/api/projects/${projectId}/upload-batches`);
}

export async function analyzeSampleBatch(
  projectId: string,
  body?: { sampleIds?: string[]; uploadBatchId?: string },
): Promise<ApiResult<{ tasks: Array<{ sampleId: string; taskId: string }>; maxConcurrent: number }>> {
  return apiFetch(`/api/projects/${projectId}/samples/analyze-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export async function getSampleSelection(
  projectId: string,
): Promise<ApiResult<{ selection: ProjectSampleSelection | null }>> {
  return apiFetch(`/api/projects/${projectId}/samples/selection`);
}

export async function updateSampleSelection(
  projectId: string,
  body: {
    primarySampleId?: string | null;
    referenceSampleIds?: string[];
    activeUploadBatchId?: string | null;
  },
): Promise<ApiResult<{ selection: ProjectSampleSelection }>> {
  return apiFetch(`/api/projects/${projectId}/samples/selection`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function resetSampleSelection(
  projectId: string,
): Promise<ApiResult<{ selection: ProjectSampleSelection | null }>> {
  return apiFetch(`/api/projects/${projectId}/samples/selection/reset`, {
    method: "POST",
  });
}

export async function recommendSamples(
  projectId: string,
): Promise<ApiResult<{ recommendation: SampleRecommendation }>> {
  return apiFetch(`/api/projects/${projectId}/samples/recommend`, {
    method: "POST",
  });
}

export async function listGenerationRuns(
  projectId: string,
  limit = 20,
): Promise<ApiResult<{ runs: GenerationRunSummary[] }>> {
  return apiFetch(`/api/projects/${projectId}/generation-runs?limit=${limit}`);
}

export async function getGenerationRun(
  projectId: string,
  runId: string,
): Promise<
  ApiResult<{
    run: GenerationRunSummary;
    generations: Array<{
      generationId: string;
      variant?: string;
      status?: string;
      taskId?: string | null;
      plan?: GenerationResponse;
    }>;
    provenance?: StructureProvenanceSummary | null;
  }>
> {
  return apiFetch(`/api/projects/${projectId}/generation-runs/${runId}`);
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

export type StockMediaStatusResponse = {
  provider: string;
  configured: boolean;
  hasApiKey: boolean;
};

export type StockMediaSettingsUpdate = {
  apiKey: string;
};

export type StockMediaProbeResponse = {
  ok: boolean;
  provider: string;
  sampleResultCount?: number;
};

export async function getStockMediaStatus(): Promise<ApiResult<StockMediaStatusResponse>> {
  return apiFetch("/api/settings/stock-media");
}

export async function updateStockMediaSettings(
  body: StockMediaSettingsUpdate,
): Promise<ApiResult<StockMediaStatusResponse>> {
  return apiFetch("/api/settings/stock-media", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function testStockMediaConnection(
  body?: { apiKey?: string },
): Promise<ApiResult<StockMediaProbeResponse>> {
  return apiFetch("/api/settings/stock-media/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
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

export async function testModelGatewayProvider(
  body: ModelGatewayProviderProbeRequest,
): Promise<ApiResult<ModelGatewayProviderProbeResponse>> {
  return apiFetch("/api/settings/model-gateway/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getGenerationAgentRuns(
  generationId: string,
): Promise<ApiResult<{ runs: AgentRunLog[] }>> {
  return apiFetch(`/api/generations/${generationId}/agent-runs`);
}

export async function planReviseGeneration(
  generationId: string,
  instruction: string,
  options?: { newSession?: boolean },
): Promise<ApiResult<RevisePlanResponse>> {
  return apiFetch(`/api/generations/${generationId}/revise/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      instruction,
      newSession: options?.newSession ?? false,
    }),
  });
}

export async function executeRevisePlan(
  generationId: string,
  planId: string,
): Promise<ApiResult<ReviseExecuteResponse>> {
  return apiFetch(`/api/generations/${generationId}/revise/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planId }),
  });
}

export async function cancelRevisePlan(
  generationId: string,
  planId?: string,
): Promise<ApiResult<{ cancelled: boolean; planIds: string[] }>> {
  return apiFetch(`/api/generations/${generationId}/revise/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ planId }),
  });
}

export async function getReviseSession(
  generationId: string,
): Promise<ApiResult<ReviseSessionResponse>> {
  return apiFetch(`/api/generations/${generationId}/revise/session`);
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
): Promise<ApiResult<SampleAnalysisFacts>> {
  return apiFetch(`/api/samples/${sampleId}/sample-analysis`);
}

export type SampleKeyframeRecord = {
  timeSec: number;
  score: number;
  relativePath: string;
  previewUrl: string;
};

export async function getSampleKeyframes(
  sampleId: string,
): Promise<ApiResult<{ sampleId: string; keyframes: SampleKeyframeRecord[] }>> {
  return apiFetch(`/api/samples/${sampleId}/keyframes`);
}

export function getTaskEventsUrl(taskId: string): string {
  return `/api/tasks/${taskId}/events`;
}

export { artifactDisplayUrl } from "@/lib/artifactUrl";

export type KnowledgeDraftResponse = {
  projectId: string;
  sampleId: string;
  skillMarkdown: string;
  entryMeta: Record<string, unknown>;
  skillMdUri: string;
  structureJsonUri: string;
  publishedEntry?: {
    id: string;
    title?: string;
    category?: string;
    style?: string;
    updatedAt?: string;
  } | null;
};

export type KnowledgeListResponse = {
  entries: KnowledgeEntry[];
};

export type KnowledgeRecommendResponse = {
  recommendation: KnowledgeRecommendation;
  selection: ProjectKnowledgeSelection | null;
};

export type KnowledgeSelectionResponse = {
  selection: ProjectKnowledgeSelection | null;
};

export type {
  KnowledgeCategorySummary,
  KnowledgeCategoryEntryCard,
  KnowledgeCategoryDetail,
  CreateProjectFromKnowledgeTemplateRequest,
  CreateProjectFromKnowledgeTemplateResponse,
};

export async function listKnowledgeCategories(): Promise<
  ApiResult<{ categories: KnowledgeCategorySummary[] }>
> {
  return apiFetch("/api/knowledge/categories");
}

export async function getKnowledgeCategory(
  categorySlug: string,
): Promise<ApiResult<KnowledgeCategoryDetail>> {
  return apiFetch(`/api/knowledge/categories/${encodeURIComponent(categorySlug)}`);
}

export async function createProjectFromKnowledgeTemplate(
  body: CreateProjectFromKnowledgeTemplateRequest,
): Promise<ApiResult<CreateProjectFromKnowledgeTemplateResponse>> {
  return apiFetch("/api/projects/from-knowledge-template", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type CompositionPatternCandidate = {
  slotId: string;
  slotRole: string;
  storyboardSummary: string;
  actionId?: string | null;
  draftReady: boolean;
  publishedEntry?: {
    id: string;
    title?: string;
    updatedAt?: string;
  } | null;
};

export type CompositionPatternsResponse = {
  generationId: string;
  patterns: CompositionPatternCandidate[];
};

export async function getCompositionPatterns(
  generationId: string,
): Promise<ApiResult<CompositionPatternsResponse>> {
  return apiFetch(`/api/generations/${generationId}/composition-patterns`);
}

export async function promoteCompositionPattern(
  projectId: string,
  body: {
    generationId: string;
    slotId: string;
    confirm: true;
  },
): Promise<ApiResult<{ entry: KnowledgeEntry }>> {
  return apiFetch(`/api/projects/${projectId}/knowledge/composition/promote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function listKnowledgeEntries(params?: {
  category?: string;
  style?: string;
  hookType?: string;
  tempo?: string;
  q?: string;
}): Promise<ApiResult<KnowledgeListResponse>> {
  const search = new URLSearchParams();
  if (params?.category) search.set("category", params.category);
  if (params?.style) search.set("style", params.style);
  if (params?.hookType) search.set("hookType", params.hookType);
  if (params?.tempo) search.set("tempo", params.tempo);
  if (params?.q) search.set("q", params.q);
  const query = search.toString();
  return apiFetch(`/api/knowledge/entries${query ? `?${query}` : ""}`);
}

export async function getKnowledgeEntry(
  entryId: string,
): Promise<ApiResult<KnowledgeEntry>> {
  return apiFetch(`/api/knowledge/entries/${entryId}`);
}

export async function getKnowledgeSkill(
  entryId: string,
): Promise<ApiResult<{ entryId: string; markdown: string }>> {
  return apiFetch(`/api/knowledge/entries/${entryId}/skill`);
}

export async function getKnowledgeDraft(
  projectId: string,
  sampleId: string,
): Promise<ApiResult<KnowledgeDraftResponse>> {
  return apiFetch(`/api/projects/${projectId}/samples/${sampleId}/knowledge-draft`);
}

export async function promoteKnowledgeDraft(
  projectId: string,
  sampleId: string,
  body: {
    title: string;
    category: string;
    style: string;
    hookType?: string;
    summaryOverride?: string;
    categorySlug?: string;
  },
): Promise<ApiResult<{ entry: KnowledgeEntry }>> {
  return apiFetch(`/api/projects/${projectId}/samples/${sampleId}/knowledge/promote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function recommendKnowledge(
  projectId: string,
): Promise<ApiResult<KnowledgeRecommendResponse>> {
  return apiFetch(`/api/projects/${projectId}/knowledge/recommend`, {
    method: "POST",
  });
}

export async function getKnowledgeSelection(
  projectId: string,
): Promise<ApiResult<KnowledgeSelectionResponse>> {
  return apiFetch(`/api/projects/${projectId}/knowledge/selection`);
}

export async function updateKnowledgeSelection(
  projectId: string,
  body: {
    primaryEntryId?: string | null;
    referenceEntryIds?: string[];
    applyStructure?: boolean;
  },
): Promise<ApiResult<KnowledgeSelectionResponse>> {
  return apiFetch(`/api/projects/${projectId}/knowledge/selection`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function resetKnowledgeSelection(
  projectId: string,
): Promise<ApiResult<KnowledgeSelectionResponse>> {
  return apiFetch(`/api/projects/${projectId}/knowledge/selection/reset`, {
    method: "POST",
  });
}

export async function applyKnowledgeToProject(
  projectId: string,
  body: { entryId: string; applyStructure?: boolean },
): Promise<
  ApiResult<{
    applied: { sampleId?: string; entryId: string };
    selection: ProjectKnowledgeSelection;
  }>
> {
  return apiFetch(`/api/projects/${projectId}/structure-from-knowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type DurationRecommendationResponse = {
  recommendedSec: number;
  sampleId?: string | null;
  structureDurationSec: number;
  defaultTargetSec: number;
  shortFormMaxSec: number;
  maxTargetSec: number;
};

export async function getDurationRecommendation(
  projectId: string,
): Promise<ApiResult<DurationRecommendationResponse>> {
  return apiFetch(`/api/projects/${projectId}/duration-recommendation`);
}

export type ScriptDraftResponse = {
  draft: ScriptDraft;
  taskStatus?: string | null;
  taskStage?: string | null;
};

export async function getScriptDraft(
  generationId: string,
): Promise<ApiResult<ScriptDraftResponse>> {
  return apiFetch(`/api/generations/${generationId}/script-draft`);
}

export async function updateScriptDraft(
  generationId: string,
  body: { masterNarration?: string; storyboard?: ScriptDraft["storyboard"] },
): Promise<ApiResult<{ draft: ScriptDraft }>> {
  return apiFetch(`/api/generations/${generationId}/script-draft`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type ScriptDraftNlReviseResponse = {
  draft: ScriptDraft;
  revisionId: string;
  summary?: string;
};

export async function nlReviseScriptDraft(
  generationId: string,
  body: { scope: "master" | "storyboard"; instruction: string },
): Promise<ApiResult<ScriptDraftNlReviseResponse>> {
  return apiFetch(`/api/generations/${generationId}/script-draft/nl-revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function approveMasterScript(
  generationId: string,
): Promise<ApiResult<{ generationId: string; taskId: string; draft: ScriptDraft }>> {
  return apiFetch(`/api/generations/${generationId}/approve-master`, {
    method: "POST",
  });
}

export async function approveStoryboardScript(
  generationId: string,
): Promise<ApiResult<{ generationId: string; taskId: string; draft: ScriptDraft }>> {
  return apiFetch(`/api/generations/${generationId}/approve-storyboard`, {
    method: "POST",
  });
}

export type { ApiMeta, ApiResult };
