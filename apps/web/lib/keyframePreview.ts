import { projectFileMediaUrl } from "@/lib/artifactUrl";

export type SampleKeyframe = {
  timeSec: number;
  score: number;
  relativePath: string;
  previewUrl: string;
};

const KEYFRAME_PATH_PATTERN =
  /keyframes\/[\w./-]+\.(?:jpg|jpeg|png|webp)/i;

export function parseKeyframePathFromEvidence(summary: string): string | null {
  const match = summary.match(KEYFRAME_PATH_PATTERN);
  return match ? match[0].replace(/\\/g, "/") : null;
}

export function sampleKeyframePreviewUrl(
  projectId: string,
  sampleId: string,
  relativePath: string,
): string {
  const normalized = relativePath.replace(/\\/g, "/").replace(/^\/+/, "");
  return projectFileMediaUrl(
    projectId,
    `samples/${sampleId}/analysis/${normalized}`,
  );
}

export function pickSegmentKeyframe(
  keyframes: SampleKeyframe[],
  startSec: number,
  endSec: number,
): SampleKeyframe | undefined {
  const inRange = keyframes.filter(
    (frame) => frame.timeSec >= startSec && frame.timeSec <= endSec,
  );
  if (inRange.length === 0) {
    const midpoint = (startSec + endSec) / 2;
    return keyframes.reduce<SampleKeyframe | undefined>((best, frame) => {
      const distance = Math.abs(frame.timeSec - midpoint);
      if (best === undefined) return frame;
      const bestDistance = Math.abs(best.timeSec - midpoint);
      if (distance < bestDistance) return frame;
      if (distance === bestDistance && frame.score > best.score) return frame;
      return best;
    }, undefined);
  }
  return inRange.reduce((best, frame) =>
    frame.score > best.score ? frame : best,
  );
}

export function resolveSegmentKeyframePreview(
  projectId: string,
  sampleId: string | null | undefined,
  keyframes: SampleKeyframe[],
  segment: { startSec: number; endSec: number },
  evidenceSummary?: string,
): string | null {
  if (sampleId) {
    const fromEvidence = evidenceSummary
      ? parseKeyframePathFromEvidence(evidenceSummary)
      : null;
    if (fromEvidence) {
      return sampleKeyframePreviewUrl(projectId, sampleId, fromEvidence);
    }
    const picked = pickSegmentKeyframe(
      keyframes,
      segment.startSec,
      segment.endSec,
    );
    if (picked?.previewUrl) {
      return picked.previewUrl;
    }
  }
  return null;
}

/** Hide secondary text when it duplicates the primary line. */
export function isDuplicateText(primary: string, secondary: string): boolean {
  const normalize = (value: string) => value.trim().replace(/\s+/g, " ");
  const a = normalize(primary);
  const b = normalize(secondary);
  return Boolean(a && b && a === b);
}

/** Pick highest-scoring keyframe for sample list poster thumbnails. */
export function pickSamplePosterUrl(keyframes: SampleKeyframe[]): string | null {
  if (keyframes.length === 0) return null;
  const best = keyframes.reduce((winner, frame) =>
    frame.score > winner.score ? frame : winner,
  );
  return best.previewUrl ?? null;
}
