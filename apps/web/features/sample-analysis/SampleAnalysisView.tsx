"use client";

import type { VideoStructure } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
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
                <p className="text-sm font-medium">{segment.visualSummary}</p>
                {showScriptSummary ? (
                  <p className="text-sm text-muted-foreground">
                    {segment.scriptSummary}
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
