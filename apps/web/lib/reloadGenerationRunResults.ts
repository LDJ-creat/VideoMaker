import type { Dispatch, SetStateAction } from "react";

import type { GapReport, GenerationPlan } from "@videomaker/contracts";

import type {
  GenerationResponse,
  StructureProvenanceSummary,
} from "@/lib/apiClient";
import { getVariantLabel } from "@/lib/variantRegistry";

export type ActiveGenerationEntry = {
  generationId: string;
  variant: string;
  taskId: string;
  label: string;
  status?: string;
};

export async function fetchGenerationRunPlans(
  entries: ActiveGenerationEntry[],
  fetchGeneration: (generationId: string) => Promise<GenerationResponse>,
): Promise<Record<string, GenerationResponse> | null> {
  if (entries.length === 0) return null;

  const plans: Record<string, GenerationResponse> = {};
  for (const entry of entries) {
    try {
      plans[entry.generationId] = await fetchGeneration(entry.generationId);
    } catch {
      return null;
    }
  }
  return Object.keys(plans).length === entries.length ? plans : null;
}

export async function reloadGenerationRunPlansWithRetry(
  entries: ActiveGenerationEntry[],
  fetchGeneration: (generationId: string) => Promise<GenerationResponse>,
  options?: { maxAttempts?: number; delayMs?: number },
): Promise<Record<string, GenerationResponse> | null> {
  const maxAttempts = options?.maxAttempts ?? 12;
  const delayMs = options?.delayMs ?? 1500;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const plans = await fetchGenerationRunPlans(entries, fetchGeneration);
    if (plans) return plans;
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, delayMs);
    });
  }
  return null;
}

export function generationRunPlansAreLoaded(
  entries: ActiveGenerationEntry[],
  variantPlans: Record<string, GenerationPlan>,
): boolean {
  if (entries.length === 0) return true;
  return entries.every((entry) => Boolean(variantPlans[entry.generationId]));
}

export type GenerationRunGenerationSummary = {
  generationId: string;
  variant?: string;
  status?: string;
  taskId?: string | null;
  plan?: GenerationResponse;
};

type ApplyGenerationRunDetailSetters = {
  setVariantPlans: (plans: Record<string, GenerationPlan>) => void;
  setGenerationId: (id: string | null) => void;
  setGenerationPlan: (plan: GenerationPlan | null) => void;
  setActiveVariantGenerationId: (id: string | null) => void;
  setGapReport: (report: GapReport | null) => void;
  setGapApiPending: (pending: boolean) => void;
  setActiveGenerations: (entries: ActiveGenerationEntry[]) => void;
  setRenderVideoByGenerationId: Dispatch<SetStateAction<Record<string, string>>>;
};

export function buildActiveGenerationEntriesFromRun(
  generations: GenerationRunGenerationSummary[],
): ActiveGenerationEntry[] {
  return generations.map((entry) => {
    const variant = entry.variant ?? entry.plan?.variant ?? "default";
    return {
      generationId: entry.generationId,
      variant,
      taskId: entry.taskId ?? "",
      label: getVariantLabel(variant),
      status: entry.status,
    };
  });
}

export function applyGenerationRunDetail(
  data: {
    generations: GenerationRunGenerationSummary[];
    provenance?: StructureProvenanceSummary | null;
  },
  setters: ApplyGenerationRunDetailSetters,
): ActiveGenerationEntry[] {
  const entries = buildActiveGenerationEntriesFromRun(data.generations);
  const planMap: Record<string, GenerationPlan> = {};
  const renderVideos: Record<string, string> = {};

  for (const entry of data.generations) {
    if (!entry.plan) continue;
    planMap[entry.generationId] = entry.plan;
    if (entry.plan.renderVideoUrl) {
      renderVideos[entry.generationId] = entry.plan.renderVideoUrl;
    }
  }

  setters.setVariantPlans(planMap);
  setters.setRenderVideoByGenerationId((prev) => ({ ...prev, ...renderVideos }));
  setters.setActiveGenerations(entries);

  const primary =
    data.generations.find(
      (entry) => entry.status === "succeeded" && entry.plan != null,
    ) ??
    data.generations.find((entry) => entry.plan != null) ??
    data.generations[0];

  if (!primary) {
    setters.setGenerationId(null);
    setters.setActiveVariantGenerationId(null);
    setters.setGenerationPlan(null);
    setters.setGapReport(null);
    setters.setGapApiPending(false);
    return entries;
  }

  setters.setGenerationId(primary.generationId);
  setters.setActiveVariantGenerationId(primary.generationId);

  if (primary.plan) {
    setters.setGenerationPlan(primary.plan);
    const gap = primary.plan.gapReport;
    if (gap) {
      setters.setGapReport(gap);
      setters.setGapApiPending(false);
    } else {
      setters.setGapReport(null);
      setters.setGapApiPending(false);
    }
  } else {
    setters.setGenerationPlan(null);
    setters.setGapReport(null);
    setters.setGapApiPending(false);
  }

  return entries;
}
