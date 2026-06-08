import type { GenerationPlan } from "@videomaker/contracts";

import type { GenerationResponse } from "@/lib/apiClient";

/** Resolve playable MP4 URL from API fields or workbench cache. */
export function resolveRenderVideoUrl(
  plan: GenerationPlan | null | undefined,
  renderVideoByGenerationId: Record<string, string>,
): string | undefined {
  if (!plan?.id) return undefined;
  const cached = renderVideoByGenerationId[plan.id]?.trim();
  if (cached) return cached;
  const fromPlan = (plan as GenerationResponse).renderVideoUrl?.trim();
  return fromPlan || undefined;
}
