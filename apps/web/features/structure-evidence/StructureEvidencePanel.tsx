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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StructureQualityWarnings } from "@/features/structure-quality/StructureQualityWarnings";
import {
  type SampleKeyframe,
  resolveSegmentKeyframePreview,
} from "@/lib/keyframePreview";
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

function StructureV3TrackPanel({ structure }: { structure: VideoStructure }) {
  const { context, verbal, visual, audio, transfer } = structure;

  return (
    <Tabs defaultValue="verbal" className="w-full" data-testid="structure-v3-tracks">
      <TabsList className="grid w-full grid-cols-4">
        {(Object.keys(STRUCTURE_V3_TRACK_LABELS) as Array<keyof typeof STRUCTURE_V3_TRACK_LABELS>).map(
          (track) => (
            <TabsTrigger key={track} value={track}>
              {STRUCTURE_V3_TRACK_LABELS[track]}
            </TabsTrigger>
          ),
        )}
      </TabsList>

      <TabsContent value="verbal" className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">
            {verbalFieldLabel("hookTemplate")}：
          </span>
          {verbal.hookTemplate || "—"}
        </p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">
            {verbalFieldLabel("ctaMechanism")}：
          </span>
          {verbal.ctaMechanism || "—"}
        </p>
        {verbal.outlineTimeline?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {verbal.outlineTimeline.map((phase) => (
              <li key={`${phase.phase}-${phase.startSec}`}>
                {outlinePhaseLabel(phase.phase)} · {phase.startSec}–{phase.endSec}s ·{" "}
                {(phase.sharePct * 100).toFixed(0)}%
              </li>
            ))}
          </ul>
        ) : null}
        {verbal.infoLubricantRatio ? (
          <p className="text-xs text-muted-foreground">
            {verbalFieldLabel("infoLubricantRatio")}：信息 {verbal.infoLubricantRatio.infoSec}s /
            润滑 {verbal.infoLubricantRatio.lubricantSec}s（
            {verbal.infoLubricantRatio.ratio.toFixed(2)}）
          </p>
        ) : null}
      </TabsContent>

      <TabsContent value="visual" className="space-y-3 text-sm">
        {visual?.cutRateProfile ? (
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">
              {visualFieldLabel("cutRateProfile")}：
            </span>
            均镜 {visual.cutRateProfile.avgShotSec ?? "—"}s · 开场{" "}
            {visual.cutRateProfile.openingCutRate ?? "—"}
          </p>
        ) : null}
        {visual?.packagingSpec ? (
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">
              {visualFieldLabel("packagingSpec")}：
            </span>
            密度 {visualDensityLabel(visual.packagingSpec.visualDensity)} ·{" "}
            {visual.packagingSpec.summary ?? "—"}
          </p>
        ) : null}
        {visual?.conceptVisualMap?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {visual.conceptVisualMap.map((entry) => (
              <li key={`${entry.concept}-${entry.timeSec ?? 0}`}>
                {entry.concept} → {entry.visualMetaphor}
                {entry.timeSec != null ? ` @ ${entry.timeSec}s` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">暂无概念-画面映射</p>
        )}
      </TabsContent>

      <TabsContent value="audio" className="space-y-3 text-sm">
        {audio?.voProfile ? (
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">
              {audioFieldLabel("voProfile")}：
            </span>
            {audio.voProfile.persona ?? "—"} / {tempoLabel(audio.voProfile.pace)} /{" "}
            {audio.voProfile.energy ?? "—"}
            {audio.voProfile.wordsPerMinute != null
              ? ` · ${audio.voProfile.wordsPerMinute} ${audioFieldLabel("wordsPerMinute")}`
              : ""}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">暂无口播画像</p>
        )}
        {audio?.audioEventRules?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {audio.audioEventRules.map((rule, index) => (
              <li key={`${rule.trigger}-${index}`}>
                {rule.trigger} → {rule.action}
                {rule.timeSec != null ? ` @ ${rule.timeSec}s` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </TabsContent>

      <TabsContent value="transfer" className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">类型：</span>
          {contentCategoryLabel(context.contentCategory)} ·{" "}
          {primaryIntentLabel(context.primaryIntent)}
        </p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">
            {transferFieldLabel("differentiationLever")}：
          </span>
          {transfer.differentiationLever || "—"}
        </p>
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">成功假说：</span>
          {context.successHypothesis || "—"}
        </p>
        {transfer.emotionTriggers?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {transfer.emotionTriggers.map((trigger) => (
              <li key={`${trigger.segmentId}-${trigger.timeSec}`}>
                {trigger.timeSec}s · {trigger.triggerType} · {trigger.mechanism}
              </li>
            ))}
          </ul>
        ) : null}
        {transfer.nonTransferableElements?.length ? (
          <p className="text-xs text-muted-foreground">
            {transferFieldLabel("nonTransferableElements")}：
            {transfer.nonTransferableElements.join("、")}
          </p>
        ) : null}
      </TabsContent>
    </Tabs>
  );
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
  const isV3 = structure.version === "p1-v3";

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
          {isV3 ? <Badge variant="outline">p1-v3 四轨</Badge> : null}
        </div>

        {isV3 ? <StructureV3TrackPanel structure={structure} /> : null}

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
