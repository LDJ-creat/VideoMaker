"use client";

import type { ReactNode } from "react";

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

type SampleVideoCardProps = {
  sample: ActiveSampleSummary;
  selected?: boolean;
  compact?: boolean;
  className?: string;
  onSelect?: (sampleId: string) => void;
  footer?: ReactNode;
};

export function SampleVideoCard({
  sample,
  selected,
  compact = false,
  className,
  onSelect,
  footer,
}: SampleVideoCardProps) {
  const Wrapper = onSelect ? "button" : "div";
  const title = sampleDisplayName(sample);

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
      {sample.previewUrl ? (
        <video
          src={sample.previewUrl}
          controls
          className={cn(
            "w-full rounded-md bg-black",
            compact ? "max-h-28" : "max-h-36",
          )}
          onClick={(event) => event.stopPropagation()}
        />
      ) : (
        <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-border bg-muted/20 text-xs text-muted-foreground">
          {sample.status === "importing" ? "视频导入中…" : "暂无可预览视频"}
        </div>
      )}
      {!compact && (
        <p className="font-mono text-[10px] text-muted-foreground truncate">{sample.id}</p>
      )}
      {sample.sourceUrl && !compact && (
        <p className="text-xs text-muted-foreground truncate">来源：{sample.sourceUrl}</p>
      )}
      {footer}
    </Wrapper>
  );
}
