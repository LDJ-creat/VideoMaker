"use client";

import type { RenderTimeline, TimelineTrackType } from "@videomaker/contracts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  GeneratedAssetBadge,
  resolveClipProvider,
} from "@/features/aigc-preview/GeneratedAssetBadge";
import { cn } from "@/lib/utils";

const TRACK_COLORS: Record<TimelineTrackType, string> = {
  video: "bg-sky-500/80",
  image: "bg-indigo-500/80",
  text: "bg-violet-500/80",
  voiceover: "bg-emerald-500/80",
  bgm: "bg-amber-500/70",
  effect: "bg-pink-500/70",
  transition: "bg-orange-500/70",
};

type TimelinePreviewProps = {
  timeline: RenderTimeline;
};

export function TimelinePreview({ timeline }: TimelinePreviewProps) {
  const duration = Math.max(timeline.durationSec, 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle>时间线预览</CardTitle>
        <CardDescription>
          紧凑多轨展示 · 总时长 {timeline.durationSec}s
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {timeline.tracks.map((track) => (
          <div key={track.id} className="space-y-1">
            <p className="font-mono text-xs uppercase text-muted-foreground">
              {track.type}
            </p>
            <div className="relative h-12 rounded-md bg-muted/40">
              {track.clips.map((clip) => {
                const rawLeft = (clip.startSec / duration) * 100;
                const rawWidth = ((clip.endSec - clip.startSec) / duration) * 100;
                const left = Math.min(Math.max(rawLeft, 0), 100);
                const width = Math.min(Math.max(rawWidth, 2), 100 - left);
                const provider = resolveClipProvider(clip.generatedBy);
                return (
                  <div
                    key={clip.id}
                    title={
                      clip.content ??
                      clip.sourceRef ??
                      `${clip.startSec}-${clip.endSec}s`
                    }
                    className={cn(
                      "absolute top-1 flex h-10 min-w-[2%] flex-col justify-center rounded px-1 text-[10px] text-white shadow-sm transition-transform hover:scale-y-110",
                      TRACK_COLORS[track.type],
                    )}
                    style={{ left: `${left}%`, width: `${width}%` }}
                  >
                    {provider && (
                      <GeneratedAssetBadge
                        provider={provider}
                        generatedBy={clip.generatedBy}
                        className="mb-0.5 w-fit bg-black/30 text-[9px] text-white"
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
