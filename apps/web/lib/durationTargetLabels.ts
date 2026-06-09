import type { GenerationStrategy } from "@videomaker/contracts";

export function formatDurationSec(sec: number): string {
  if (!Number.isFinite(sec) || sec <= 0) return "—";
  if (sec < 60) return `${Math.round(sec)} 秒`;
  const minutes = Math.floor(sec / 60);
  const remainder = Math.round(sec % 60);
  return remainder > 0 ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`;
}

export function generationStrategyLabel(_strategy: GenerationStrategy | undefined): string {
  return "分镜合成模式";
}

export function generationStrategyHint(_targetSec: number): string {
  return "确认分镜后按槽位补素材并合成完整时间线。";
}

export function scriptReviewGateLabel(stage: string | null | undefined): string {
  if (stage === "awaiting_master_review") return "总脚本审核";
  if (stage === "awaiting_storyboard_review") return "分镜脚本审核";
  return "脚本审核";
}
