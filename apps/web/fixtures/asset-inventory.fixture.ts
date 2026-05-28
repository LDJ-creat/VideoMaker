import type { AssetInventory } from "@videomaker/contracts";

export const fixtureAssetInventory: AssetInventory = {
  id: "inv-demo-001",
  projectId: "proj-demo-001",
  userBrief: {
    topic: "夏季防晒喷雾",
    productName: "清爽防护 SPF50+",
    sellingPoints: ["轻薄不黏", "12 小时防护", "敏感肌可用"],
    targetAudience: "18-30 岁都市女性",
    tone: "活力、可信",
    mustMention: ["SPF50+", "无酒精"],
    avoidMention: ["医疗功效", "绝对美白"],
  },
  assets: [
    {
      id: "asset-user-01",
      type: "video",
      uri: "storage/projects/proj-demo-001/assets/hook.mp4",
      description: "户外痛点开场",
      durationSec: 4,
    },
    {
      id: "asset-user-02",
      type: "video",
      uri: "storage/projects/proj-demo-001/assets/product.mp4",
      description: "产品使用演示",
      durationSec: 8,
    },
  ],
  extractedFacts: [
    {
      id: "fact-1",
      kind: "selling_point",
      text: "轻薄不黏",
      source: "brief",
    },
  ],
  candidateMoments: [
    {
      id: "moment-1",
      assetId: "asset-user-01",
      startSec: 0.5,
      endSec: 3.2,
      description: "阳光刺眼揉眼镜头",
      tags: ["hook", "pain"],
    },
  ],
};
