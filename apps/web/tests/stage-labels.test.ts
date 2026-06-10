import { describe, expect, it } from "vitest";

import {
  getTaskStageLabel,
  isMaterialStage,
  TASK_STAGE_LABELS,
} from "@/features/tasks/stageLabels";

describe("stageLabels", () => {
  it("maps all P1 stages to Chinese labels", () => {
    expect(TASK_STAGE_LABELS.running_agent).toBe("运行 AI 分析");
    expect(TASK_STAGE_LABELS.generating_image).toBe("AI 生图");
    expect(TASK_STAGE_LABELS.parsing_edit_intent).toBe("理解改片指令");
  });

  it("getTaskStageLabel returns label for known stage", () => {
    expect(getTaskStageLabel("transcribing")).toBe("语音转写");
    expect(getTaskStageLabel("generating_material")).toBe("生成补全素材");
    expect(getTaskStageLabel("synthesizing_narration_preview")).toBe("合成口播预览");
    expect(getTaskStageLabel("aligning_narration_timing")).toBe("对齐分镜时长");
  });

  it("isMaterialStage identifies material generation stages", () => {
    expect(isMaterialStage("generating_image")).toBe(true);
    expect(isMaterialStage("rendering_material")).toBe(true);
    expect(isMaterialStage("mapping_slots")).toBe(false);
  });
});
