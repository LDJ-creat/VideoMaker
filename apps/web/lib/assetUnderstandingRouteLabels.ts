import type { TaskEvent } from "@videomaker/contracts";

export type AssetUnderstandingRouteHint =
  | "direct_multimodal"
  | "direct_multimodal_batched"
  | "legacy";

const ROUTE_LABELS: Record<AssetUnderstandingRouteHint, string> = {
  direct_multimodal: "直连多模态资产理解",
  direct_multimodal_batched: "直连多模态（分批）",
  legacy: "传统资产理解",
};

export function inferAssetUnderstandingRouteFromEvent(
  event: TaskEvent | null | undefined,
): AssetUnderstandingRouteHint | null {
  const message = event?.message ?? "";
  if (!message) {
    return null;
  }
  if (message.includes("Direct multimodal asset batch")) {
    return "direct_multimodal_batched";
  }
  if (message.includes("Direct multimodal user asset")) {
    return "direct_multimodal";
  }
  if (message.includes("Direct multimodal asset")) {
    return "direct_multimodal";
  }
  if (message.includes("(legacy)")) {
    return "legacy";
  }
  return null;
}

export function assetUnderstandingRouteLabel(
  route: AssetUnderstandingRouteHint,
): string {
  return ROUTE_LABELS[route];
}
