export type UsageUnitsKind = "tokens" | "chars" | "images" | "video_seconds";

export type UsageUnits = {
  kind: UsageUnitsKind;
  prompt?: number;
  completion?: number;
  total?: number;
  chars?: number;
  images?: number;
  calls?: number;
  requestedDurationSec?: number;
  actualDurationSec?: number;
};

export type BillingUnit = "tokens" | "chars" | "images" | "video_seconds";

export type EvaluationInputMode = "sample_migration" | "knowledge_guided" | "greenfield";

export type EvaluationModule = "core" | "migration" | "knowledge_fit";

export type EvaluationProfile = {
  inputMode: EvaluationInputMode;
  enabledModules: EvaluationModule[];
  referenceStructureId?: string;
  knowledgeEntryId?: string;
  variantId?: string;
};

export type StageTimingStatus = "completed" | "paused" | "failed" | "running";
export type StageTimingKind = "active" | "human_gate";

export type StageTimingBreakdown = {
  slotId: string;
  durationMs: number;
};

export type StageTiming = {
  stage: string;
  startedAt?: string;
  endedAt?: string;
  durationMs: number;
  status: StageTimingStatus;
  kind?: StageTimingKind;
  breakdown?: StageTimingBreakdown[];
};

export type CategoryUsage = {
  billingUnit: BillingUnit;
  calls: number;
  latencyMs: number;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  totalChars?: number;
  successfulImages?: number;
  failedCalls?: number;
};

export type VideoGenJobUsage = {
  jobId: string;
  slotId?: string;
  model?: string;
  requestedDurationSec?: number;
  actualDurationSec?: number;
  outputBytes?: number;
  latencyMs: number;
};

export type VideoCategoryUsage = {
  billingUnit: "video_seconds";
  successfulJobs: number;
  totalDurationSec: number;
  requestedDurationSec?: number;
  latencyMs: number;
  jobs?: VideoGenJobUsage[];
};

export type ObservabilityWallClock = {
  totalMs: number;
  queuedMs?: number;
  activeMs?: number;
  humanWaitMs?: number;
  startedAt?: string;
  endedAt?: string;
};

export type ObservabilityTiming = {
  wallClock: ObservabilityWallClock;
  stages: StageTiming[];
  modelLatency: Partial<Record<keyof UsageByCategory, number>>;
};

export type UsageByCategory = {
  text_chat?: CategoryUsage;
  vision_chat?: CategoryUsage;
  tts?: CategoryUsage;
  image_gen?: CategoryUsage;
  video_gen?: VideoCategoryUsage;
};

export type EstimatedCostUsd = {
  total: number;
  byCategory?: Record<string, number>;
  priceSource?: string;
  confidence?: "estimate" | "partial" | "unknown";
};

export type ObservabilitySummary = {
  incomplete?: boolean;
  warnings?: string[];
  notes?: string[];
  usageByCategory: UsageByCategory;
  timing: ObservabilityTiming;
  estimatedCostUsd?: EstimatedCostUsd;
};

export type EvaluationVerdictStatus = "pass" | "warn" | "block" | "partial";

export type EvaluationVerdict = {
  status: EvaluationVerdictStatus;
  blockingIssues?: string[];
  warnings?: string[];
};

export type EvaluationScores = {
  core?: {
    weighted?: number;
    technical?: number | null;
    plan?: number;
    perceptual?: number;
  };
  migration?: Record<string, number | undefined> & { weighted?: number };
  knowledgeFit?: Record<string, number | undefined> & { weighted?: number };
};

export type EvaluationReport = {
  version: "1.0";
  generationId: string;
  projectId?: string;
  taskId?: string;
  evaluatedAt: string;
  partial?: boolean;
  profile: EvaluationProfile;
  verdict: EvaluationVerdict;
  scores?: EvaluationScores;
  modules?: Record<string, unknown>;
  observability: ObservabilitySummary;
};
