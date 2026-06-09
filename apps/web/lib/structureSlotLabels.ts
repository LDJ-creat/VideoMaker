const SLOT_ROLE_LABELS: Record<string, string> = {
  hook_visual: "开场画面",
  hook_text: "开场文案",
  product_closeup: "产品特写",
  usage_scene: "使用场景",
  benefit_card: "卖点卡片",
  comparison: "对比",
  proof: "证明",
  transition: "转场",
  cta: "行动号召",
};

export function structureSlotRoleLabel(role: string | undefined): string {
  if (!role) return "结构槽位";
  return SLOT_ROLE_LABELS[role] ?? role;
}
