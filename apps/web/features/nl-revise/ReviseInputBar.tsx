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

type ReviseInputBarProps = {
  onSubmit: (instruction: string) => void | Promise<void>;
  disabled?: boolean;
  busy?: boolean;
  className?: string;
};

export function ReviseInputBar({
  onSubmit,
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
          描述你想调整的内容，例如「开头更抓人」「减少字幕」
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="输入改片指令…"
          rows={3}
          disabled={disabled || busy}
          aria-label="改片指令"
        />
        <Button
          type="button"
          disabled={disabled || busy || instruction.trim().length === 0}
          onClick={() => void handleSubmit()}
        >
          {busy ? "正在提交改片…" : "提交改片"}
        </Button>
      </CardContent>
    </Card>
  );
}
