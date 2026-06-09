"use client";

import type { StoryboardScene } from "@videomaker/contracts";
import { Film, ImageIcon } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { GeneratedAssetBadge } from "@/features/aigc-preview/GeneratedAssetBadge";
import type { StoryboardSceneMedia } from "@/features/master-narration/resolveStoryboardSceneMedia";
import { scriptBelongsToMaster } from "@/features/master-narration/resolveMasterNarration";
import { cn } from "@/lib/utils";

const KNOWN_MEDIA_PROVIDERS = new Set([
  "asset_reuse",
  "stock_media_search",
  "hyperframes_material",
  "image_generation",
  "video_generation",
  "tts",
  "text_completion",
  "packaging_completion",
]);

type StoryboardSceneCardProps = {
  scene: StoryboardScene;
  index: number;
  media: StoryboardSceneMedia;
  master: string;
  roleLabel?: string;
  visualIntent?: string;
  scriptIntent?: string;
  userAssetId?: string | null;
  userAssetSummary?: string | null;
  gapSummary?: string | null;
  completionProvider?: string | null;
};

export function StoryboardSceneCard({
  scene,
  index,
  media,
  master,
  roleLabel,
  visualIntent,
  scriptIntent,
  userAssetId,
  userAssetSummary,
  gapSummary,
  completionProvider,
}: StoryboardSceneCardProps) {
  const [mediaFailed, setMediaFailed] = useState(false);
  const script = scene.script.trim();
  const aligned = !script || !master || scriptBelongsToMaster(script, master);
  const showMedia = Boolean(media.url) && !mediaFailed;
  const visualProvider =
    completionProvider && KNOWN_MEDIA_PROVIDERS.has(completionProvider)
      ? completionProvider
      : media.provider && KNOWN_MEDIA_PROVIDERS.has(media.provider)
        ? media.provider
        : completionProvider ?? media.provider;

  return (
    <div
      className="rounded-lg border border-border p-3"
      data-testid={`narration-scene-${scene.id}`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">#{index + 1}</Badge>
          {roleLabel ? <Badge variant="outline">{roleLabel}</Badge> : null}
          <span className="font-mono text-xs text-muted-foreground">
            {scene.startSec}–{scene.endSec}s
          </span>
          {!aligned ? (
            <Badge variant="destructive">与全片口播未对齐</Badge>
          ) : null}
        </div>
        <span className="font-mono text-xs text-muted-foreground">{scene.slotId}</span>
      </div>

      {(visualIntent || scriptIntent || userAssetId || userAssetSummary || gapSummary) && (
        <dl className="mb-3 grid gap-2 rounded-md border border-border/60 bg-muted/10 p-3 text-sm">
          {visualIntent ? (
            <MigrationField label="结构意图" value={visualIntent} hint={scriptIntent} />
          ) : null}
          <MigrationField
            label="用户素材"
            value={
              userAssetId
                ? `复用 ${userAssetId}`
                : userAssetSummary ?? "未匹配到可用素材"
            }
            hint={userAssetId && userAssetSummary ? userAssetSummary : undefined}
          />
          {gapSummary && !userAssetId ? (
            <MigrationField label="缺口说明" value={gapSummary} />
          ) : null}
        </dl>
      )}

      <div className="grid gap-3 md:grid-cols-[minmax(0,280px)_1fr]">
        <div
          className={cn(
            "relative overflow-hidden rounded-md border border-border bg-black/90",
            showMedia
              ? "aspect-video"
              : "flex min-h-[140px] items-center justify-center bg-muted/30",
          )}
          data-testid={`scene-media-${scene.id}`}
        >
          {showMedia && media.kind === "video" ? (
            <video
              src={media.url!}
              controls
              playsInline
              preload="metadata"
              className="h-full w-full object-contain"
              onError={() => setMediaFailed(true)}
            />
          ) : showMedia && media.kind === "image" ? (
            <Image
              src={media.url!}
              alt={scene.visual || `分镜 ${index + 1}`}
              fill
              className="object-contain"
              sizes="280px"
              unoptimized
              onError={() => setMediaFailed(true)}
            />
          ) : (
            <div className="flex flex-col items-center gap-2 px-4 py-6 text-center text-muted-foreground">
              {media.kind === "video" || scene.source === "generated" ? (
                <Film className="h-8 w-8" aria-hidden />
              ) : (
                <ImageIcon className="h-8 w-8" aria-hidden />
              )}
              <p className="text-xs">分镜素材预览不可用</p>
              <p className="line-clamp-3 text-xs">{media.caption || scene.visual}</p>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {visualProvider && KNOWN_MEDIA_PROVIDERS.has(visualProvider) ? (
              <GeneratedAssetBadge provider={visualProvider} />
            ) : null}
            <span className="text-xs text-muted-foreground">视觉素材来源</span>
          </div>
          <p className="text-sm text-muted-foreground">{scene.visual}</p>
          <div className="rounded-md border border-dashed border-border bg-muted/20 px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">分镜口播</p>
            <p className="text-sm font-medium leading-relaxed">
              {script || "（本段无口播）"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function MigrationField({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[72px_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="space-y-1">
        <p className="text-sm text-foreground">{value}</p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </dd>
    </div>
  );
}
