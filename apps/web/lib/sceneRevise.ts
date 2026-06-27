import type { SceneReviseRequest, SceneVisualEditMode } from "@videomaker/contracts";

export type SlotChainKind =
  | "hf_only"
  | "stock_then_hf"
  | "reuse_then_hf"
  | "image_only"
  | "video_only"
  | "image_then_hf"
  | "stock_only"
  | "unknown";

export const SCENE_VISUAL_EDIT_MODES: SceneVisualEditMode[] = ["edit", "full"];

export const SCENE_VISUAL_EDIT_MODE_LABELS: Record<SceneVisualEditMode, string> = {
  edit: "微调修改",
  full: "完全重生成",
};

export const SCENE_VISUAL_EDIT_MODE_HINTS: Record<SceneVisualEditMode, string> = {
  edit: "在现有画面上按说明调整，尽量保持风格与底层素材。",
  full: "按说明重做该镜，含重新搜索 Pexels 素材或重新 AI 生成 / HF 分镜。",
};

export const SLOT_CHAIN_KIND_HINTS: Partial<Record<SlotChainKind, Record<SceneVisualEditMode, string>>> = {
  stock_then_hf: {
    edit: "将保留 Pexels 底片，只改包装与动效。",
    full: "将重新搜索 Pexels 并重新润色。",
  },
  hf_only: {
    edit: "在现有 HF 分镜上微调。",
    full: "将重新生成 HF 分镜。",
  },
  image_only: {
    edit: "该镜为纯图片，将按完全重生成处理。",
    full: "将重新生成图片素材。",
  },
};

export function buildSceneReviseRequest(input: {
  sceneId: string;
  slotId: string;
  mode: SceneVisualEditMode;
  instruction: string;
}): SceneReviseRequest {
  return {
    sceneId: input.sceneId,
    slotId: input.slotId,
    mode: input.mode,
    instruction: input.instruction.trim(),
  };
}

export function chainHint(
  chainKind: SlotChainKind | undefined,
  mode: SceneVisualEditMode,
): string | null {
  if (!chainKind) {
    return null;
  }
  return SLOT_CHAIN_KIND_HINTS[chainKind]?.[mode] ?? null;
}
