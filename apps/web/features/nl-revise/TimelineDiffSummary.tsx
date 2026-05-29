"use client";

import type { GenerationPlan } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export type TimelineDiffItem = {
  label: string;
  before: string;
  after: string;
  changed: boolean;
};

export function buildTimelineDiffItems(
  before: GenerationPlan,
  after: GenerationPlan,
): TimelineDiffItem[] {
  const beforeClips = before.timeline.tracks.reduce(
    (count, track) => count + track.clips.length,
    0,
  );
  const afterClips = after.timeline.tracks.reduce(
    (count, track) => count + track.clips.length,
    0,
  );

  return [
    {
      label: "总时长",
      before: `${before.timeline.durationSec}s`,
      after: `${after.timeline.durationSec}s`,
      changed: before.timeline.durationSec !== after.timeline.durationSec,
    },
    {
      label: "分镜场景",
      before: `${before.storyboard.length} 个`,
      after: `${after.storyboard.length} 个`,
      changed: before.storyboard.length !== after.storyboard.length,
    },
    {
      label: "时间线片段",
      before: `${beforeClips} 个`,
      after: `${afterClips} 个`,
      changed: beforeClips !== afterClips,
    },
    {
      label: "包装风格",
      before: before.packagingPlan.styleSummary,
      after: after.packagingPlan.styleSummary,
      changed:
        before.packagingPlan.styleSummary !== after.packagingPlan.styleSummary,
    },
  ];
}

type TimelineDiffSummaryProps = {
  before: GenerationPlan;
  after: GenerationPlan;
};

export function TimelineDiffSummary({ before, after }: TimelineDiffSummaryProps) {
  const items = buildTimelineDiffItems(before, after);
  const hasChanges = items.some((item) => item.changed);

  return (
    <Card data-testid="timeline-diff-summary">
      <CardHeader>
        <CardTitle>改片对比</CardTitle>
        <CardDescription>
          {hasChanges
            ? "相较上一版，以下字段已更新"
            : "未检测到显著结构差异（可能仅文案微调）"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="font-medium">{item.label}</span>
            <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
              <span>{item.before}</span>
              <span aria-hidden>→</span>
              <span className={item.changed ? "text-foreground" : undefined}>
                {item.after}
              </span>
              {item.changed && <Badge variant="ai">已变更</Badge>}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
