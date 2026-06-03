import type {
  CompletionAction,
  GenerationPlan,
  StoryboardScene,
  TimelineClip,
  TimelineTrackType,
} from "@videomaker/contracts";

import { artifactDisplayUrl, projectFileMediaUrl } from "@/lib/artifactUrl";

export type StoryboardSceneMedia = {
  kind: "video" | "image" | "placeholder";
  url: string | null;
  caption: string;
  provider?: string;
};

const VIDEO_EXT = /\.(mp4|webm|mov|mkv)$/i;
const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp)$/i;
const ASSET_ID_PATTERN = /^asset-[\w-]+$/i;

function mediaKindFromPath(value: string): "video" | "image" | null {
  if (VIDEO_EXT.test(value)) return "video";
  if (IMAGE_EXT.test(value)) return "image";
  return null;
}

function resolveRelativeProjectPath(
  projectId: string,
  generationId: string,
  relativePath: string,
): { kind: "video" | "image"; url: string } | null {
  const normalized = relativePath.replace(/\\/g, "/").replace(/^\/+/, "");
  const kind = mediaKindFromPath(normalized);
  if (!kind) return null;

  if (normalized.includes("/")) {
    return {
      kind,
      url: projectFileMediaUrl(projectId, normalized),
    };
  }

  const candidates = [
    `renders/${generationId}/${normalized}`,
    `generations/${generationId}/generated/${normalized}`,
    `generations/${generationId}/render/${normalized}`,
  ];
  return {
    kind,
    url: projectFileMediaUrl(projectId, candidates[0]!),
  };
}

function resolveSourceRef(
  projectId: string,
  generationId: string,
  sourceRef: string,
  trackType: TimelineTrackType,
): StoryboardSceneMedia | null {
  const trimmed = sourceRef.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("/api/")) {
    const kind = trackType === "image" ? "image" : "video";
    return { kind, url: trimmed, caption: trimmed };
  }

  if (ASSET_ID_PATTERN.test(trimmed)) {
    const kind = trackType === "image" ? "image" : "video";
    return {
      kind,
      url: `/api/projects/${projectId}/media/assets/${encodeURIComponent(trimmed)}`,
      caption: trimmed,
    };
  }

  const fromPath = resolveRelativeProjectPath(projectId, generationId, trimmed);
  if (fromPath) {
    return { kind: fromPath.kind, url: fromPath.url, caption: trimmed };
  }

  return null;
}

function findTimelineClip(
  plan: GenerationPlan,
  slotId: string,
): { clip: TimelineClip; trackType: TimelineTrackType } | null {
  const clipId = `clip-${slotId}`;
  for (const trackType of ["video", "image"] as const) {
    const track = plan.timeline.tracks.find((item) => item.type === trackType);
    const clip = track?.clips.find((item) => item.id === clipId);
    if (clip) {
      return { clip, trackType };
    }
  }
  return null;
}

function resolveFromCompletionAction(
  projectId: string,
  action: CompletionAction | undefined,
): StoryboardSceneMedia | null {
  if (!action?.artifactRef) return null;
  const url = artifactDisplayUrl(projectId, action.artifactRef);
  if (!url) return null;
  const uri = action.artifactRef.uri.replace(/\\/g, "/");
  const kind =
    action.artifactRef.type === "video" || VIDEO_EXT.test(uri)
      ? "video"
      : action.artifactRef.type === "image" || IMAGE_EXT.test(uri)
        ? "image"
        : "image";
  return {
    kind,
    url,
    caption: action.rationale || action.reason,
    provider: action.provider,
  };
}

function resolveFromVisualField(
  projectId: string,
  generationId: string,
  visual: string,
): StoryboardSceneMedia | null {
  const trimmed = visual.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("/api/")) {
    const kind = mediaKindFromPath(trimmed) ?? "image";
    return { kind, url: trimmed, caption: trimmed };
  }

  const artifactLike = artifactDisplayUrl(projectId, {
    id: "scene-visual",
    type: "image",
    uri: trimmed,
    createdAt: "1970-01-01T00:00:00.000Z",
  });
  if (artifactLike && (mediaKindFromPath(trimmed) || trimmed.includes("materials/"))) {
    return {
      kind: mediaKindFromPath(trimmed) ?? "image",
      url: artifactLike,
      caption: trimmed,
    };
  }

  const relative = resolveRelativeProjectPath(projectId, generationId, trimmed);
  if (relative) {
    return { kind: relative.kind, url: relative.url, caption: trimmed };
  }

  if (mediaKindFromPath(trimmed)) {
    return {
      kind: mediaKindFromPath(trimmed)!,
      url: projectFileMediaUrl(
        projectId,
        `renders/${generationId}/${trimmed.replace(/^\/+/, "")}`,
      ),
      caption: trimmed,
    };
  }

  return null;
}

export function resolveStoryboardSceneMedia(
  plan: GenerationPlan,
  scene: StoryboardScene,
): StoryboardSceneMedia {
  const action = plan.completionActions.find((item) => item.slotId === scene.slotId);
  const fromAction = resolveFromCompletionAction(plan.projectId, action);
  if (fromAction?.url) {
    return fromAction;
  }

  const timelineHit = findTimelineClip(plan, scene.slotId);
  if (timelineHit?.clip.sourceRef) {
    const fromClip = resolveSourceRef(
      plan.projectId,
      plan.id,
      timelineHit.clip.sourceRef,
      timelineHit.trackType,
    );
    if (fromClip?.url) {
      const provider =
        typeof timelineHit.clip.generatedBy === "object"
          ? timelineHit.clip.generatedBy?.provider
          : timelineHit.clip.generatedBy;
      return { ...fromClip, provider: provider ?? action?.provider };
    }
  }

  const fromVisual = resolveFromVisualField(plan.projectId, plan.id, scene.visual);
  if (fromVisual?.url) {
    return { ...fromVisual, provider: action?.provider };
  }

  return {
    kind: "placeholder",
    url: null,
    caption: scene.visual,
    provider: action?.provider ?? scene.source,
  };
}
