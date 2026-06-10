/** Shown when real sample structure blocks knowledge-as-primary-structure. */
export const KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_HINT =
  "已有样例分析结果，生成以样例结构为准；知识库仅作参考经验。";

export const KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_DETAIL =
  "已有样例视频的结构分析结果，知识库条目只能作为生成时的参考经验，无法替换为项目主结构。";

/** Matches API `detail` from structure-from-knowledge when blocked. */
export function isKnowledgeStructureApplyBlockedMessage(message: string): boolean {
  return (
    message.includes("参考经验") ||
    message.includes("reference only") ||
    message.includes(KNOWLEDGE_STRUCTURE_APPLY_BLOCKED_DETAIL)
  );
}

/** Max reference knowledge entries (matches auto-recommend Stage C). */
export const MAX_KNOWLEDGE_REFERENCE_ENTRIES = 2;

export const KNOWLEDGE_RECOMMENDATION_GUIDANCE_TITLE =
  "填写创作 Brief 后，系统将自动推荐匹配的知识";

export const KNOWLEDGE_RECOMMENDATION_GUIDANCE_BODY =
  "推荐知识会根据你的创作 Brief 进行匹配；完成样例视频分析后还可结合结构模式进一步提升准确度。填写并保存 Brief 前，我们不会展示可能误导的默认推荐。";

export const GENERATION_KNOWLEDGE_ONLY_HINT =
  "未分析样例视频时，将使用知识库结构作为生成骨架；填写并保存 Brief 后即可开始生成。";

export const GENERATION_KNOWLEDGE_ONLY_NO_LIBRARY =
  "暂无已发布知识库条目，无法在无样例分析时生成。请完成样例分析并 promote，或从模板库创建项目。";

export const GENERATION_REQUIRES_BRIEF_OR_SAMPLE =
  "请先填写并保存创作 Brief，或完成样例视频分析后再生成。";

export const KNOWLEDGE_RECOMMENDATION_LOADING_LABEL = "加载推荐知识…";

export const KNOWLEDGE_RECOMMENDATION_UPDATING_LABEL =
  "正在根据 Brief 更新推荐…";
