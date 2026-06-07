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
