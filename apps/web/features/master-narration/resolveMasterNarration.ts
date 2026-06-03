import type { GenerationPlan, StoryboardScene } from "@videomaker/contracts";

export function resolveMasterNarration(plan: GenerationPlan): string {
  const master = plan.masterNarration?.trim();
  if (master) {
    return master;
  }
  return deriveMasterFromStoryboard(plan.storyboard);
}

export function deriveMasterFromStoryboard(storyboard: StoryboardScene[]): string {
  return [...storyboard]
    .sort((left, right) => left.startSec - right.startSec)
    .map((scene) => scene.script.trim())
    .filter(Boolean)
    .join("");
}

export function scriptBelongsToMaster(script: string, master: string): boolean {
  const normalizedScript = script.replace(/\s+/g, "");
  const normalizedMaster = master.replace(/\s+/g, "");
  if (!normalizedScript || !normalizedMaster) {
    return false;
  }
  return normalizedMaster.includes(normalizedScript);
}

export function estimateSpeechDurationSec(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) {
    return 0;
  }
  const cjkCount = (trimmed.match(/[\u4e00-\u9fff]/g) ?? []).length;
  const otherCount = trimmed.length - cjkCount;
  return Math.max(1, Math.round(cjkCount / 4 + otherCount / 12));
}
