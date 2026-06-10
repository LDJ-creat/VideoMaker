import type { ArtifactRef } from "@videomaker/contracts";

/** Resolve a TaskEvent artifact ref to a browser-loadable URL when possible. */
export function artifactDisplayUrl(
  projectId: string,
  ref: ArtifactRef,
): string | null {
  const uri = ref.uri.replace(/\\/g, "/");

  if (uri.startsWith("http://") || uri.startsWith("https://")) {
    return uri;
  }
  if (uri.startsWith("/api/")) {
    return uri;
  }

  const projectMarker = `projects/${projectId}/`;
  const markerIndex = uri.indexOf(projectMarker);
  if (markerIndex >= 0) {
    const relative = uri.slice(markerIndex + projectMarker.length);
    if (relative) {
      const segments = relative.split("/").map(encodeURIComponent).join("/");
      return `/api/projects/${projectId}/media/file/${segments}`;
    }
  }

  if (ref.type === "html" || ref.type === "render") {
    return `/api/projects/${projectId}/media/artifacts/${encodeURIComponent(ref.id)}`;
  }

  return null;
}

/** Browser URL for HyperFrames composition player (preferred for inline preview). */
export function generationCompositionPreviewUrl(
  projectId: string,
  generationId: string,
): string {
  const segments = ["renders", generationId, "composition", "index.html"]
    .map(encodeURIComponent)
    .join("/");
  return `/api/projects/${projectId}/media/file/${segments}`;
}

/** Browser URL for HyperFrames preview.html wrapper (iframe shell). */
export function generationRenderPreviewUrl(
  projectId: string,
  generationId: string,
): string {
  const segments = ["renders", generationId, "preview.html"]
    .map(encodeURIComponent)
    .join("/");
  return `/api/projects/${projectId}/media/file/${segments}`;
}

/** Browser URL for a project storage file under `projects/{projectId}/`. */
export function projectFileMediaUrl(
  projectId: string,
  relativePath: string,
): string {
  const segments = relativePath
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean)
    .map(encodeURIComponent)
    .join("/");
  return `/api/projects/${projectId}/media/file/${segments}`;
}

/** Browser URL for preview TTS master.wav under generations/{generationId}/preview/ */
export function generationNarrationPreviewAudioUrl(
  projectId: string,
  generationId: string,
): string {
  return projectFileMediaUrl(
    projectId,
    `generations/${generationId}/preview/master.wav`,
  );
}

/** Browser URL for rendered demo MP4 when the HyperFrames CLI produced output.mp4 */
export function generationRenderVideoUrl(
  projectId: string,
  generationId: string,
): string {
  const segments = ["renders", generationId, "output.mp4"]
    .map(encodeURIComponent)
    .join("/");
  return `/api/projects/${projectId}/media/file/${segments}`;
}
