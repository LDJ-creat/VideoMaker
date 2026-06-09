import type { CompletionAction } from "@videomaker/contracts";

const NON_VISUAL_STRATEGIES = new Set(["tts"]);

/** Per-slot completionActions include visual gap fill + TTS; keep visual only. */
export function pickVisualCompletionAction(
  actions: CompletionAction[],
  slotId: string,
): CompletionAction | undefined {
  return actions.find((action) => {
    if (action.slotId !== slotId) return false;
    const provider = String(action.provider ?? "");
    const strategy = String(action.strategy ?? "");
    if (provider === "tts" || strategy === "tts") return false;
    if (NON_VISUAL_STRATEGIES.has(provider) || NON_VISUAL_STRATEGIES.has(strategy)) {
      return false;
    }
    return true;
  });
}

export function visualCompletionActions(
  actions: CompletionAction[],
): CompletionAction[] {
  return actions.filter((action) => {
    const provider = String(action.provider ?? "");
    const strategy = String(action.strategy ?? "");
    return provider !== "tts" && strategy !== "tts";
  });
}
