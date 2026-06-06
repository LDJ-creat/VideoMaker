"use client";

import type { NarrativeSegment, VideoStructure } from "@videomaker/contracts";
import type { TaskStage } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StructureQualityWarnings } from "@/features/structure-quality/StructureQualityWarnings";
import {
  type SampleKeyframe,
  resolveSegmentKeyframePreview,
} from "@/lib/keyframePreview";
import { cn } from "@/lib/utils";

import { EvidenceCard } from "./EvidenceCard";

export type SegmentEvidenceView = {
  segment: NarrativeSegment;
  transcriptExcerpt?: string;
  ocrExcerpts?: string[];
  audioSummary?: string;
  keyframeLabel?: string;
  keyframePreviewUrl?: string | null;
  shotRanges: Array<{ startSec: number; endSec: number }>;
  relatedSlotIds: string[];
};

const ANALYSIS_STAGES: TaskStage[] = ["extracting_structure", "running_agent"];

type StructureEvidencePanelProps = {
  structure: VideoStructure;
  projectId?: string;
  sampleId?: string | null;
  keyframes?: SampleKeyframe[];
  highlightedSlotIds?: string[];
  onHighlightSlot?: (slotId: string) => void;
  analysisStage?: TaskStage | null;
};

export function buildSegmentEvidenceViews(
  structure: VideoStructure,
  options?: {
    projectId?: string;
    sampleId?: string | null;
    keyframes?: SampleKeyframe[];
  },
): SegmentEvidenceView[] {
  const { projectId, sampleId, keyframes = [] } = options ?? {};

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

    const keyframeEvidence = segmentEvidence.find(
      (item) => item.source === "keyframe",
    );
    const keyframeLabel = keyframeEvidence?.summary;
    const keyframePreviewUrl =
      projectId && sampleId
        ? resolveSegmentKeyframePreview(
            projectId,
            sampleId,
            keyframes,
            segment,
            keyframeEvidence?.summary,
          )
        : null;

    const shotRanges = structure.rhythm.shotBoundaries.filter(
      (shot) => shot.startSec < segment.endSec && shot.endSec > segment.startSec,
    );

    return {
      segment,
      transcriptExcerpt,
      ocrExcerpts,
      audioSummary,
      keyframeLabel,
      keyframePreviewUrl,
      shotRanges,
      relatedSlotIds,
    };
  });
}

export function StructureEvidencePanel({
  structure,
  projectId,
  sampleId,
  keyframes = [],
  highlightedSlotIds = [],
  onHighlightSlot,
  analysisStage,
}: StructureEvidencePanelProps) {
  const isAnalyzing =
    analysisStage != null && ANALYSIS_STAGES.includes(analysisStage);
  const views = buildSegmentEvidenceViews(structure, {
    projectId,
    sampleId,
    keyframes,
  });

  return (
    <Card data-testid="structure-evidence-panel">
      <CardHeader>
        <CardTitle>叙事分段 · 结构解读</CardTitle>
        <CardDescription>{structure.narrative.summary}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <StructureQualityWarnings analysisQuality={structure.analysisQuality} />
        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span>时长 {structure.metadata.durationSec}s</span>
          <span>镜头 {structure.rhythm.shotCount}</span>
          <Badge variant="ai">
            置信度 {(structure.confidence * 100).toFixed(0)}%
          </Badge>
          <Badge variant="secondary">证据条目 {structure.evidence.length}</Badge>
        </div>

        {isAnalyzing && (
          <p
            className="rounded-md border border-ai/30 bg-ai/5 px-3 py-2 text-sm text-ai"
            role="status"
          >
            AI 正在分析样例结构…
          </p>
        )}

        <p className="text-xs text-muted-foreground">
          各段按叙事节拍拆解；点击分段可高亮对应结构槽。展开「核对依据」可查看转写、镜头等原始证据。
        </p>

        {views.map((view) => (
          <EvidenceCard
            key={view.segment.id}
            view={view}
            highlighted={view.relatedSlotIds.some((slotId) =>
              highlightedSlotIds.includes(slotId),
            )}
            onSelect={() => {
              const firstSlot = view.relatedSlotIds[0];
              if (firstSlot) onHighlightSlot?.(firstSlot);
            }}
          />
        ))}
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
