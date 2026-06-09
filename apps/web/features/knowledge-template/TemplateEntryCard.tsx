"use client";

import { Play, X } from "lucide-react";

import { SampleThumbnail } from "@/components/sample-thumbnail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { KnowledgeCategoryEntryCard } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

export type TemplateEntryRole = "primary" | "reference" | null;

type TemplateEntryCardProps = {
  entry: KnowledgeCategoryEntryCard;
  role: TemplateEntryRole;
  referenceIndex?: number;
  referencesFull: boolean;
  onSetPrimary: (entryId: string) => void;
  onToggleReference: (entryId: string) => void;
  onPreview: (entry: KnowledgeCategoryEntryCard) => void;
};

export function TemplateEntryCard({
  entry,
  role,
  referenceIndex,
  referencesFull,
  onSetPrimary,
  onToggleReference,
  onPreview,
}: TemplateEntryCardProps) {
  const disabled = !entry.importable;

  return (
    <article
      data-testid="template-entry-card"
      className={cn(
        "flex flex-col overflow-hidden rounded-2xl border bg-card shadow-sm transition-colors duration-200",
        role === "primary" && "border-primary border-l-4 bg-primary/5 ring-1 ring-primary/30",
        role === "reference" && "border-ai/40 bg-ai/[0.06] ring-1 ring-ai/20",
        role === null && "border-border",
        disabled && "opacity-55",
      )}
    >
      <div className="relative aspect-video w-full border-b border-border/50 bg-muted">
        <SampleThumbnail
          previewUrl={entry.previewUrl}
          posterUrl={entry.posterUrl}
          alt={entry.title}
          size="md"
          className="!h-full !w-full !rounded-none"
        />
        {entry.previewUrl && entry.importable ? (
          <button
            type="button"
            aria-label="预览样例视频"
            className="absolute inset-0 flex cursor-pointer items-center justify-center bg-black/20 opacity-0 transition-opacity hover:opacity-100"
            onClick={() => onPreview(entry)}
          >
            <span className="rounded-full bg-background/90 p-2">
              <Play className="h-5 w-5 text-primary" />
            </span>
          </button>
        ) : null}
        {role === "primary" ? (
          <Badge className="absolute left-3 top-3">主样例</Badge>
        ) : null}
        {role === "reference" ? (
          <Badge variant="ai" className="absolute left-3 top-3">
            参考 {referenceIndex}
          </Badge>
        ) : null}
        {disabled ? (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60 text-sm font-medium">
            暂不可用
          </div>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="space-y-1">
          <h3 className="font-serif text-base font-semibold leading-tight">{entry.title}</h3>
          <p className="text-xs text-muted-foreground">
            {entry.style}
            {entry.hookType ? ` · ${entry.hookType}` : ""}
          </p>
          <p className="truncate font-mono text-xs text-muted-foreground">{entry.slotPattern}</p>
        </div>
        <div className="mt-auto flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={role === "primary" ? "default" : "outline"}
            disabled={disabled}
            onClick={() => onSetPrimary(entry.entryId)}
          >
            {role === "primary" ? "已为主样例" : "设为主样例"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={role === "reference" ? "secondary" : "outline"}
            disabled={disabled || (referencesFull && role !== "reference")}
            title={
              referencesFull && role !== "reference" ? "最多 2 个参考样例" : entry.importBlockReason
            }
            onClick={() => onToggleReference(entry.entryId)}
          >
            {role === "reference" ? "取消参考" : "加为参考"}
          </Button>
        </div>
      </div>
    </article>
  );
}

type SelectedEntryChipProps = {
  entry: KnowledgeCategoryEntryCard;
  label: string;
  onRemove?: () => void;
};

export function SelectedEntryChip({ entry, label, onRemove }: SelectedEntryChipProps) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-background/80 p-2">
      <SampleThumbnail
        previewUrl={entry.previewUrl}
        posterUrl={entry.posterUrl}
        alt={entry.title}
        size="sm"
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="truncate text-sm">{entry.title}</p>
      </div>
      {onRemove ? (
        <button
          type="button"
          aria-label={`移除${label}`}
          className="cursor-pointer rounded p-1 text-muted-foreground hover:text-foreground"
          onClick={onRemove}
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}
