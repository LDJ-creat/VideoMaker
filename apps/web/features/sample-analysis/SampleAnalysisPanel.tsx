"use client";

import type { ReactNode } from "react";

import { Loader2 } from "lucide-react";

import type { SampleAnalysisFacts, TaskStage, VideoStructure } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { KnowledgeDraftPanel } from "@/features/knowledge/KnowledgeDraftPanel";
import { sampleDisplayName } from "@/features/project-input/SampleVideoCard";
import { SampleAnalysisView } from "@/features/sample-analysis/SampleAnalysisView";
import { StructureEvidencePanel } from "@/features/structure-evidence/StructureEvidencePanel";
import type { ActiveSampleSummary, SampleKeyframeRecord } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

type SampleAnalysisPanelProps = {
  projectId: string;
  samples: ActiveSampleSummary[];
  displayedSampleId: string | null;
  pendingSampleId?: string | null;
  onSelectSample: (sampleId: string) => void;
  structure: VideoStructure | null;
  sampleAnalysisFacts?: SampleAnalysisFacts | null;
  sampleKeyframes: SampleKeyframeRecord[];
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
  onViewDetails,
}: {
  sample: ActiveSampleSummary;
  isDisplayed: boolean;
  isPending: boolean;
  onViewDetails: () => void;
}) {
  const title = sampleDisplayName(sample);

  return (
    <div
      className={cn(
        "rounded-lg border p-3 transition-colors",
        isDisplayed
          ? "border-primary bg-primary/5 ring-1 ring-primary/30"
          : isPending
            ? "border-primary/50 bg-muted/30"
            : "border-border bg-card hover:border-primary/40",
      )}
    >
      <div className="space-y-3">
        {sample.previewUrl ? (
          <video
            src={sample.previewUrl}
            controls
            playsInline
            preload="metadata"
            className="mx-auto aspect-[9/16] w-full max-w-[168px] rounded-md bg-black object-cover"
            title="点击播放样例视频"
            onClick={(event) => event.stopPropagation()}
            onPointerDown={(event) => event.stopPropagation()}
          />
        ) : (
          <div className="mx-auto flex aspect-[9/16] w-full max-w-[168px] items-center justify-center rounded-md border border-dashed border-border bg-muted/20 text-[10px] text-muted-foreground">
            无预览
          </div>
        )}
        <div className="min-w-0 space-y-2">
          <div>
            <p className="truncate text-sm font-medium">{title}</p>
            <p className="font-mono text-[10px] text-muted-foreground">
              {sample.id.slice(0, 8)}…
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            <Badge variant="ai">已分析</Badge>
            {sample.uploadBatchId && (
              <Badge variant="outline">批次 {sample.uploadBatchId.slice(0, 6)}</Badge>
            )}
          </div>
          <Button
            type="button"
            size="sm"
            variant={isDisplayed ? "secondary" : "outline"}
            className="w-full"
            onClick={onViewDetails}
            disabled={isDisplayed || isPending}
          >
            {isPending ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                加载中…
              </span>
            ) : isDisplayed ? (
              "当前查看中"
            ) : (
              "查看详情"
            )}
          </Button>
        </div>
      </div>
    </div>
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
  sampleKeyframes,
  error = null,
  highlightedSlotIds = [],
  onHighlightSlot,
  analysisStage,
  emptyMessage = "暂无分析结果，请先完成样例分析或加载演示数据。",
}: SampleAnalysisPanelProps) {
  const analyzed = sortAnalyzedSamples(
    samples.filter((sample) => sample.hasStructure && sample.status === "analyzed"),
  );
  const displayedSample =
    analyzed.find((sample) => sample.id === displayedSampleId) ?? null;
  const pendingSample =
    analyzed.find((sample) => sample.id === pendingSampleId) ?? null;
  const isSwitching =
    Boolean(pendingSampleId) && pendingSampleId !== displayedSampleId;
  const initialLoading = Boolean(pendingSampleId) && !structure;

  if (analyzed.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {emptyMessage}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]">
      <Card className="flex h-fit flex-col xl:sticky xl:top-4 xl:max-h-[calc(100dvh-2rem)]">
        <CardHeader className="shrink-0 pb-3">
          <CardTitle>已分析样例</CardTitle>
          <CardDescription>
            共 {analyzed.length} 个。结构证据、叙事分段与知识草稿均属于单个样例，请在此切换。
          </CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-y-contain">
          {analyzed.map((sample) => (
            <AnalyzedSampleListItem
              key={sample.id}
              sample={sample}
              isDisplayed={sample.id === displayedSampleId}
              isPending={sample.id === pendingSampleId}
              onViewDetails={() => onSelectSample(sample.id)}
            />
          ))}
        </CardContent>
      </Card>

      <div className="min-w-0 space-y-4">
            {displayedSample && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">当前详情所属样例</p>
              <p className="truncate text-sm font-medium">
                {sampleDisplayName(displayedSample)}
              </p>
              <p className="font-mono text-[10px] text-muted-foreground">
                {displayedSample.id}
              </p>
              {sampleAnalysisFacts?.structureAnalysisRoute === "direct_multimodal" ? (
                <div className="mt-1">
                  <Badge variant="secondary">直连多模态分析</Badge>
                </div>
              ) : null}
              {isSwitching && pendingSample && (
                <p className="mt-1 text-xs text-muted-foreground">
                  正在切换到 {sampleDisplayName(pendingSample)}…
                </p>
              )}
            </div>
            <Badge variant="ai">{isSwitching ? "切换中" : "查看中"}</Badge>
          </div>
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
                projectId={projectId}
                sampleId={displayedSampleId}
                keyframes={sampleKeyframes}
                highlightedSlotIds={highlightedSlotIds}
                onHighlightSlot={onHighlightSlot}
                analysisStage={analysisStage}
              />
              {sampleAnalysisFacts?.audioProfile ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">音频事实</CardTitle>
                    <CardDescription>
                      来自 sample-analysis.json 的确定性音频画像
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2 text-sm text-muted-foreground">
                    <Badge variant="secondary">
                      口播 {sampleAnalysisFacts.audioProfile.hasVoiceover ? "有" : "无"}
                    </Badge>
                    <Badge variant="secondary">
                      BGM {sampleAnalysisFacts.audioProfile.hasBgm ? "疑似有" : "无"}
                    </Badge>
                    {sampleAnalysisFacts.audioProfile.tempoBpm != null ? (
                      <Badge variant="outline">
                        节奏约 {sampleAnalysisFacts.audioProfile.tempoBpm} BPM
                      </Badge>
                    ) : null}
                    <Badge variant="outline">
                      口播覆盖{" "}
                      {(
                        sampleAnalysisFacts.audioProfile.metrics.voiceoverCoveragePct *
                        100
                      ).toFixed(0)}
                      %
                    </Badge>
                  </CardContent>
                </Card>
              ) : null}
              <SampleAnalysisView structure={structure} />
              <KnowledgeDraftPanel
                projectId={projectId}
                sampleId={displayedSampleId}
              />
            </div>
          </div>
        )}

        {!initialLoading && !structure && !error && (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              请从左侧选择一个样例并点击「查看详情」。
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
