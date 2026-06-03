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
          const showScriptIntent = !isDuplicateText(
            slot.visualIntent,
            slot.scriptIntent,
          );
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
            {showScriptIntent ? (
              <p className="mt-1 text-xs text-muted-foreground">
                口播意图：{slot.scriptIntent}
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
