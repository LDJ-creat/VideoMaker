"use client";

import { useEffect, useState } from "react";

import type { NarrativeSegment, SampleAnalysisFacts, VideoStructure } from "@videomaker/contracts";
import type { TaskStage } from "@videomaker/contracts";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NarrativeTimeline } from "@/features/structure-evidence/NarrativeTimeline";
import { SegmentDetailPanel } from "@/features/structure-evidence/SegmentDetailPanel";
import { StructureHero } from "@/features/structure-evidence/StructureHero";
import {
  audioFieldLabel,
  contentCategoryLabel,
  outlinePhaseLabel,
  primaryIntentLabel,
  STRUCTURE_V3_TRACK_LABELS,
  tempoLabel,
  transferFieldLabel,
  verbalFieldLabel,
  visualDensityLabel,
  visualFieldLabel,
} from "@/lib/structureV3Labels";
import { cn } from "@/lib/utils";

import { EvidenceCard } from "./EvidenceCard";

export type SegmentEvidenceView = {
  segment: NarrativeSegment;
  transcriptExcerpt?: string;
  ocrExcerpts?: string[];
  audioSummary?: string;
  shotRanges: Array<{ startSec: number; endSec: number }>;
  relatedSlotIds: string[];
};

const ANALYSIS_STAGES: TaskStage[] = ["extracting_structure", "running_agent"];

type StructureEvidencePanelProps = {
  structure: VideoStructure;
  sampleAnalysisFacts?: SampleAnalysisFacts | null;
  highlightedSlotIds?: string[];
  onHighlightSlot?: (slotId: string) => void;
  analysisStage?: TaskStage | null;
  promoteAction?: React.ReactNode;
  showAllSegments?: boolean;
};

export function buildSegmentEvidenceViews(
  structure: VideoStructure,
): SegmentEvidenceView[] {
  return structure.narrative.segments.map((segment) => {
    const relatedSlotIds = structure.slots
      .filter((slot) => slot.segmentId === segment.id)
      .map((slot) => slot.id);

    const segmentEvidence = structure.evidence.filter(
      (item) =>
        item.targetId === segment.id || relatedSlotIds.includes(item.targetId),
    );

    const asrEvidence = segmentEvidence.find((item) => item.source === "asr");
    const transcriptExcerpt =
      asrEvidence?.excerpt?.trim() ||
      asrEvidence?.summary;

    const ocrExcerpts = segmentEvidence
      .filter((item) => item.source === "ocr")
      .map((item) => item.excerpt?.trim() || item.summary)
      .filter(Boolean);
    if (ocrExcerpts.length === 0 && segment.visualSpec?.onScreenText?.length) {
      ocrExcerpts.push(...segment.visualSpec.onScreenText);
    }

    const audioEvidence = segmentEvidence.find((item) => item.source === "audio");
    const audioSummary = audioEvidence?.summary;

    const shotRanges = structure.rhythm.shotBoundaries.filter(
      (shot) => shot.startSec < segment.endSec && shot.endSec > segment.startSec,
    );

    return {
      segment,
      transcriptExcerpt,
      ocrExcerpts,
      audioSummary,
      shotRanges,
      relatedSlotIds,
    };
  });
}

export function StructureV3TrackPanel({ structure }: { structure: VideoStructure }) {
  const { context, verbal, visual, audio, transfer } = structure;

  return (
    <Tabs defaultValue="verbal" className="w-full" data-testid="structure-v3-tracks">
      <TabsList className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-4">
        {(Object.keys(STRUCTURE_V3_TRACK_LABELS) as Array<keyof typeof STRUCTURE_V3_TRACK_LABELS>).map(
          (track) => (
            <TabsTrigger key={track} value={track} className="text-xs sm:text-sm">
              {STRUCTURE_V3_TRACK_LABELS[track]}
            </TabsTrigger>
          ),
        )}
      </TabsList>

      <TabsContent value="verbal" className="mt-4 space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-border bg-muted/10 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {verbalFieldLabel("hookTemplate")}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-foreground">
              {verbal.hookTemplate || "—"}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-muted/10 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {verbalFieldLabel("ctaMechanism")}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-foreground">
              {verbal.ctaMechanism || "—"}
            </p>
          </div>
        </div>

        {verbal.outlineTimeline?.length ? (
          <div className="rounded-xl border border-border bg-muted/10 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              口播节奏时间线
            </p>
            <div className="mt-3 flex h-2 w-full overflow-hidden rounded-full bg-muted/40">
              {verbal.outlineTimeline.map((phase) => {
                const span = Math.max(phase.endSec - phase.startSec, 0.1);
                const widthPct =
                  structure.metadata.durationSec > 0
                    ? (span / structure.metadata.durationSec) * 100
                    : 100 / verbal.outlineTimeline!.length;
                return (
                  <span
                    key={`${phase.phase}-${phase.startSec}`}
                    className="h-full bg-primary/50 first:rounded-l-full last:rounded-r-full"
                    style={{ width: `${widthPct}%` }}
                    title={`${outlinePhaseLabel(phase.phase)} ${phase.startSec}–${phase.endSec}s`}
                  />
                );
              })}
            </div>
            <ul className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {verbal.outlineTimeline.map((phase) => (
                <li
                  key={`card-${phase.phase}-${phase.startSec}`}
                  className="rounded-lg border border-border/60 bg-card/60 px-3 py-2"
                >
                  <p className="text-sm font-medium text-foreground">
                    {outlinePhaseLabel(phase.phase)}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {phase.startSec}–{phase.endSec}s · {(phase.sharePct * 100).toFixed(0)}%
                  </p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </TabsContent>

      <TabsContent value="visual" className="mt-4 grid gap-4 sm:grid-cols-2">
        {visual?.cutRateProfile ? (
          <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {visualFieldLabel("cutRateProfile")}
            </p>
            <p className="mt-2 text-foreground">
              均镜 {visual.cutRateProfile.avgShotSec ?? "—"}s · 开场{" "}
              {visual.cutRateProfile.openingCutRate ?? "—"}
            </p>
          </div>
        ) : null}
        {visual?.packagingSpec ? (
          <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {visualFieldLabel("packagingSpec")}
            </p>
            <p className="mt-2 text-foreground">
              密度 {visualDensityLabel(visual.packagingSpec.visualDensity)} ·{" "}
              {visual.packagingSpec.summary ?? "—"}
            </p>
          </div>
        ) : null}
      </TabsContent>

      <TabsContent value="audio" className="mt-4">
        <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm">
          {audio?.voProfile ? (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {audioFieldLabel("voProfile")}
              </p>
              <p className="mt-2 text-foreground">
                {audio.voProfile.persona ?? "—"} / {tempoLabel(audio.voProfile.pace)} /{" "}
                {audio.voProfile.energy ?? "—"}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">暂无口播画像</p>
          )}
        </div>
      </TabsContent>

      <TabsContent value="transfer" className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            类型
          </p>
          <p className="mt-2 text-foreground">
            {contentCategoryLabel(context.contentCategory)} ·{" "}
            {primaryIntentLabel(context.primaryIntent)}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {transferFieldLabel("differentiationLever")}
          </p>
          <p className="mt-2 text-foreground">
            {transfer.differentiationLever || "—"}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-muted/10 p-4 text-sm lg:col-span-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            成功假说
          </p>
          <p className="mt-2 text-foreground">{context.successHypothesis || "—"}</p>
        </div>
      </TabsContent>
    </Tabs>
  );
}

export function StructureEvidencePanel({
  structure,
  sampleAnalysisFacts = null,
  highlightedSlotIds = [],
  onHighlightSlot,
  analysisStage,
  promoteAction,
  showAllSegments = false,
}: StructureEvidencePanelProps) {
  const isAnalyzing =
    analysisStage != null && ANALYSIS_STAGES.includes(analysisStage);
  const views = buildSegmentEvidenceViews(structure);
  const isV3 = structure.version === "p1-v3";

  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(
    views[0]?.segment.id ?? null,
  );

  useEffect(() => {
    if (views.length === 0) {
      setSelectedSegmentId(null);
      return;
    }
    if (!views.some((view) => view.segment.id === selectedSegmentId)) {
      setSelectedSegmentId(views[0]!.segment.id);
    }
  }, [views, selectedSegmentId]);

  const selectedView = views.find((view) => view.segment.id === selectedSegmentId) ?? views[0];

  return (
    <Card data-testid="structure-evidence-panel">
      <CardHeader className="pb-3">
        <CardTitle className="font-serif text-lg">叙事分段 · 结构解读</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <StructureHero
          structure={structure}
          sampleAnalysisFacts={sampleAnalysisFacts}
          promoteAction={promoteAction}
          directMultimodal={
            sampleAnalysisFacts?.structureAnalysisRoute === "direct_multimodal"
          }
        />

        {isAnalyzing && (
          <p
            className="rounded-md border border-ai/30 bg-ai/5 px-3 py-2 text-sm text-ai"
            role="status"
          >
            AI 正在分析样例结构…
          </p>
        )}

        <NarrativeTimeline
          segments={structure.narrative.segments}
          durationSec={structure.metadata.durationSec}
          selectedSegmentId={selectedSegmentId}
          onSelectSegment={(segmentId) => {
            setSelectedSegmentId(segmentId);
            const view = views.find((item) => item.segment.id === segmentId);
            const firstSlot = view?.relatedSlotIds[0];
            if (firstSlot) onHighlightSlot?.(firstSlot);
          }}
        />

        {selectedView ? (
          <SegmentDetailPanel
            view={selectedView}
            structure={structure}
            highlightedSlotIds={highlightedSlotIds}
            onHighlightSlot={onHighlightSlot}
          />
        ) : null}

        {showAllSegments ? (
          <div className="space-y-2">
            {views.map((view) => (
              <EvidenceCard
                key={view.segment.id}
                view={view}
                mode="compact"
                highlighted={view.relatedSlotIds.some((slotId) =>
                  highlightedSlotIds.includes(slotId),
                )}
                onSelect={() => {
                  setSelectedSegmentId(view.segment.id);
                  const firstSlot = view.relatedSlotIds[0];
                  if (firstSlot) onHighlightSlot?.(firstSlot);
                }}
              />
            ))}
          </div>
        ) : null}

        {isV3 ? (
          <details open className="rounded-lg border border-border bg-muted/10 p-3">
            <summary className="cursor-pointer text-sm font-medium">
              四轨深度洞察
            </summary>
            <div className="mt-3">
              <StructureV3TrackPanel structure={structure} />
            </div>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function slotHighlightClass(isHighlighted: boolean): string {
  return cn(
    isHighlighted &&
      "ring-2 ring-ai ring-offset-2 ring-offset-background border-ai/50",
  );
}
