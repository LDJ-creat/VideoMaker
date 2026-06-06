import type {
  ContentCategory,
  StructureAudioLayer,
  TransferMetadata,
  VerbalLayer,
  VisualLayer,
} from "@videomaker/contracts";

export const STRUCTURE_V3_TRACK_LABELS = {
  verbal: "文本轨",
  visual: "视觉轨",
  audio: "听觉轨",
  transfer: "策略轨",
} as const;

export type StructureV3TrackId = keyof typeof STRUCTURE_V3_TRACK_LABELS;

const CONTENT_CATEGORY_LABELS: Record<ContentCategory, string> = {
  product_commerce: "带货电商",
  education: "知识教育",
  vlog_lifestyle: "生活方式 Vlog",
  brand_story: "品牌故事",
  tutorial: "教程实操",
  entertainment: "娱乐剧情",
  news_commentary: "资讯评论",
  general: "通用",
};

const PRIMARY_INTENT_LABELS: Record<string, string> = {
  exposure: "拉新曝光",
  consideration: "种草心智",
  conversion: "促进转化",
};

export function contentCategoryLabel(value: string | undefined): string {
  if (!value) return "未标注";
  return CONTENT_CATEGORY_LABELS[value as ContentCategory] ?? value;
}

export function primaryIntentLabel(value: string | undefined): string {
  if (!value) return "未标注";
  return PRIMARY_INTENT_LABELS[value] ?? value;
}

export function verbalFieldLabel(field: keyof VerbalLayer | string): string {
  const labels: Record<string, string> = {
    hookTemplate: "Hook 模板",
    outlineTimeline: "论证时间线",
    ctaMechanism: "CTA 机制",
    infoLubricantRatio: "信息/润滑比",
    phase: "阶段",
    startSec: "起始",
    endSec: "结束",
    sharePct: "时长占比",
    infoSec: "信息秒数",
    lubricantSec: "润滑秒数",
    ratio: "比例",
  };
  return labels[field] ?? field;
}

export function visualFieldLabel(field: keyof VisualLayer | string): string {
  const labels: Record<string, string> = {
    conceptVisualMap: "概念-画面映射",
    cutRateProfile: "切镜节奏",
    packagingSpec: "包装规格",
    concept: "概念",
    visualMetaphor: "视觉隐喻",
    timeSec: "时间点",
    assetHint: "素材提示",
    avgShotSec: "平均镜头时长",
    openingCutRate: "开场切镜密度",
    fastCutRanges: "快切区间",
    visualDensity: "视觉密度",
    summary: "概要",
  };
  return labels[field] ?? field;
}

export function audioFieldLabel(field: keyof StructureAudioLayer | string): string {
  const labels: Record<string, string> = {
    voProfile: "口播画像",
    audioEventRules: "音频事件规则",
    pace: "语速",
    energy: "能量",
    persona: "人设",
    wordsPerMinute: "字/分钟",
    trigger: "触发条件",
    action: "动作",
  };
  return labels[field] ?? field;
}

export function transferFieldLabel(field: keyof TransferMetadata | string): string {
  const labels: Record<string, string> = {
    structureFamily: "结构族",
    differentiationLever: "差异化杠杆",
    emotionTriggers: "情绪触发点",
    scalabilityRules: "可扩展规则",
    nonTransferableElements: "不可迁移元素",
    materialRequirementsSummary: "素材需求摘要",
    triggerType: "触发类型",
    segmentId: "关联分段",
    mechanism: "机制",
  };
  return labels[field] ?? field;
}

export function outlinePhaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    hook: "开场钩子",
    problem: "痛点",
    solution: "方案",
    proof: "证明",
    benefit: "卖点",
    comparison: "对比",
    cta: "行动号召",
    transition: "过渡",
  };
  return labels[phase] ?? phase;
}

export function tempoLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    slow: "慢",
    medium: "中",
    fast: "快",
    mixed: "混合",
  };
  if (!value) return "未标注";
  return labels[value] ?? value;
}

export function visualDensityLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
  };
  if (!value) return "未标注";
  return labels[value] ?? value;
}
