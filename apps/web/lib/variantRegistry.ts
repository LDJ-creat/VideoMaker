import type { VariantDefinition } from "@videomaker/contracts";

/** Browser-safe mirror of packages/contracts/variants/registry.yaml */
const WEB_VARIANT_REGISTRY: VariantDefinition[] = [
  {
    id: "high_click",
    label: "高点击版",
    enabled: true,
    description: "更强 hook、更快节奏、前 3 秒信息密度更高",
    agentOverrides: {
      storyboard_writer: {
        hookStrength: "high",
        tempo: "fast",
        subtitleDensity: "medium",
      },
      gap_planner: {
        preferProviders: ["hyperframes_material", "video_generation"],
        videoGenPriority: "high",
      },
    },
  },
  {
    id: "high_conversion",
    label: "高转化版",
    enabled: true,
    description: "卖点提前、proof/CTA 加重、包装偏卖点卡",
    agentOverrides: {
      storyboard_writer: {
        sellingPointOrder: "early",
        ctaWeight: "high",
        subtitleDensity: "high",
      },
      gap_planner: {
        preferProviders: ["hyperframes_material", "image_generation"],
        videoGenPriority: "low",
      },
    },
  },
  {
    id: "fast_paced",
    label: "高节奏版",
    enabled: false,
    description: "",
    agentOverrides: {},
  },
  {
    id: "premium",
    label: "高质感版",
    enabled: false,
    description: "",
    agentOverrides: {},
  },
];

export function loadVariantRegistry(): VariantDefinition[] {
  return WEB_VARIANT_REGISTRY;
}

export function getEnabledVariants(): VariantDefinition[] {
  return WEB_VARIANT_REGISTRY.filter((variant) => variant.enabled);
}

export function getVariantLabel(variantId: string): string {
  return (
    WEB_VARIANT_REGISTRY.find((variant) => variant.id === variantId)?.label ??
    variantId
  );
}
