"use client";

import type { CompletionProvider, GeneratedBy } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type GeneratedAssetProvider =
  | CompletionProvider
  | "hyperframes_material"
  | "image_generation"
  | "video_generation"
  | "tts";

const PROVIDER_LABELS: Record<string, string> = {
  image_generation: "AI 生图",
  video_generation: "AI 生视频",
  tts: "AI 配音",
  hyperframes_material: "HyperFrames",
  packaging_completion: "包装补全",
  text_completion: "文案补全",
  asset_reuse: "素材复用",
  stock_media_search: "Pexels 素材",
};

type GeneratedAssetBadgeProps = {
  provider: GeneratedAssetProvider | string;
  generatedBy?: string | GeneratedBy;
  className?: string;
};

function formatTooltip(
  provider: string,
  generatedBy?: string | GeneratedBy,
): string {
  if (typeof generatedBy === "string") {
    return generatedBy;
  }
  if (generatedBy && typeof generatedBy === "object") {
    const parts = [
      generatedBy.photographer && `摄影师 ${generatedBy.photographer}`,
      generatedBy.model && `模型 ${generatedBy.model}`,
      generatedBy.template && `模板 ${generatedBy.template}`,
      generatedBy.promptVersion && `prompt ${generatedBy.promptVersion}`,
      generatedBy.pageUrl,
    ].filter(Boolean) as string[];
    if (parts.length > 0) {
      return parts.join(" · ");
    }
    if (generatedBy.provider) {
      return generatedBy.provider;
    }
  }
  return provider;
}

export function GeneratedAssetBadge({
  provider,
  generatedBy,
  className,
}: GeneratedAssetBadgeProps) {
  const label = PROVIDER_LABELS[provider] ?? provider;
  const tooltip = formatTooltip(provider, generatedBy);

  return (
    <Badge
      variant="ai"
      className={cn("text-[10px] font-normal", className)}
      title={tooltip}
      data-testid="generated-asset-badge"
    >
      {label}
    </Badge>
  );
}

export function resolveClipProvider(
  generatedBy?: string | GeneratedBy,
): string | undefined {
  if (!generatedBy) return undefined;
  if (typeof generatedBy === "string") return generatedBy;
  return generatedBy.provider;
}
