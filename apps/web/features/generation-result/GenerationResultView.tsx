"use client";

import type { GenerationPlan } from "@videomaker/contracts";
import { ExternalLink, Film } from "lucide-react";
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
import {
  generationCompositionPreviewUrl,
  generationRenderVideoUrl,
} from "@/lib/artifactUrl";

type GenerationResultViewProps = {
  plan: GenerationPlan;
  previewHref?: string;
  /** From API when renders/.../output.mp4 exists; skips client probe when set. */
  videoHref?: string;
  showTimeline?: boolean;
};

function resolvePreviewHref(
  plan: GenerationPlan,
  previewHref?: string,
): string | null {
  if (previewHref?.trim()) {
    return previewHref;
  }
  if (plan.projectId && plan.id) {
    return generationCompositionPreviewUrl(plan.projectId, plan.id);
  }
  return null;
}

export function GenerationResultView({
  plan,
  previewHref,
  videoHref,
  showTimeline = false,
}: GenerationResultViewProps) {
  const resolvedPreviewHref = resolvePreviewHref(plan, previewHref);
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
                演示视频 MP4（HyperFrames CLI 渲染）。下方 HTML 预览用于核对时间轴与分镜素材。
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
          ) : null}

          {resolvedPreviewHref ? (
            <div className="space-y-2">
              <div className="overflow-hidden rounded-lg border border-border bg-black">
                <iframe
                  src={resolvedPreviewHref}
                  title="HyperFrames 预览"
                  className="aspect-video w-full min-h-[280px] bg-black"
                  allow="autoplay"
                />
              </div>
              {!playableVideoUrl ? (
                <p className="text-xs text-muted-foreground">
                  HTML 时间轴预览（分镜素材 + 转场）。演示 MP4 需 HyperFrames CLI 成功渲染
                  output.mp4。
                </p>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <a
                  href={resolvedPreviewHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-primary underline-offset-4 hover:underline"
                >
                  <ExternalLink className="h-4 w-4" />
                  新标签页打开 HTML 预览
                </a>
                {!playableVideoUrl ? (
                  <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Film className="h-4 w-4" />
                    演示视频 MP4（未生成）
                  </span>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <ExternalLink className="h-4 w-4" />
                HyperFrames 预览（渲染完成后可用）
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {showTimeline && <TimelinePreview timeline={plan.timeline} />}
    </div>
  );
}
