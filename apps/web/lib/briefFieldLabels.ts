import type { ContentCategory } from "@videomaker/contracts";

export type BriefFieldLabels = {
  subjectName: string;
  keyPoints: string;
  creativeGoalPlaceholder: string;
  topicPlaceholder: string;
};

export const CONTENT_CATEGORY_OPTIONS: Array<{
  value: ContentCategory;
  label: string;
  description: string;
}> = [
  {
    value: "general",
    label: "通用",
    description: "不预设框架，由系统结合素材推断",
  },
  {
    value: "product_commerce",
    label: "带货种草",
    description: "产品推荐、好物分享、转化导向",
  },
  {
    value: "education",
    label: "知识科普",
    description: "讲解概念、干货、测评（非带货）",
  },
  {
    value: "vlog_lifestyle",
    label: "Vlog / 生活",
    description: "旅行、日常、记录向内容",
  },
  {
    value: "brand_story",
    label: "品牌故事",
    description: "品牌认知、情感表达、形象塑造",
  },
  {
    value: "tutorial",
    label: "教程",
    description: "步骤型 How-to、操作演示",
  },
  {
    value: "entertainment",
    label: "娱乐剧情",
    description: "搞笑、短剧、挑战类内容",
  },
  {
    value: "news_commentary",
    label: "资讯评论",
    description: "热点、观点、评论解读",
  },
];

const LABELS: Record<ContentCategory, BriefFieldLabels> = {
  general: {
    subjectName: "主体名称",
    keyPoints: "核心信息点（每行一条）",
    creativeGoalPlaceholder: "例如：让观众快速了解主题",
    topicPlaceholder: "视频主题",
  },
  product_commerce: {
    subjectName: "产品名",
    keyPoints: "卖点（每行一条）",
    creativeGoalPlaceholder: "例如：促进下单转化",
    topicPlaceholder: "例如：夏季防晒好物",
  },
  education: {
    subjectName: "讲解对象 / 概念",
    keyPoints: "核心知识点（每行一条）",
    creativeGoalPlaceholder: "例如：60 秒讲明白一个概念",
    topicPlaceholder: "例如：为什么天是蓝的",
  },
  vlog_lifestyle: {
    subjectName: "地点 / 人物",
    keyPoints: "记录重点（每行一条）",
    creativeGoalPlaceholder: "例如：记录旅行氛围与体验",
    topicPlaceholder: "例如：京都三日游 Day1",
  },
  brand_story: {
    subjectName: "品牌名",
    keyPoints: "品牌主张（每行一条）",
    creativeGoalPlaceholder: "例如：传递品牌理念与信任感",
    topicPlaceholder: "例如：品牌周年故事",
  },
  tutorial: {
    subjectName: "教程主题",
    keyPoints: "关键步骤 / 要点（每行一条）",
    creativeGoalPlaceholder: "例如：让观众跟着做一遍",
    topicPlaceholder: "例如：手冲咖啡入门",
  },
  entertainment: {
    subjectName: "角色 / 场景",
    keyPoints: "笑点 / 情节要点（每行一条）",
    creativeGoalPlaceholder: "例如：制造反转或共鸣",
    topicPlaceholder: "例如：办公室搞笑日常",
  },
  news_commentary: {
    subjectName: "议题 / 事件",
    keyPoints: "核心观点（每行一条）",
    creativeGoalPlaceholder: "例如：清晰表达立场与论据",
    topicPlaceholder: "例如：某热点事件解读",
  },
};

export function briefFieldLabels(
  category: ContentCategory | undefined,
): BriefFieldLabels {
  return LABELS[category ?? "general"];
}

export function defaultContentCategory(
  brief?: {
    contentCategory?: ContentCategory;
    productName?: string;
    sellingPoints?: string[];
  } | null,
): ContentCategory {
  if (brief?.contentCategory) {
    return brief.contentCategory;
  }
  if (brief?.productName || (brief?.sellingPoints?.length ?? 0) > 0) {
    return "product_commerce";
  }
  return "general";
}
