import type { GenerationStrategy } from "@videomaker/contracts";

export function formatDurationSec(sec: number): string {
  if (!Number.isFinite(sec) || sec <= 0) return "—";
  if (sec < 60) return `${Math.round(sec)} 秒`;
  const minutes = Math.floor(sec / 60);
  const remainder = Math.round(sec % 60);
  return remainder > 0 ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`;
}

export function generationStrategyLabel(strategy: GenerationStrategy | undefined): string {
  if (strategy === "short_form_direct") return "短视频直生成（≤60s）";
  if (strategy === "long_form_composed") return "长视频分镜合成（>60s）";
  return "待确认策略";
}

export function generationStrategyHint(
  targetSec: number,
  shortFormMaxSec: number,
): string {
  if (targetSec <= shortFormMaxSec) {
    return `目标 ${formatDurationSec(targetSec)}：确认脚本后将优先单次视频生成与精简分镜。`;
  }
  return `目标 ${formatDurationSec(targetSec)}：确认分镜后将按槽位补素材并合成完整时间线。`;
}

export function scriptReviewGateLabel(stage: string | null | undefined): string {
  if (stage === "awaiting_master_review") return "总脚本审核";
  if (stage === "awaiting_storyboard_review") return "分镜脚本审核";
  return "脚本审核";
}
