/** Canonical VideoStructure slot roles — keep in sync with services/shared/structure/slot_roles.py */

export const SLOT_ROLE_ENUM = [
  "hook_visual",
  "hook_text",
  "product_closeup",
  "usage_scene",
  "benefit_card",
  "comparison",
  "proof",
  "transition",
  "cta",
] as const;

export type StructureSlotRoleConst = (typeof SLOT_ROLE_ENUM)[number];

export const PACKAGING_ROLES: readonly StructureSlotRoleConst[] = [
  "hook_text",
  "benefit_card",
  "comparison",
  "proof",
  "transition",
  "cta",
];

export const GAP_HYPERFRAMES_PRIMARY_ROLES: readonly StructureSlotRoleConst[] = [
  "hook_text",
  "benefit_card",
  "comparison",
  "transition",
  "cta",
];

export const VISUAL_ROLES: readonly StructureSlotRoleConst[] = [
  "hook_visual",
  "product_closeup",
  "usage_scene",
];

export const STOCK_GENERIC_VISUAL_ROLES: readonly StructureSlotRoleConst[] = [
  "hook_visual",
  "usage_scene",
];

/** Deprecated aliases (scheme 1) → canonical enum value */
export const SLOT_ROLE_ALIASES: Record<string, StructureSlotRoleConst> = {
  demonstration: "usage_scene",
  demo: "usage_scene",
  tutorial: "usage_scene",
  attention_grabber: "hook_visual",
  intro: "hook_visual",
  pain_point: "proof",
  problem_visual: "proof",
  problem: "proof",
  product_intro: "product_closeup",
  solution: "product_closeup",
  benefit: "benefit_card",
  call_to_action: "cta",
  cta_visual: "cta",
  hook: "hook_visual",
  proof: "proof",
  comparison: "comparison",
  transition: "transition",
};

export const ROLE_GLOSSARY_ZH: Record<StructureSlotRoleConst, string> = {
  hook_visual: "开场注意力画面，强调停滑与视觉冲击，不一定是产品本体",
  hook_text: "开场/on-screen 文字包装（标题、悬念句、数字钩子）",
  product_closeup: "特定主体/商品/SKU 特写，画面必须可识别该主体，禁止通用素材库替代",
  usage_scene: "通用场景 B-roll、生活方式、操作演示、教程步骤（非 SKU 绑定）",
  benefit_card: "卖点/利益点信息卡（文字 + 动效包装）",
  comparison: "对比/前后/竞品对照信息卡",
  proof: "证言、数据、案例或信任状（口播或包装卡）",
  transition: "段间转场/过渡包装",
  cta: "行动号召结尾包装",
};

export function normalizeSlotRole(
  role: string,
  defaultRole: StructureSlotRoleConst = "usage_scene",
): StructureSlotRoleConst {
  const raw = role.trim();
  if ((SLOT_ROLE_ENUM as readonly string[]).includes(raw)) {
    return raw as StructureSlotRoleConst;
  }
  const lowered = raw.toLowerCase();
  const slug = lowered.replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const compact = slug.replace(/_/g, "");
  for (const key of [lowered, slug, compact]) {
    if (!key) continue;
    const mapped = SLOT_ROLE_ALIASES[key];
    if (mapped) return mapped;
  }
  return defaultRole;
}

export function defaultRequiredAssetTypes(role: string): string[] {
  const normalized = normalizeSlotRole(role);
  if ((PACKAGING_ROLES as readonly string[]).includes(normalized)) {
    return ["text", "packaging"];
  }
  return ["video", "image"];
}
