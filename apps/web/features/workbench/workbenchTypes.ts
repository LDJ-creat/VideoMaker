export type WorkbenchPanel =
  | "input"
  | "progress"
  | "script-review"
  | "analysis"
  | "narration"
  | "result"
  | "knowledge";

export const PANEL_LABELS: Record<WorkbenchPanel, string> = {
  input: "录入",
  progress: "进度",
  "script-review": "脚本审核",
  analysis: "样例分析",
  narration: "全片拆解",
  result: "结果",
  knowledge: "知识库",
};
