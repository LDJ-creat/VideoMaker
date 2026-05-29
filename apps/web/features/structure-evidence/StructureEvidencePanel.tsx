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
import { cn } from "@/lib/utils";

import { EvidenceCard } from "./EvidenceCard";

export type SegmentEvidenceView = {
  segment: NarrativeSegment;
  transcriptExcerpt?: string;
  keyframeLabel?: string;
  shotRanges: Array<{ startSec: number; endSec: number }>;
  relatedSlotIds: string[];
};

const ANALYSIS_STAGES: TaskStage[] = ["extracting_structure", "running_agent"];

type StructureEvidencePanelProps = {
  structure: VideoStructure;
  highlightedSlotIds?: string[];
  onHighlightSlot?: (slotId: string) => void;
  analysisStage?: TaskStage | null;
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

    const transcriptExcerpt = segmentEvidence.find(
      (item) => item.source === "asr",
    )?.summary;

    const keyframeLabel = segmentEvidence.find(
      (item) => item.source === "keyframe",
    )?.summary;

    const shotRanges = structure.rhythm.shotBoundaries.filter(
      (shot) => shot.startSec < segment.endSec && shot.endSec > segment.startSec,
    );

    return {
      segment,
      transcriptExcerpt,
      keyframeLabel,
      shotRanges,
      relatedSlotIds,
    };
  });
}

export function StructureEvidencePanel({
  structure,
  highlightedSlotIds = [],
  onHighlightSlot,
  analysisStage,
}: StructureEvidencePanelProps) {
  const isAnalyzing =
    analysisStage != null && ANALYSIS_STAGES.includes(analysisStage);
  const views = buildSegmentEvidenceViews(structure);

  return (
    <Card data-testid="structure-evidence-panel">
      <CardHeader>
        <CardTitle>结构证据</CardTitle>
        <CardDescription>
          叙事片段对应的镜头、转写与关键帧依据（点击可高亮槽位）
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isAnalyzing && (
          <p
            className="rounded-md border border-ai/30 bg-ai/5 px-3 py-2 text-sm text-ai"
            role="status"
          >
            AI 正在分析样例结构…
          </p>
        )}

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

        <div className="flex flex-wrap gap-2 pt-2">
          <Badge variant="outline">置信度 {(structure.confidence * 100).toFixed(0)}%</Badge>
          <Badge variant="secondary">
            证据条目 {structure.evidence.length}
          </Badge>
        </div>
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
