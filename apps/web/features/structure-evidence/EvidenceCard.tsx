"use client";

import { useState } from "react";

import { ImageIcon, ZoomIn } from "lucide-react";
import Image from "next/image";

import { ImageLightbox } from "@/components/ImageLightbox";
import { Badge } from "@/components/ui/badge";
import { isDuplicateText } from "@/lib/keyframePreview";
import { cn } from "@/lib/utils";

import type { SegmentEvidenceView } from "./StructureEvidencePanel";

type EvidenceCardProps = {
  view: SegmentEvidenceView;
  highlighted?: boolean;
  onSelect?: () => void;
};

export function EvidenceCard({ view, highlighted, onSelect }: EvidenceCardProps) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const { segment, transcriptExcerpt, keyframeLabel, keyframePreviewUrl, shotRanges } =
    view;
  const showIntent =
    segment.intent.trim().length > 0 &&
    !isDuplicateText(segment.role, segment.intent);

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        className={cn(
          "w-full cursor-pointer rounded-lg border border-border bg-muted/20 p-4 text-left transition-colors hover:bg-muted/40",
          highlighted && "border-ai/50 bg-ai/5",
        )}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect?.();
          }
        }}
        data-testid={`evidence-card-${segment.id}`}
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline">{segment.role}</Badge>
            <span className="font-mono text-xs text-muted-foreground">
              {segment.startSec}–{segment.endSec}s
            </span>
          </div>
          {showIntent ? (
            <span className="text-xs text-muted-foreground">{segment.intent}</span>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-[96px_1fr]">
          {keyframePreviewUrl ? (
            <button
              type="button"
              className="group relative flex h-16 w-full shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-background/60 text-muted-foreground transition-colors hover:border-primary/50"
              aria-label={`放大查看 ${keyframeLabel ?? `${segment.role} 关键帧`}`}
              title="点击放大关键帧"
              onClick={(event) => {
                event.stopPropagation();
                setPreviewOpen(true);
              }}
            >
              <Image
                src={keyframePreviewUrl}
                alt={keyframeLabel ?? `${segment.role} 关键帧`}
                fill
                className="object-cover transition-transform group-hover:scale-105"
                sizes="96px"
                unoptimized
              />
              <span className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/25">
                <ZoomIn className="h-4 w-4 text-white opacity-0 transition-opacity group-hover:opacity-100" />
              </span>
            </button>
          ) : (
            <div
              className="relative flex h-16 w-full items-center justify-center overflow-hidden rounded-md border border-dashed border-border bg-background/60 text-muted-foreground"
              aria-label={keyframeLabel ?? "关键帧占位"}
              title={keyframeLabel}
            >
              <ImageIcon className="h-5 w-5" aria-hidden />
            </div>
          )}

          <div className="space-y-2 text-sm">
            <p className="font-medium">{segment.visualSummary}</p>
            {transcriptExcerpt ? (
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">转写：</span>
                {transcriptExcerpt}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">暂无转写摘录</p>
            )}
            {keyframeLabel && !keyframePreviewUrl ? (
              <p className="text-xs text-muted-foreground">关键帧：{keyframeLabel}</p>
            ) : null}
            {shotRanges.length > 0 && (
              <p className="font-mono text-xs text-muted-foreground">
                镜头：{" "}
                {shotRanges
                  .map((shot) => `${shot.startSec}–${shot.endSec}s`)
                  .join(" · ")}
              </p>
            )}
          </div>
        </div>
      </div>

      {keyframePreviewUrl ? (
        <ImageLightbox
          src={keyframePreviewUrl}
          alt={keyframeLabel ?? `${segment.role} 关键帧`}
          caption={keyframeLabel ?? segment.visualSummary}
          open={previewOpen}
          onClose={() => setPreviewOpen(false)}
        />
      ) : null}
    </>
  );
}
