"use client";

import type { NarrativeSegment } from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { computeSegmentFlexLayout } from "@/features/structure-evidence/narrativeTimelineLayout";
import { narrativeRoleLabel } from "@/lib/narrativeRoleLabels";
import { cn } from "@/lib/utils";

type NarrativeTimelineProps = {
  segments: NarrativeSegment[];
  durationSec: number;
  selectedSegmentId: string | null;
  onSelectSegment: (segmentId: string) => void;
  keyframeBySegmentId?: Record<string, string | null>;
};

function roleAbbrev(role: string): string {
  const label = narrativeRoleLabel(role);
  return label.slice(0, 2);
}

export function NarrativeTimeline({
  segments,
  durationSec,
  selectedSegmentId,
  onSelectSegment,
  keyframeBySegmentId = {},
}: NarrativeTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const layout = useMemo(
    () => computeSegmentFlexLayout(segments, durationSec),
    [segments, durationSec],
  );

  const selectAdjacent = useCallback(
    (direction: -1 | 1) => {
      if (segments.length === 0) return;
      const currentIndex = segments.findIndex((s) => s.id === selectedSegmentId);
      const baseIndex = currentIndex >= 0 ? currentIndex : 0;
      const nextIndex = Math.max(0, Math.min(segments.length - 1, baseIndex + direction));
      onSelectSegment(segments[nextIndex]!.id);
    },
    [onSelectSegment, segments, selectedSegmentId],
  );

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        selectAdjacent(-1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        selectAdjacent(1);
      }
    };
    node.addEventListener("keydown", onKeyDown);
    return () => node.removeEventListener("keydown", onKeyDown);
  }, [selectAdjacent]);

  return (
    <div
      ref={containerRef}
      className="space-y-2 outline-none"
      tabIndex={0}
      role="tablist"
      aria-label="叙事时间轴"
      data-testid="narrative-timeline"
    >
      <div className="rounded-lg border border-border bg-muted/20 p-0.5">
        <div className="flex h-10 w-full gap-0.5">
          {layout.map(({ segment, flexGrow, sharePct }) => {
            const isSelected = segment.id === selectedSegmentId;
            const keyframeUrl = keyframeBySegmentId[segment.id];
            return (
              <button
                key={segment.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                title={`${narrativeRoleLabel(segment.role)} · ${segment.startSec}–${segment.endSec}s · ${sharePct.toFixed(0)}% · ${segment.intent}`}
                className={cn(
                  "group relative min-w-[2.75rem] flex-1 rounded-md px-0.5 text-[10px] font-medium transition-colors",
                  "bg-primary/15 hover:bg-primary/25",
                  isSelected && "z-10 bg-primary/30 ring-2 ring-ai",
                )}
                style={{ flexGrow }}
                onClick={() => onSelectSegment(segment.id)}
                data-testid={`timeline-segment-${segment.id}`}
              >
                <span className="relative z-10 block truncate px-1 py-2.5 text-foreground">
                  {roleAbbrev(segment.role)}
                </span>
                {keyframeUrl ? (
                  <span
                    className="pointer-events-none absolute inset-0 rounded-md opacity-0 transition-opacity duration-200 group-hover:opacity-40 group-focus-visible:opacity-40"
                    style={{
                      backgroundImage: `url(${keyframeUrl})`,
                      backgroundSize: "cover",
                      backgroundPosition: "center",
                    }}
                    aria-hidden
                  />
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        点击分段查看详情；可用左右方向键切换。展开「核对依据」可查看转写与镜头证据。
      </p>
    </div>
  );
}
