import type { TaskStage } from "@videomaker/contracts";

export const TASK_STAGE_LABELS: Record<TaskStage, string> = {
  uploading: "上传中",
  extracting_metadata: "提取元信息",
  extracting_audio: "提取音频",
  transcribing: "语音转写",
  detecting_shots: "镜头切分",
  extracting_keyframes: "提取关键帧",
  extracting_structure: "结构拆解",
  analyzing_assets: "分析素材",
  mapping_slots: "槽位匹配",
  planning_completion: "缺口规划",
  generating_storyboard: "生成分镜",
  building_timeline: "构建时间线",
  rendering: "渲染视频",
  completed: "已完成",
  running_agent: "运行 AI 分析",
  generating_material: "生成补全素材",
  generating_image: "AI 生图",
  generating_video: "AI 生视频",
  generating_tts: "合成配音",
  rendering_material: "渲染包装片段",
  parsing_edit_intent: "理解改片指令",
  applying_edit_intent: "应用改片",
};

const MATERIAL_STAGES = new Set<TaskStage>([
  "generating_material",
  "generating_image",
  "generating_video",
  "generating_tts",
  "rendering_material",
]);

export function getTaskStageLabel(stage: TaskStage): string {
  return TASK_STAGE_LABELS[stage] ?? stage;
}

export function isMaterialStage(stage: TaskStage): boolean {
  return MATERIAL_STAGES.has(stage);
}
