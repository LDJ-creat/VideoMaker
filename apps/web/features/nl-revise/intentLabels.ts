import type {
  EditIntentOperation,
  EditIntentTarget,
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
