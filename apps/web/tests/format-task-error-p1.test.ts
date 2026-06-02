import { describe, expect, it } from "vitest";

import { formatTaskError } from "@/lib/formatTaskError";

describe("formatTaskError P1 codes", () => {
  it("maps gateway_not_configured", () => {
    const result = formatTaskError({
      code: "gateway_not_configured",
      message: "TEXT_API_KEY missing",
      retryable: true,
    });
    expect(result?.title).toBe("模型服务未配置");
    expect(result?.hint).toMatch(/模型服务/);
  });

  it("maps video_quota_exceeded", () => {
    const result = formatTaskError({
      code: "video_quota_exceeded",
      message: "quota used",
      retryable: false,
    });
    expect(result?.hint).toMatch(/1 次生视频配额/);
  });

  it("maps hyperframes_missing", () => {
    const result = formatTaskError({
      code: "hyperframes_missing",
      message: "cli not found",
      retryable: true,
    });
    expect(result?.title).toMatch(/HyperFrames/);
  });

  it("maps LLMValidationError", () => {
    const result = formatTaskError({
      code: "LLMValidationError",
      message: "invalid json",
      retryable: true,
    });
    expect(result?.hint).toMatch(/可点击重试|可重试/);
  });
});
