import type { AspectRatio } from "@videomaker/contracts";

export const ASPECT_RATIO_OPTIONS: AspectRatio[] = ["9:16", "16:9", "1:1"];

export function aspectRatioLabel(ratio: AspectRatio): string {
  if (ratio === "9:16") return "竖屏 9:16";
  if (ratio === "16:9") return "横屏 16:9";
  return "方形 1:1";
}

export function aspectRatioDefaultHint(): string {
  return "请在下方选择画幅比例";
}
