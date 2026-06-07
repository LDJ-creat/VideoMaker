"use client";

import type { ReactNode } from "react";

import { SampleThumbnail, type SampleThumbnailSize } from "@/components/sample-thumbnail";
import { Badge } from "@/components/ui/badge";
import type { ActiveSampleSummary } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

export function sampleDisplayName(sample: ActiveSampleSummary): string {
  if (sample.fileName?.trim()) {
    return sample.fileName.trim();
  }
  if (sample.sourceUrl?.trim()) {
    try {
      return new URL(sample.sourceUrl).hostname;
    } catch {
      return sample.sourceUrl;
    }
  }
  return `样例 ${sample.id.slice(0, 8)}`;
}

function sampleStatusLabel(sample: ActiveSampleSummary): string {
  if (sample.hasStructure && sample.status === "analyzed") return "已分析";
  if (sample.status === "importing") return "导入中";
  if (sample.status === "analyzing") return "分析中";
  return sample.status;
}

type SampleVideoCardProps = {
  sample: ActiveSampleSummary;
  selected?: boolean;
  variant?: "default" | "compact" | "filmstrip";
  /** filmstrip 密度：compact 用于录入向导内嵌列表 */
  density?: "default" | "compact";
  className?: string;
  onSelect?: (sampleId: string) => void;
  onPreview?: (sample: ActiveSampleSummary) => void;
  footer?: ReactNode;
};

export function SampleVideoCard({
  sample,
  selected,
  variant = "default",
  density = "default",
  className,
  onSelect,
  onPreview,
  footer,
}: SampleVideoCardProps) {
  const title = sampleDisplayName(sample);

  if (variant === "filmstrip") {
    const isCompact = density === "compact";
    const thumbSize: SampleThumbnailSize = isCompact ? "sm" : "md";
    const shellClassName = cn(
      isCompact ? "rounded-md border" : "rounded-lg border",
      selected
        ? "border-primary border-l-4 bg-primary/5 ring-1 ring-primary/30"
        : "border-border",
      footer ? "w-full space-y-2 p-2" : isCompact ? "gap-2 p-1.5" : "gap-3 p-2",
      !footer && onSelect && "hover:border-primary/40",
      className,
    );
    const rowClassName = cn(
      "flex w-full items-center text-left transition-colors",
      isCompact ? "gap-2" : "gap-3",
    );
    const rowBody = (
      <>
        <SampleThumbnail
          previewUrl={sample.previewUrl}
          posterUrl={sample.posterUrl}
          alt={title}
          size={thumbSize}
          onPreviewClick={
            onPreview && sample.previewUrl ? () => onPreview(sample) : undefined
          }
        />
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className={cn("truncate font-medium", isCompact ? "text-xs" : "text-sm")}>
            {title}
          </p>
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "inline-block shrink-0 rounded-full",
                isCompact ? "h-1.5 w-1.5" : "h-2 w-2",
                sample.hasStructure && sample.status === "analyzed"
                  ? "bg-emerald-500"
                  : sample.status === "analyzing" || sample.status === "importing"
                    ? "bg-amber-500"
                    : "bg-muted-foreground/40",
              )}
              title={sampleStatusLabel(sample)}
            />
            <span className="truncate text-[11px] text-muted-foreground">
              {sampleStatusLabel(sample)}
            </span>
          </div>
        </div>
      </>
    );

    if (footer) {
      return (
        <div className={shellClassName}>
          {onSelect ? (
            <button
              type="button"
              className={cn(rowClassName, "rounded-md hover:bg-muted/40")}
              onClick={() => onSelect(sample.id)}
            >
              {rowBody}
            </button>
          ) : (
            <div className={rowClassName}>{rowBody}</div>
          )}
          {footer}
        </div>
      );
    }

    const Wrapper = onSelect ? "button" : "div";
    return (
      <Wrapper
        type={onSelect ? "button" : undefined}
        className={cn(shellClassName, "flex", rowClassName)}
        onClick={onSelect ? () => onSelect(sample.id) : undefined}
      >
        {rowBody}
      </Wrapper>
    );
  }

  const Wrapper = onSelect ? "button" : "div";

  return (
    <Wrapper
      type={onSelect ? "button" : undefined}
      className={cn(
        "w-full space-y-2 rounded-lg border p-3 text-left transition-colors",
        selected ? "border-primary ring-1 ring-primary/40" : "border-border",
        onSelect && "hover:border-primary/50",
        className,
      )}
      onClick={onSelect ? () => onSelect(sample.id) : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="truncate text-sm font-medium">{title}</span>
        <Badge variant="secondary">{sample.sourceKind}</Badge>
        <Badge variant="outline">{sample.status}</Badge>
        {sample.hasStructure && <Badge variant="ai">已分析</Badge>}
        {sample.uploadBatchId && (
          <Badge variant="outline">批次 {sample.uploadBatchId.slice(0, 6)}</Badge>
        )}
      </div>
      {variant !== "compact" && sample.previewUrl ? (
        <video
          src={sample.previewUrl}
          controls
          className="max-h-36 w-full rounded-md bg-black"
          onClick={(event) => event.stopPropagation()}
        />
      ) : variant === "compact" && sample.previewUrl ? (
        <video
          src={sample.previewUrl}
          muted
          playsInline
          preload="metadata"
          className="max-h-28 w-full rounded-md bg-black object-cover"
          onClick={(event) => event.stopPropagation()}
        />
      ) : !sample.previewUrl ? (
        <div className="flex h-16 items-center justify-center rounded-md border border-dashed border-border bg-muted/20 text-xs text-muted-foreground">
          {sample.status === "importing" ? "视频导入中…" : "暂无可预览视频"}
        </div>
      ) : null}
      {variant === "default" && (
        <p className="truncate font-mono text-[10px] text-muted-foreground">
          {sample.id}
        </p>
      )}
      {sample.sourceUrl && variant === "default" && (
        <p className="truncate text-xs text-muted-foreground">
          来源：{sample.sourceUrl}
        </p>
      )}
      {footer}
    </Wrapper>
  );
}
