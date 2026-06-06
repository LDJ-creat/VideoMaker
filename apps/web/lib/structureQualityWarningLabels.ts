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

export type StructureQualitySeverity = "critical" | "warn" | "info";

export type ParsedStructureQualityWarning = {
  raw: string;
  code: string;
  severity: StructureQualitySeverity;
  message: string;
  hint?: string;
  hidden?: boolean;
};

function slotRoleLabel(role: string): string {
  return SLOT_ROLE_LABELS[role] ?? role;
}

function segmentLabel(segmentId: string): string {
  return segmentId.replace(/^seg-?/i, "段 ").trim();
}

export function parseStructureQualityWarning(raw: string): ParsedStructureQualityWarning {
  let text = raw.trim();
  let severity: StructureQualitySeverity = "warn";

  if (text.startsWith("critical:")) {
    severity = "critical";
    text = text.slice("critical:".length).trim();
  }

  if (text.startsWith("analysis_route:")) {
    return {
      raw,
      code: text.split(":")[0] ?? "analysis_route",
      severity: "info",
      hidden: true,
      message: "本次样例走直连多模态分析路径。",
    };
  }

  if (text === "narrative_summary_repeats_segments") {
    return {
      raw,
      code: text,
      severity: "warn",
      message: "全片摘要与各段描述高度重复，缺少更高层的结构概括。",
      hint: "生成迁移方案时可能难以快速把握整体叙事骨架。",
    };
  }

  if (text.startsWith("slot_roles_uniform:")) {
    const role = text.slice("slot_roles_uniform:".length);
    return {
      raw,
      code: "slot_roles_uniform",
      severity: "critical",
      message: `结构槽类型过于单一：所有槽位均为「${slotRoleLabel(role)}」。`,
      hint: "槽位区分不足会影响素材匹配与迁移；存在严重提示时无法加入知识库。",
    };
  }

  if (text.startsWith("missing_transcript_excerpt:")) {
    const segmentId = text.slice("missing_transcript_excerpt:".length);
    return {
      raw,
      code: "missing_transcript_excerpt",
      severity: "critical",
      message: `${segmentLabel(segmentId)} 缺少口播摘录（transcriptExcerpt）。`,
      hint: "口播摘录用于核对 ASR 依据；存在严重提示时无法加入知识库。",
    };
  }

  if (text.startsWith("locale_not_chinese:")) {
    return {
      raw,
      code: "locale_not_chinese",
      severity: "critical",
      message: "全片摘要中英文占比过高，与当前中文分析设定不一致。",
      hint: "存在严重提示时无法加入知识库。",
    };
  }

  if (text.startsWith("segment_intent_short:")) {
    const segmentId = text.slice("segment_intent_short:".length);
    return {
      raw,
      code: "segment_intent_short",
      severity: "warn",
      message: `${segmentLabel(segmentId)} 的段落意图（intent）过短，解释性不足。`,
    };
  }

  if (text.startsWith("segment_summary_duplicate:")) {
    const segmentId = text.slice("segment_summary_duplicate:".length);
    return {
      raw,
      code: "segment_summary_duplicate",
      severity: "warn",
      message: `${segmentLabel(segmentId)} 的画面概要与口播手法描述几乎相同。`,
      hint: "理想情况下画面与口播应分别描述镜头手法与修辞策略。",
    };
  }

  if (text.startsWith("missing_migration_template:")) {
    const slotId = text.slice("missing_migration_template:".length);
    return {
      raw,
      code: "missing_migration_template",
      severity: "warn",
      message: `结构槽 ${slotId} 缺少迁移模板（migrationTemplate）。`,
      hint: "迁移模板说明如何把该槽位映射到新主题素材。",
    };
  }

  if (text.startsWith("segment_") && text.endsWith("_vision_skipped_digest_coverage")) {
    const segmentId = text.slice("segment_".length, -"_vision_skipped_digest_coverage".length);
    return {
      raw,
      code: "vision_skipped_digest_coverage",
      severity: "warn",
      message: `${segmentLabel(segmentId)} 跳过了分段视觉分析（批次 digest 已覆盖该时段）。`,
      hint: "这是成本优化行为，通常不影响整体结构，但段级画面细节可能较薄。",
    };
  }

  if (text.startsWith("critic_repair_failed:")) {
    return {
      raw,
      code: "critic_repair_failed",
      severity: "warn",
      message: "结构质检 Agent 未能自动修复校验问题。",
    };
  }

  if (text.startsWith("critic_skipped:")) {
    return {
      raw,
      code: "critic_skipped",
      severity: "warn",
      message: "结构质检 Agent 已跳过（模型不可用或超时）。",
    };
  }

  if (text.startsWith("keyframe_sampling_applied:")) {
    return {
      raw,
      code: "keyframe_sampling_applied",
      severity: "info",
      message: "关键帧已抽样压缩以控制分析成本。",
    };
  }

  return {
    raw,
    code: text.split(":")[0] ?? text,
    severity,
    message: text,
    hint: "此为系统内部质量码，如需排查请联系开发。",
  };
}

export function formatStructureQualityWarnings(
  warnings: string[],
): ParsedStructureQualityWarning[] {
  return warnings
    .map(parseStructureQualityWarning)
    .filter((item) => !item.hidden);
}

export function hasCriticalStructureQualityWarnings(warnings: string[]): boolean {
  return warnings.some((raw) => parseStructureQualityWarning(raw).severity === "critical");
}

export function structureQualitySeverityLabel(
  severity: StructureQualitySeverity,
): string {
  switch (severity) {
    case "critical":
      return "严重";
    case "info":
      return "说明";
    default:
      return "注意";
  }
}
