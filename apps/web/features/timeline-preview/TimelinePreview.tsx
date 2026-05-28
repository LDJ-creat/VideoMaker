"use client";

import type { RenderTimeline, TimelineTrackType } from "@videomaker/contracts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
            <div className="relative h-10 rounded-md bg-muted/40">
              {track.clips.map((clip) => {
                const left = (clip.startSec / duration) * 100;
                const width =
                  ((clip.endSec - clip.startSec) / duration) * 100;
                return (
                  <div
                    key={clip.id}
                    title={
                      clip.content ??
                      clip.sourceRef ??
                      `${clip.startSec}-${clip.endSec}s`
                    }
                    className={cn(
                      "absolute top-1 h-8 min-w-[2%] rounded px-1 text-[10px] text-white shadow-sm transition-transform hover:scale-y-110",
                      TRACK_COLORS[track.type],
                    )}
                    style={{ left: `${left}%`, width: `${Math.max(width, 2)}%` }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
