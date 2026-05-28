"use client";

import type { GenerationPlan } from "@videomaker/contracts";
import { ExternalLink, Film } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";

type GenerationResultViewProps = {
  plan: GenerationPlan;
  previewHref?: string;
  videoHref?: string;
};

export function GenerationResultView({
  plan,
  previewHref = "#preview-placeholder",
  videoHref,
}: GenerationResultViewProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>生成结果</CardTitle>
          <CardDescription>
            变体 {plan.variant} · {plan.storyboard.length} 个分镜场景
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3">
            {plan.storyboard.map((scene) => (
              <div
                key={scene.id}
                className="rounded-lg border border-border p-3"
              >
                <div className="mb-1 flex items-center justify-between">
                  <Badge variant="outline">{scene.source}</Badge>
                  <span className="font-mono text-xs text-muted-foreground">
                    {scene.startSec}–{scene.endSec}s
                  </span>
                </div>
                <p className="text-sm font-medium">{scene.visual}</p>
                <p className="text-sm text-muted-foreground">{scene.script}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-3">
            <a
              href={previewHref}
              className="inline-flex items-center gap-2 text-sm text-primary underline-offset-4 hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              HyperFrames 预览
            </a>
            {videoHref ? (
              <a
                href={videoHref}
                className="inline-flex items-center gap-2 text-sm text-primary underline-offset-4 hover:underline"
              >
                <Film className="h-4 w-4" />
                演示视频
              </a>
            ) : (
              <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <Film className="h-4 w-4" />
                演示视频（集成后可用）
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <TimelinePreview timeline={plan.timeline} />
    </div>
  );
}
