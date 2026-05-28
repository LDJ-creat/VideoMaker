import type { GapReport } from "@videomaker/contracts";

export const fixtureGapReport: GapReport = {
  id: "gap-demo-001",
  projectId: "proj-demo-001",
  structureId: "vs-demo-001",
  inventoryId: "inv-demo-001",
  summary: "钩子槽匹配良好；CTA 字幕素材偏弱；缺少对比镜头",
  slotMatches: [
    {
      slotId: "slot-hook-visual",
      assetId: "asset-user-01",
      matchScore: 0.92,
      matchReason: "用户素材包含同类产品痛点开场",
    },
    {
      slotId: "slot-product",
      assetId: "asset-user-02",
      matchScore: 0.78,
      matchReason: "产品演示片段时长足够但光线偏暗",
    },
  ],
  weakSlots: [
    {
      slotId: "slot-benefit",
      reason: "仅有文案草稿，缺少配套包装字幕样式",
      impact: "medium",
      suggestedFixes: ["packaging_completion", "text_completion"],
    },
  ],
  missingSlots: [
    {
      slotId: "slot-cta",
      reason: "未上传带价格信息的结尾画面或贴纸素材",
      impact: "high",
      suggestedFixes: ["image_generation", "packaging_completion"],
    },
  ],
};
