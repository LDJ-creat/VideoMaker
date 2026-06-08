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

const VIDEO_PROBE_INTERVAL_MS = 2000;
const VIDEO_PROBE_MAX_ATTEMPTS = 15;

type GenerationResultViewProps = {
  plan: GenerationPlan;
  /** From API when renders/.../output.mp4 exists; skips client probe when set. */
  videoHref?: string;
  showTimeline?: boolean;
};

async function probeVideoUrl(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: "HEAD" });
    return response.ok;
  } catch {
    return false;
  }
}

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
    let attempt = 0;

    const runProbe = async () => {
      while (!cancelled && attempt < VIDEO_PROBE_MAX_ATTEMPTS) {
        if (await probeVideoUrl(probeTarget)) {
          if (!cancelled) {
            setProbedVideoUrl(probeTarget);
          }
          return;
        }
        attempt += 1;
        if (attempt >= VIDEO_PROBE_MAX_ATTEMPTS || cancelled) {
          if (!cancelled) {
            setProbedVideoUrl(null);
          }
          return;
        }
        await new Promise<void>((resolve) => {
          window.setTimeout(resolve, VIDEO_PROBE_INTERVAL_MS);
        });
      }
    };

    void runProbe();
    return () => {
      cancelled = true;
    };
  }, [probeTarget]);

  const playableVideoUrl = apiVideoUrl ?? probedVideoUrl;
  const narrationDurationSec = plan.narrationDurationSec;
  const durationTargetSec = plan.durationTargetSec;
  const narrationLongerThanTarget =
    narrationDurationSec != null &&
    durationTargetSec != null &&
    narrationDurationSec > durationTargetSec + 0.05;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>生成结果</CardTitle>
          <CardDescription>
            变体 {plan.variant} · {plan.storyboard.length} 个分镜场景
            {plan.ttsMode ? ` · 口播 ${plan.ttsMode === "global" ? "全片" : "分镜"}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {narrationLongerThanTarget ? (
            <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
              口播时长 {narrationDurationSec.toFixed(1)}s 长于目标时长{" "}
              {durationTargetSec.toFixed(1)}s，成片已按口播延长尾镜。
            </p>
          ) : null}
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
