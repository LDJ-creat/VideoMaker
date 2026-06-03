"use client";

import { ImageIcon } from "lucide-react";
import Image from "next/image";

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
  const { segment, transcriptExcerpt, keyframeLabel, keyframePreviewUrl, shotRanges } =
    view;
  const showIntent =
    segment.intent.trim().length > 0 &&
    !isDuplicateText(segment.role, segment.intent);

  return (
    <button
      type="button"
      className={cn(
        "w-full rounded-lg border border-border bg-muted/20 p-4 text-left transition-colors hover:bg-muted/40",
        highlighted && "border-ai/50 bg-ai/5",
      )}
      onClick={onSelect}
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
        <div
          className="relative flex h-16 w-full items-center justify-center overflow-hidden rounded-md border border-dashed border-border bg-background/60 text-muted-foreground"
          aria-label={keyframeLabel ?? "关键帧占位"}
          title={keyframeLabel}
        >
          {keyframePreviewUrl ? (
            <Image
              src={keyframePreviewUrl}
              alt={keyframeLabel ?? `${segment.role} 关键帧`}
              fill
              className="object-cover"
              sizes="96px"
              unoptimized
            />
          ) : (
            <ImageIcon className="h-5 w-5" aria-hidden />
          )}
        </div>

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
    </button>
  );
}
