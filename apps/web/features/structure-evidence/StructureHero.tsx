"use client";

import type { SampleAnalysisFacts, VideoStructure } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { StructureQualityWarnings } from "@/features/structure-quality/StructureQualityWarnings";
import { cn } from "@/lib/utils";

type StructureHeroProps = {
  structure: VideoStructure;
  sampleAnalysisFacts?: SampleAnalysisFacts | null;
  promoteAction?: React.ReactNode;
  directMultimodal?: boolean;
};

export function StructureHero({
  structure,
  sampleAnalysisFacts,
  promoteAction,
  directMultimodal = false,
}: StructureHeroProps) {
  const audio = sampleAnalysisFacts?.audioProfile;

  return (
    <div
      className="space-y-3 rounded-xl bg-secondary/30 px-4 py-3"
      data-testid="structure-hero"
    >
      <p className="line-clamp-2 text-sm leading-relaxed text-foreground">
        {structure.narrative.summary}
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>时长 {structure.metadata.durationSec}s</span>
        <span>镜头 {structure.rhythm.shotCount}</span>
        <span>证据 {structure.evidence.length}</span>
        <Badge variant="ai">
          置信度 {(structure.confidence * 100).toFixed(0)}%
        </Badge>
        {structure.version === "p1-v3" ? (
          <Badge variant="outline">p1-v3 四轨</Badge>
        ) : null}
        {directMultimodal ? <Badge variant="secondary">直连多模态</Badge> : null}
        {audio ? (
          <>
            <Badge variant="secondary">
              口播 {audio.hasVoiceover ? "有" : "无"}
            </Badge>
            <Badge variant="secondary">BGM {audio.hasBgm ? "疑似有" : "无"}</Badge>
            <Badge variant="outline">
              口播覆盖 {(audio.metrics.voiceoverCoveragePct * 100).toFixed(0)}%
            </Badge>
          </>
        ) : null}
      </div>
      <StructureQualityWarnings analysisQuality={structure.analysisQuality} />
      {promoteAction}
    </div>
  );
}
