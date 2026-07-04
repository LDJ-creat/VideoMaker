import type { CompletionAction } from "@videomaker/contracts";

import { pickVisualCompletionAction } from "@/features/structure-migration/pickVisualCompletionAction";

const PROVIDER_LABEL_KEYS = [
  "stock_media_search",
  "hyperframes_material",
  "image_generation",
  "video_generation",
  "asset_reuse",
] as const;

/**
 * Resolve ordered visual completion providers for a slot (e.g. Pexels + HyperFrames finish).
 */
export function resolveCompletionProviderChain(
  actions: CompletionAction[],
  slotId: string,
): string[] {
  const visual = actions.filter((action) => {
    if (action.slotId !== slotId) return false;
    const provider = String(action.provider ?? "");
    const strategy = String(action.strategy ?? "");
    return provider !== "tts" && strategy !== "tts";
  });

  const providers: string[] = [];
  const seen = new Set<string>();

  const ordered = [...visual].sort((left, right) => {
    const leftFinish = left.id?.endsWith("-finish") ? 1 : 0;
    const rightFinish = right.id?.endsWith("-finish") ? 1 : 0;
    return leftFinish - rightFinish;
  });

  for (const action of ordered) {
    const provider = String(action.provider ?? action.strategy ?? "").trim();
    if (!provider || provider === "tts" || seen.has(provider)) continue;
    seen.add(provider);
    providers.push(provider);
  }

  if (providers.length > 0) {
    return providers.sort((left, right) => {
      const leftIdx = PROVIDER_LABEL_KEYS.indexOf(left as (typeof PROVIDER_LABEL_KEYS)[number]);
      const rightIdx = PROVIDER_LABEL_KEYS.indexOf(right as (typeof PROVIDER_LABEL_KEYS)[number]);
      const safeLeft = leftIdx === -1 ? PROVIDER_LABEL_KEYS.length : leftIdx;
      const safeRight = rightIdx === -1 ? PROVIDER_LABEL_KEYS.length : rightIdx;
      return safeLeft - safeRight;
    });
  }

  const primary = pickVisualCompletionAction(actions, slotId);
  if (primary?.provider) return [primary.provider];
  if (primary?.strategy) return [primary.strategy];
  return [];
}
