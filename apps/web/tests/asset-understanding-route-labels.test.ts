import { describe, expect, it } from "vitest";

import type { TaskEvent } from "@videomaker/contracts";

import {
  assetUnderstandingRouteLabel,
  inferAssetUnderstandingRouteFromEvent,
} from "@/lib/assetUnderstandingRouteLabels";
import { validateAssetUploadSize } from "@/lib/validation";

describe("assetUnderstandingRouteLabels", () => {
  it("infers direct multimodal route from task message", () => {
    const event = {
      message: "Direct multimodal user asset understanding",
    } as TaskEvent;
    expect(inferAssetUnderstandingRouteFromEvent(event)).toBe("direct_multimodal");
    expect(assetUnderstandingRouteLabel("direct_multimodal")).toContain("直连");
  });

  it("infers batched route from batch message", () => {
    const event = {
      message: "Direct multimodal asset batch 2/3",
    } as TaskEvent;
    expect(inferAssetUnderstandingRouteFromEvent(event)).toBe(
      "direct_multimodal_batched",
    );
  });

  it("infers legacy route", () => {
    const event = {
      message: "Analyzing user brief and uploaded assets (legacy)",
    } as TaskEvent;
    expect(inferAssetUnderstandingRouteFromEvent(event)).toBe("legacy");
  });
});

describe("validateAssetUploadSize", () => {
  it("rejects unsupported asset types", () => {
    const file = new File(["x"], "archive.zip", {
      type: "application/zip",
    });
    expect(validateAssetUploadSize(file)).toMatch(/不支持/);
  });

  it("rejects oversized video uploads", () => {
    const file = new File([new Uint8Array(51 * 1024 * 1024)], "clip.mp4", {
      type: "video/mp4",
    });
    expect(validateAssetUploadSize(file)).toMatch(/视频/);
  });
});
