/** FastAPI backend URL — server-only, never exposed to the browser. */
export function getBackendApiUrl(): string {
  return process.env.VIDEOMAKER_API_URL ?? "http://127.0.0.1:8000";
}

/** When true, BFF returns fixture JSON on upstream failure with X-Videomaker-Data-Source: fixture. */
export function shouldUseFixtureFallback(): boolean {
  return process.env.VIDEOMAKER_USE_FIXTURE_FALLBACK === "true";
}

export const DATA_SOURCE_HEADER = "X-Videomaker-Data-Source";
