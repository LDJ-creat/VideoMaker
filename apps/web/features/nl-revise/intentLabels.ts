import type {
  EditExecutionTool,
  EditIntentItem,
  EditIntentOperation,
  EditIntentTarget,
  RevisePlanSource,
} from "@videomaker/contracts";

export const EDIT_INTENT_TARGET_LABELS: Record<EditIntentTarget, string> = {
  "generation_plan.storyboard": "分镜",
  "generation_plan.packaging": "包装",
  render_timeline: "时间线",
  generation_params: "生成参数",
};

export const EDIT_INTENT_OPERATION_LABELS: Record<EditIntentOperation, string> =
  {
    adjust_hook: "强化开头 hook",
    reduce_subtitles: "减少字幕",
    increase_subtitles: "增加字幕",
    reorder_selling_points: "调整卖点顺序",
    change_pace: "调整节奏",
    change_packaging_style: "更换包装风格",
    adjust_cta: "调整 CTA",
    subtitle_patch: "字幕轨修补",
    timeline_scene_patch: "分镜时长调整",
    packaging_scene_patch: "单镜包装 overlay",
  };

export const EDIT_INTENT_EXECUTION_TOOL_LABELS: Record<
  EditExecutionTool,
  string
> = {
  subtitle_patch: "字幕轨修补",
  timeline_scene_patch: "分镜时长调整",
  packaging_scene_patch: "单镜包装 overlay",
  script_revise: "分镜脚本改写",
  packaging_agent: "全片包装重设计",
  storyboard_agent: "分镜脚本重生成",
  material_regen: "单镜素材重生成",
  full_pipeline: "全链路重跑",
};

export const EDIT_INTENT_LIST_DESCRIPTION: Record<RevisePlanSource, string> = {
  nl: "AI 已从自然语言指令解析出以下结构化改片步骤",
  scene_structured:
    "以下为分镜结构化改片步骤（规则生成，未调用改片规划 LLM）",
};

/** Prefer executionTool (+ materialEditMode) over legacy operation label. */
export function resolveEditIntentDisplayLabel(intent: EditIntentItem): string {
  const tool = intent.executionTool;
  if (tool === "material_regen") {
    const mode = intent.params?.materialEditMode;
    if (mode === "full") return "单镜完全重生成";
    if (mode === "edit") return "单镜微调修改";
    return EDIT_INTENT_EXECUTION_TOOL_LABELS.material_regen;
  }
  if (tool && tool in EDIT_INTENT_EXECUTION_TOOL_LABELS) {
    return EDIT_INTENT_EXECUTION_TOOL_LABELS[tool];
  }
  return (
    EDIT_INTENT_OPERATION_LABELS[intent.operation] ?? intent.operation
  );
}

export function resolveEditIntentListDescription(
  planSource?: RevisePlanSource,
): string {
  if (planSource && planSource in EDIT_INTENT_LIST_DESCRIPTION) {
    return EDIT_INTENT_LIST_DESCRIPTION[planSource];
  }
  return EDIT_INTENT_LIST_DESCRIPTION.nl;
}
