export class ApiClientError extends Error {
  code: string;
  status?: number;

  constructor(message: string, code = "API_ERROR", status?: number) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
  }
}

/** Turn FastAPI `detail` (string, array of validation errors, or object) into user text. */
export function formatFastApiDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (!Array.isArray(detail)) {
    return null;
  }
  const parts = detail
    .map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object") {
        const entry = item as { loc?: unknown; msg?: unknown };
        const msg =
          typeof entry.msg === "string"
            ? entry.msg
            : entry.msg != null
              ? String(entry.msg)
              : String(item);
        if (Array.isArray(entry.loc) && entry.loc.length > 0) {
          const path = entry.loc
            .filter((part) => part !== "body")
            .map(String)
            .join(".");
          return path ? `${path}: ${msg}` : msg;
        }
        return msg;
      }
      return String(item);
    })
    .filter(Boolean);
  return parts.length > 0 ? parts.join("; ") : null;
}

export function getErrorMessage(err: unknown): string {
  if (err instanceof ApiClientError) {
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  if (
    typeof err === "object" &&
    err !== null &&
    "message" in err &&
    typeof (err as { message: unknown }).message === "string"
  ) {
    return (err as { message: string }).message;
  }
  return "请求失败，请稍后重试";
}

/** Transient 404 while worker persists generation-plan.json after task terminal. */
export function isGenerationPlanNotReadyError(err: unknown): boolean {
  if (!(err instanceof ApiClientError)) return false;
  if (err.status !== 404) return false;
  return err.message.includes("Generation plan not ready");
}

/** Expected 404 before canonical TTS runs (e.g. storyboard review gate). */
export function isNarrationTimingNotReadyError(err: unknown): boolean {
  if (!(err instanceof ApiClientError)) return false;
  if (err.status !== 404) return false;
  return (
    err.message.includes("Narration timing not found") ||
    err.message.includes("Narration drift report not found")
  );
}
