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
};

export function StoryboardSceneCard({
  scene,
  index,
  media,
  master,
}: StoryboardSceneCardProps) {
  const [mediaFailed, setMediaFailed] = useState(false);
  const script = scene.script.trim();
  const aligned = !script || !master || scriptBelongsToMaster(script, master);
  const showMedia = Boolean(media.url) && !mediaFailed;

  return (
    <div
      className="rounded-lg border border-border p-3"
      data-testid={`narration-scene-${scene.id}`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">#{index + 1}</Badge>
          <span className="font-mono text-xs text-muted-foreground">
            {scene.startSec}–{scene.endSec}s
          </span>
          <Badge variant="outline">{scene.source}</Badge>
          {!aligned ? (
            <Badge variant="destructive">与全片口播未对齐</Badge>
          ) : null}
        </div>
        <span className="font-mono text-xs text-muted-foreground">{scene.slotId}</span>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,280px)_1fr]">
        <div
          className={cn(
            "relative overflow-hidden rounded-md border border-border bg-black/90",
            showMedia ? "aspect-video" : "flex min-h-[140px] items-center justify-center bg-muted/30",
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
            {media.provider && KNOWN_MEDIA_PROVIDERS.has(media.provider) ? (
              <GeneratedAssetBadge provider={media.provider} />
            ) : null}
            <span className="text-xs text-muted-foreground">画面意图</span>
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
