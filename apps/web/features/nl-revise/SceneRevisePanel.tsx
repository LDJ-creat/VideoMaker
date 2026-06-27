"use client";

import type { SceneReviseRequest, SceneVisualEditMode } from "@videomaker/contracts";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  buildSceneReviseRequest,
  chainHint,
  SCENE_VISUAL_EDIT_MODE_HINTS,
  SCENE_VISUAL_EDIT_MODE_LABELS,
  SCENE_VISUAL_EDIT_MODES,
  type SlotChainKind,
} from "@/lib/sceneRevise";
import { cn } from "@/lib/utils";

type SceneRevisePanelProps = {
  sceneId: string;
  slotId: string;
  index: number;
  chainKind?: SlotChainKind;
  disabled?: boolean;
  busy?: boolean;
  onSubmit: (request: SceneReviseRequest) => Promise<void>;
  className?: string;
};

export function SceneRevisePanel({
  sceneId,
  slotId,
  index,
  chainKind,
  disabled,
  busy,
  onSubmit,
  className,
}: SceneRevisePanelProps) {
  const [mode, setMode] = useState<SceneVisualEditMode>("edit");
  const [instruction, setInstruction] = useState("");

  const handleSubmit = async () => {
    if (disabled || busy) return;
    const trimmed = instruction.trim();
    if (!trimmed) return;
    const request = buildSceneReviseRequest({
      sceneId,
      slotId,
      mode,
      instruction: trimmed,
    });
    await onSubmit(request);
  };

  const chainModeHint = chainHint(chainKind, mode);

  return (
    <div
      className={cn("mt-3 space-y-3 rounded-md border border-border bg-muted/20 p-3", className)}
      data-testid={`scene-revise-panel-${sceneId}`}
    >
      <p className="text-sm font-medium">修改/重生成画面 · 第 {index + 1} 镜</p>

      <fieldset className="space-y-2" disabled={disabled || busy}>
        <legend className="text-sm font-medium">修改模式</legend>
        <div className="flex flex-col gap-2 sm:flex-row">
          {SCENE_VISUAL_EDIT_MODES.map((item) => (
            <label
              key={item}
              className={cn(
                "flex flex-1 cursor-pointer gap-2 rounded-md border border-border px-3 py-2 text-sm",
                mode === item && "border-primary bg-primary/5",
              )}
            >
              <input
                type="radio"
                name={`scene-revise-mode-${sceneId}`}
                value={item}
                checked={mode === item}
                onChange={() => setMode(item)}
                className="mt-0.5"
                aria-label={SCENE_VISUAL_EDIT_MODE_LABELS[item]}
              />
              <span>
                <span className="font-medium">{SCENE_VISUAL_EDIT_MODE_LABELS[item]}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  {SCENE_VISUAL_EDIT_MODE_HINTS[item]}
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="space-y-2">
        <Label htmlFor={`scene-revise-instruction-${sceneId}`}>修改说明（必填）</Label>
        <Textarea
          id={`scene-revise-instruction-${sceneId}`}
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={3}
          disabled={disabled || busy}
          placeholder={
            mode === "edit"
              ? "例如：字幕居中，动效更大，底片不变"
              : "例如：改成更明快的城市风，或整体赛博朋克风格"
          }
        />
        <p className="text-xs text-muted-foreground">
          {chainModeHint ?? "口播与其它镜不变；确认后将生成改片方案。"}
        </p>
      </div>

      <Button
        type="button"
        size="sm"
        disabled={disabled || busy || !instruction.trim()}
        onClick={() => void handleSubmit()}
        data-testid={`scene-revise-submit-${sceneId}`}
      >
        {busy ? "正在生成方案…" : "生成改片方案"}
      </Button>
    </div>
  );
}
