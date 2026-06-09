"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ScriptNlReviseScope = "master" | "storyboard";

type ScriptNlReviseBarProps = {
  scope: ScriptNlReviseScope;
  onSubmit: (instruction: string) => void | Promise<void>;
  disabled?: boolean;
  busy?: boolean;
  className?: string;
};

const PLACEHOLDERS: Record<ScriptNlReviseScope, string> = {
  master: "例如：开头更抓人、加入价格对比、整体口语化…",
  storyboard: "例如：第 2 镜画面改成户外场景、减少第 3 镜口播字数…",
};

const DESCRIPTIONS: Record<ScriptNlReviseScope, string> = {
  master: "描述你想如何修改总脚本，AI 会基于当前草稿生成新版本。",
  storyboard: "描述你想如何修改分镜（画面或口播），总脚本已锁定不会被改写。",
};

export function ScriptNlReviseBar({
  scope,
  onSubmit,
  disabled,
  busy,
  className,
}: ScriptNlReviseBarProps) {
  const [instruction, setInstruction] = useState("");

  const handleSubmit = async () => {
    const trimmed = instruction.trim();
    if (!trimmed || disabled || busy) return;
    await onSubmit(trimmed);
    setInstruction("");
  };

  return (
    <Card className={cn("border-dashed", className)} data-testid={`script-nl-revise-${scope}`}>
      <CardHeader className="py-3">
        <CardTitle className="text-sm">自然语言改脚本</CardTitle>
        <CardDescription>{DESCRIPTIONS[scope]}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">
        <Textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder={PLACEHOLDERS[scope]}
          rows={2}
          disabled={disabled || busy}
          aria-label="脚本修改指令"
        />
        <Button
          type="button"
          variant="secondary"
          disabled={disabled || busy || instruction.trim().length === 0}
          onClick={() => void handleSubmit()}
        >
          {busy ? "AI 正在改脚本…" : "应用修改"}
        </Button>
      </CardContent>
    </Card>
  );
}
