"use client";

import { Layers } from "lucide-react";
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

type ReviseInputBarProps = {
  onSubmit: (instruction: string) => void | Promise<void>;
  onGoToNarration?: () => void;
  disabled?: boolean;
  busy?: boolean;
  className?: string;
};

export function ReviseInputBar({
  onSubmit,
  onGoToNarration,
  disabled,
  busy,
  className,
}: ReviseInputBarProps) {
  const [instruction, setInstruction] = useState("");

  const handleSubmit = async () => {
    const trimmed = instruction.trim();
    if (!trimmed || disabled || busy) return;
    await onSubmit(trimmed);
    setInstruction("");
  };

  return (
    <Card className={cn(className)} data-testid="revise-input-bar">
      <CardHeader>
        <CardTitle>自然语言改片</CardTitle>
        <CardDescription>
          整片级调整（改口播、调时长、全局包装等）请用下方输入，由 AI 规划改片方案。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className="space-y-2 rounded-md border border-border/80 bg-muted/30 p-3 text-sm"
          data-testid="revise-input-guide"
        >
          <p className="font-medium text-foreground">只想改某一镜？</p>
          <p className="text-muted-foreground">
            单镜重生成画面、改包装样式、去掉字幕等，请前往「全片拆解」，在对应分镜卡片点击
            <span className="font-medium text-foreground">「改这一镜」</span>
            —— 无需 AI 规划，更快更准。
          </p>
          {onGoToNarration ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 gap-1.5"
              disabled={disabled || busy}
              onClick={onGoToNarration}
              data-testid="revise-go-to-narration"
            >
              <Layers className="h-3.5 w-3.5" aria-hidden />
              去全片拆解 · 改这一镜
            </Button>
          ) : null}
        </div>

        <Textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="例如：开头更抓人、整体字幕再少一点、最后一镜标题卡改成深色…"
          rows={3}
          disabled={disabled || busy}
          aria-label="改片指令"
        />
        <Button
          type="button"
          disabled={disabled || busy || instruction.trim().length === 0}
          onClick={() => void handleSubmit()}
        >
          {busy ? "正在提交改片…" : "提交改片（AI 规划）"}
        </Button>
      </CardContent>
    </Card>
  );
}
