"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { Loader2 } from "lucide-react";

import { SamplePreviewDialog } from "@/components/sample-preview-dialog";
import { SampleThumbnail } from "@/components/sample-thumbnail";
import type { SampleAnalysisFacts, TaskStage, VideoStructure } from "@videomaker/contracts";

import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KnowledgeDraftPanel } from "@/features/knowledge/KnowledgeDraftPanel";
import { sampleDisplayName } from "@/features/project-input/SampleVideoCard";
import { StructureEvidencePanel } from "@/features/structure-evidence/StructureEvidencePanel";
import type { ActiveSampleSummary } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type SampleAnalysisPanelProps = {
  projectId: string;
  samples: ActiveSampleSummary[];
  displayedSampleId: string | null;
  pendingSampleId?: string | null;
  onSelectSample: (sampleId: string) => void;
  structure: VideoStructure | null;
  sampleAnalysisFacts?: SampleAnalysisFacts | null;
  error?: string | null;
  highlightedSlotIds?: string[];
  onHighlightSlot?: (slotId: string) => void;
  analysisStage?: TaskStage;
  emptyMessage?: ReactNode;
};

function sortAnalyzedSamples(samples: ActiveSampleSummary[]): ActiveSampleSummary[] {
  return [...samples].sort((left, right) => {
    const leftBatch = left.batchCreatedAt ?? "";
    const rightBatch = right.batchCreatedAt ?? "";
    if (leftBatch !== rightBatch) {
      return rightBatch.localeCompare(leftBatch);
    }
    return right.id.localeCompare(left.id);
  });
}

function AnalyzedSampleListItem({
  sample,
  isDisplayed,
  isPending,
  onSelect,
  onPreview,
}: {
  sample: ActiveSampleSummary;
  isDisplayed: boolean;
  isPending: boolean;
  onSelect: () => void;
  onPreview: (sample: ActiveSampleSummary) => void;
}) {
  const title = sampleDisplayName(sample);

  return (
    <button
      type="button"
      className={cn(
        "flex w-full items-center gap-2 rounded-lg border px-2 py-2 text-left transition-colors",
        isDisplayed
          ? "border-primary border-l-4 bg-primary/5 ring-1 ring-primary/30"
          : isPending
            ? "border-primary/50 bg-muted/30"
            : "border-border bg-card hover:border-primary/40",
      )}
      onClick={onSelect}
      disabled={isPending}
    >
      <SampleThumbnail
        previewUrl={sample.previewUrl}
        posterUrl={sample.posterUrl}
        alt={title}
        size="xs"
        onPreviewClick={
          sample.previewUrl ? () => onPreview(sample) : undefined
        }
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{title}</p>
        <div className="flex items-center gap-1">
          {isPending ? (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
          ) : (
            <Badge variant="ai" className="text-[10px]">
              已分析
            </Badge>
          )}
        </div>
      </div>
    </button>
  );
}

export function SampleAnalysisPanel({
  projectId,
  samples,
  displayedSampleId,
  pendingSampleId = null,
  onSelectSample,
  structure,
  sampleAnalysisFacts = null,
  error = null,
  highlightedSlotIds = [],
  onHighlightSlot,
  analysisStage,
  emptyMessage = "暂无分析结果，请先完成样例分析。",
}: SampleAnalysisPanelProps) {
  const [previewSample, setPreviewSample] = useState<ActiveSampleSummary | null>(
    null,
  );
  const analyzed = sortAnalyzedSamples(
    samples.filter((sample) => sample.hasStructure && sample.status === "analyzed"),
  );
  const pendingSample =
    analyzed.find((sample) => sample.id === pendingSampleId) ?? null;
  const isSwitching =
    Boolean(pendingSampleId) && pendingSampleId !== displayedSampleId;
  const initialLoading = Boolean(pendingSampleId) && !structure;

  if (analyzed.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
          {samples.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              已有 {samples.length} 个样例待分析，请返回「录入」点击「开始样例分析」。
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              请先在「录入」上传样例视频并开始样例分析。
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
    <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)]">
      <Card className="flex h-fit flex-col xl:sticky xl:top-4 xl:max-h-[calc(100dvh-2rem)]">
        <CardContent className="space-y-3 p-4">
          <div>
            <p className="font-serif text-base font-semibold">已分析样例</p>
            <p className="text-xs text-muted-foreground">共 {analyzed.length} 个</p>
          </div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-y-contain">
            {analyzed.map((sample) => (
              <AnalyzedSampleListItem
                key={sample.id}
                sample={sample}
                isDisplayed={sample.id === displayedSampleId}
                isPending={sample.id === pendingSampleId}
                onSelect={() => onSelectSample(sample.id)}
                onPreview={setPreviewSample}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="min-w-0 space-y-4">
        {isSwitching && pendingSample && (
          <p className="text-xs text-muted-foreground" role="status">
            正在切换到 {sampleDisplayName(pendingSample)}…
          </p>
        )}

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {initialLoading && (
          <Card>
            <CardContent className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在加载样例分析详情…
            </CardContent>
          </Card>
        )}

        {!initialLoading && structure && displayedSampleId && (
          <div className="relative space-y-4">
            {isSwitching && (
              <div
                className="absolute inset-0 z-10 flex items-start justify-center rounded-lg bg-background/70 pt-16 backdrop-blur-[1px]"
                aria-live="polite"
                aria-busy="true"
              >
                <div className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm text-muted-foreground shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在加载新样例详情…
                </div>
              </div>
            )}
            <div
              className={cn(
                "space-y-4 transition-opacity duration-150",
                isSwitching && "pointer-events-none opacity-60",
              )}
            >
              <StructureEvidencePanel
                structure={structure}
                sampleAnalysisFacts={sampleAnalysisFacts}
                highlightedSlotIds={highlightedSlotIds}
                onHighlightSlot={onHighlightSlot}
                analysisStage={analysisStage}
                promoteAction={
                  <KnowledgeDraftPanel
                    projectId={projectId}
                    sampleId={displayedSampleId}
                    layout="inline"
                  />
                }
              />
              <details open className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                <summary className="cursor-pointer font-serif text-base font-semibold">
                  知识草稿详情
                </summary>
                <div className="mt-4">
                  <KnowledgeDraftPanel
                    projectId={projectId}
                    sampleId={displayedSampleId}
                    layout="card"
                  />
                </div>
              </details>
            </div>
          </div>
        )}

        {!initialLoading && !structure && !error && (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              请从左侧选择一个样例查看结构详情。
            </CardContent>
          </Card>
        )}
      </div>
    </div>
    <SamplePreviewDialog
      sample={previewSample}
      open={previewSample != null}
      onClose={() => setPreviewSample(null)}
    />
    </>
  );
}
