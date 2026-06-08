import type { AspectRatio } from "@videomaker/contracts";

export const ASPECT_RATIO_OPTIONS: AspectRatio[] = ["9:16", "16:9", "1:1"];

export function aspectRatioLabel(ratio: AspectRatio): string {
  if (ratio === "9:16") return "竖屏 9:16";
  if (ratio === "16:9") return "横屏 16:9";
  return "方形 1:1";
}

export function defaultAspectRatioForDuration(
  targetSec: number,
  shortFormMaxSec = 60,
): AspectRatio {
  return targetSec <= shortFormMaxSec ? "9:16" : "16:9";
}

export function aspectRatioDefaultHint(
  targetSec: number,
  shortFormMaxSec: number,
): string {
  const ratio = defaultAspectRatioForDuration(targetSec, shortFormMaxSec);
  return `根据目标时长默认 ${aspectRatioLabel(ratio)}`;
}
