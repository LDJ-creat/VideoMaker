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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { UserBriefRequest } from "@/lib/apiClient";
import { saveBrief } from "@/lib/apiClient";

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

type BriefEditorProps = {
  apiBaseUrl: string;
  projectId: string;
  onSaved?: (brief: UserBriefRequest) => void;
};

export function BriefEditor({
  apiBaseUrl,
  projectId,
  onSaved,
}: BriefEditorProps) {
  const [topic, setTopic] = useState("");
  const [productName, setProductName] = useState("");
  const [sellingPoints, setSellingPoints] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [tone, setTone] = useState("");
  const [mustMention, setMustMention] = useState("");
  const [avoidMention, setAvoidMention] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const buildBrief = (): UserBriefRequest => ({
    topic: topic || undefined,
    productName: productName || undefined,
    sellingPoints: splitLines(sellingPoints),
    targetAudience: targetAudience || undefined,
    tone: tone || undefined,
    mustMention: splitLines(mustMention),
    avoidMention: splitLines(avoidMention),
  });

  const handleSave = async () => {
    const brief = buildBrief();
    setStatus(null);
    try {
      await saveBrief(apiBaseUrl, projectId, brief);
      setStatus("Brief 已保存");
      onSaved?.(brief);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "保存失败");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>创作 Brief</CardTitle>
        <CardDescription>结构化输入，驱动素材分析与槽位映射</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="brief-topic">主题</Label>
          <Input
            id="brief-topic"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief-product">产品名</Label>
          <Input
            id="brief-product"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="brief-selling">卖点（每行一条）</Label>
          <Textarea
            id="brief-selling"
            value={sellingPoints}
            onChange={(e) => setSellingPoints(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief-audience">目标受众</Label>
          <Input
            id="brief-audience"
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief-tone">语气</Label>
          <Input
            id="brief-tone"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief-must">必须提及（每行一条）</Label>
          <Textarea
            id="brief-must"
            value={mustMention}
            onChange={(e) => setMustMention(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="brief-avoid">禁止提及（每行一条）</Label>
          <Textarea
            id="brief-avoid"
            value={avoidMention}
            onChange={(e) => setAvoidMention(e.target.value)}
          />
        </div>
        <div className="md:col-span-2 flex items-center gap-3">
          <Button type="button" onClick={() => void handleSave()}>
            保存 Brief
          </Button>
          {status && (
            <p className="text-sm text-muted-foreground" role="status">
              {status}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
