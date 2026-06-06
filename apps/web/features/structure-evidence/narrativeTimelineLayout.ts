import type { NarrativeSegment } from "@videomaker/contracts";

/** Minimum flex-grow unit so short segments (e.g. 过渡) stay readable. */
const MIN_FLEX = 0.85;

/** Blend equal vs duration-proportional weights to avoid one long segment dominating. */
const PROPORTIONAL_BLEND = 0.45;

export type SegmentFlexLayout = {
  segment: NarrativeSegment;
  flexGrow: number;
  spanSec: number;
  sharePct: number;
};

/**
 * Computes flex-grow weights for timeline segments.
 * Uses sqrt-compressed duration shares blended with equal distribution,
 * then enforces a minimum flex per segment.
 */
export function computeSegmentFlexLayout(
  segments: NarrativeSegment[],
  durationSec: number,
): SegmentFlexLayout[] {
  if (segments.length === 0) return [];

  const equalShare = 1 / segments.length;
  const spans = segments.map((segment) =>
    Math.max(segment.endSec - segment.startSec, 0.1),
  );
  const totalSpan = spans.reduce((sum, span) => sum + span, 0);
  const durationBase = durationSec > 0 ? durationSec : totalSpan;

  const rawWeights = spans.map((span) => {
    const proportional = span / durationBase;
    const compressed = Math.sqrt(proportional / equalShare) * equalShare;
    return PROPORTIONAL_BLEND * compressed + (1 - PROPORTIONAL_BLEND) * equalShare;
  });

  const withMin = rawWeights.map((weight) => Math.max(weight, MIN_FLEX * equalShare));
  const sum = withMin.reduce((acc, weight) => acc + weight, 0);

  return segments.map((segment, index) => {
    const spanSec = spans[index]!;
    const flexGrow = withMin[index]! / sum;
    const sharePct = durationBase > 0 ? (spanSec / durationBase) * 100 : equalShare * 100;
    return { segment, flexGrow, spanSec, sharePct };
  });
}
