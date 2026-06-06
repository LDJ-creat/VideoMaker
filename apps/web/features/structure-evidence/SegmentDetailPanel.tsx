"use client";

import type { VideoStructure } from "@videomaker/contracts";

import { EvidenceCard } from "@/features/structure-evidence/EvidenceCard";
import type { SegmentEvidenceView } from "@/features/structure-evidence/StructureEvidencePanel";
import { RelatedSlotsColumn } from "@/features/structure-mapping/StructureSlotBoard";

type SegmentDetailPanelProps = {
  view: SegmentEvidenceView;
  structure: VideoStructure;
  highlightedSlotIds?: string[];
  onHighlightSlot?: (slotId: string) => void;
};

export function SegmentDetailPanel({
  view,
  structure,
  highlightedSlotIds = [],
  onHighlightSlot,
}: SegmentDetailPanelProps) {
  const relatedSlots = structure.slots.filter(
    (slot) => slot.segmentId === view.segment.id,
  );

  return (
    <div
      className="grid gap-4 md:grid-cols-[minmax(0,1fr)_280px]"
      data-testid="segment-detail-panel"
    >
      <EvidenceCard
        view={view}
        mode="detail"
        highlighted={view.relatedSlotIds.some((id) => highlightedSlotIds.includes(id))}
        onSelect={() => {
          const first = view.relatedSlotIds[0];
          if (first) onHighlightSlot?.(first);
        }}
      />
      <RelatedSlotsColumn
        slots={relatedSlots}
        highlightedSlotIds={highlightedSlotIds}
        onSelectSlot={onHighlightSlot}
      />
    </div>
  );
}
