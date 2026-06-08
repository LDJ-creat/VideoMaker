import type { GenerationPlan } from "@videomaker/contracts";

import type { GenerationResponse } from "@/lib/apiClient";

export type ActiveGenerationEntry = {
  generationId: string;
  variant: string;
  taskId: string;
  label: string;
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
