"use client";

import type { GenerationPlan } from "@videomaker/contracts";
import { Film } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TimelinePreview } from "@/features/timeline-preview/TimelinePreview";
import { generationRenderVideoUrl } from "@/lib/artifactUrl";

type GenerationResultViewProps = {
  plan: GenerationPlan;
  /** From API when renders/.../output.mp4 exists; skips client probe when set. */
  videoHref?: string;
  showTimeline?: boolean;
};

export function GenerationResultView({
  plan,
  videoHref,
  showTimeline = false,
}: GenerationResultViewProps) {
  const apiVideoUrl = videoHref?.trim() || null;
  const [probedVideoUrl, setProbedVideoUrl] = useState<string | null>(null);

  const probeTarget =
    !apiVideoUrl && plan.projectId && plan.id
      ? generationRenderVideoUrl(plan.projectId, plan.id)
      : null;

  useEffect(() => {
    if (!probeTarget) {
      setProbedVideoUrl(null);
      return;
    }
    let cancelled = false;
    fetch(probeTarget, { method: "HEAD" })
      .then((response) => {
        if (!cancelled && response.ok) {
          setProbedVideoUrl(probeTarget);
        } else if (!cancelled) {
          setProbedVideoUrl(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProbedVideoUrl(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [probeTarget]);

  const playableVideoUrl = apiVideoUrl ?? probedVideoUrl;

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

          {playableVideoUrl ? (
            <div className="space-y-2">
              <div className="overflow-hidden rounded-lg border border-border bg-black">
                <video
                  src={playableVideoUrl}
                  controls
                  playsInline
                  className="aspect-video w-full min-h-[280px] bg-black"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                演示视频 MP4（HyperFrames CLI 渲染）。
              </p>
              <a
                href={playableVideoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm text-primary underline-offset-4 hover:underline"
              >
                <Film className="h-4 w-4" />
                新标签页打开 MP4
              </a>
            </div>
          ) : (
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Film className="h-4 w-4" />
              演示视频 MP4（未生成）
            </span>
          )}
        </CardContent>
      </Card>

      {showTimeline && <TimelinePreview timeline={plan.timeline} />}
    </div>
  );
}
