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
import { slotHighlightClass } from "@/features/structure-evidence/StructureEvidencePanel";
import { isDuplicateText } from "@/lib/keyframePreview";
import { cn } from "@/lib/utils";

type StructureSlot = VideoStructure["slots"][number];

type RelatedSlotsColumnProps = {
  slots: StructureSlot[];
  highlightedSlotIds?: string[];
  onSelectSlot?: (slotId: string) => void;
};

export function RelatedSlotsColumn({
  slots,
  highlightedSlotIds = [],
  onSelectSlot,
}: RelatedSlotsColumnProps) {
  if (slots.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/10 p-4 text-xs text-muted-foreground">
        本段暂无关联结构槽
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="related-slots-column">
      <p className="text-xs font-medium text-muted-foreground">关联结构槽</p>
      <ul className="space-y-2">
        {slots.map((slot) => (
          <li key={slot.id}>
            <button
              type="button"
              className={cn(
                "w-full rounded-lg border border-border bg-muted/20 p-3 text-left transition-colors hover:bg-muted/40",
                slotHighlightClass(highlightedSlotIds.includes(slot.id)),
              )}
              data-testid={`structure-slot-${slot.id}`}
              onClick={() => onSelectSlot?.(slot.id)}
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <Badge variant="outline" className="text-[10px]">
                  {slot.role}
                </Badge>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {slot.startSec}–{slot.endSec}s
                </span>
              </div>
              <p className="line-clamp-3 text-xs font-medium">{slot.visualIntent}</p>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

type StructureSlotBoardProps = {
  structure: VideoStructure;
  highlightedSlotIds?: string[];
};

export function StructureSlotBoard({
  structure,
  highlightedSlotIds = [],
}: StructureSlotBoardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>结构槽位</CardTitle>
        <CardDescription>
          从样例视频抽取的可复用创意结构（共 {structure.slots.length} 槽）
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {structure.slots.map((slot) => {
          return (
            <div
              key={slot.id}
              data-testid={`structure-slot-${slot.id}`}
              className={cn(
                "rounded-lg border border-border bg-muted/20 p-4",
                slotHighlightClass(highlightedSlotIds.includes(slot.id)),
              )}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <Badge variant="outline">{slot.role}</Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  {slot.startSec}–{slot.endSec}s
                </span>
              </div>
              <p className="text-sm font-medium">{slot.visualIntent}</p>
              {!isDuplicateText(slot.visualIntent, slot.scriptIntent) &&
              slot.scriptIntent ? (
                <p className="mt-1 text-xs text-muted-foreground">{slot.scriptIntent}</p>
              ) : null}
              {slot.durationSharePct != null ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  时长占比 {(slot.durationSharePct * 100).toFixed(0)}%
                </p>
              ) : null}
              {slot.migrationTemplate ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  迁移模板：{slot.migrationTemplate}
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-1">
                {slot.requiredAssetType.map((type) => (
                  <Badge key={type} variant="secondary" className="text-[10px]">
                    {type}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
