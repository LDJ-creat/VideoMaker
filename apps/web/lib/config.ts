/** API base URL for VideoMaker backend (FastAPI). */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

/**
 * When true, apiClient returns fixture data after a failed real API call.
 * Set NEXT_PUBLIC_USE_FIXTURES=false to require live API only.
 */
export function shouldUseFixtureFallback(): boolean {
  return process.env.NEXT_PUBLIC_USE_FIXTURES !== "false";
}
