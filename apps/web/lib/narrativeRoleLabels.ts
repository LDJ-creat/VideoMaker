import type { NarrativeSegmentRole } from "@videomaker/contracts";

export const NARRATIVE_ROLE_LABELS: Record<NarrativeSegmentRole, string> = {
  hook: "开场钩子",
  problem: "痛点",
  solution: "解法",
  proof: "证明",
  benefit: "收益",
  comparison: "对比",
  cta: "行动号召",
  transition: "过渡",
};

export function narrativeRoleLabel(role: NarrativeSegmentRole | string): string {
  if (role in NARRATIVE_ROLE_LABELS) {
    return NARRATIVE_ROLE_LABELS[role as NarrativeSegmentRole];
  }
  return role;
}
