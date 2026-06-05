"use client";

import type { VideoStructure } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { StructureQualityWarnings } from "@/features/structure-quality/StructureQualityWarnings";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { isDuplicateText } from "@/lib/keyframePreview";

type SampleAnalysisViewProps = {
  structure: VideoStructure;
};

export function SampleAnalysisView({ structure }: SampleAnalysisViewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>样例分析</CardTitle>
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
        </div>
        <div className="grid gap-3">
          {structure.narrative.segments.map((segment) => {
            const showScriptSummary = !isDuplicateText(
              segment.visualSummary,
              segment.scriptSummary,
            );
            return (
              <div
                key={segment.id}
                className="rounded-lg border border-border p-3"
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <Badge variant="secondary">{segment.role}</Badge>
                  <span className="font-mono text-xs text-muted-foreground">
                    {segment.startSec}s – {segment.endSec}s
                  </span>
                </div>
                {segment.retentionRole ? (
                  <p className="mb-1 text-xs text-muted-foreground">
                    留存作用：{segment.retentionRole}
                  </p>
                ) : null}
                <p className="text-sm font-medium">{segment.visualSummary}</p>
                {showScriptSummary ? (
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">口播手法：</span>
                    {segment.scriptSummary}
                  </p>
                ) : null}
                {segment.transcriptExcerpt ? (
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">口播摘录：</span>
                    {segment.transcriptExcerpt}
                  </p>
                ) : null}
                {segment.rhetoricalDevices?.length ? (
                  <p className="text-xs text-muted-foreground">
                    修辞：{segment.rhetoricalDevices.join("、")}
                  </p>
                ) : null}
                {segment.voStyle ? (
                  <p className="text-xs text-muted-foreground">
                    口播风格：{segment.voStyle.persona} / {segment.voStyle.pace} /{" "}
                    {segment.voStyle.energy}
                  </p>
                ) : null}
                {segment.visualSpec ? (
                  <p className="text-xs text-muted-foreground">
                    画面：{segment.visualSpec.framing} · {segment.visualSpec.cameraMove}
                    {segment.visualSpec.onScreenText?.length
                      ? ` · 花字：${segment.visualSpec.onScreenText.join("、")}`
                      : ""}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
