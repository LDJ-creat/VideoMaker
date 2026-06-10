"use client";

import type { RevisePlan } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EditIntentList } from "@/features/nl-revise/EditIntentList";
import { cn } from "@/lib/utils";

const COST_TIER_LABELS: Record<RevisePlan["costTier"], string> = {
  low: "低成本",
  medium: "中等成本",
  high: "高成本",
};

type RevisePlanCardProps = {
  plan: RevisePlan;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void | Promise<void>;
  onReviseInstruction?: () => void;
  busy?: boolean;
  className?: string;
};

export function RevisePlanCard({
  plan,
  onConfirm,
  onCancel,
  onReviseInstruction,
  busy,
  className,
}: RevisePlanCardProps) {
  return (
    <Card className={cn("border-ai/30", className)} data-testid="revise-plan-card">
      <CardHeader>
        <CardTitle>改片方案</CardTitle>
        <CardDescription>请确认以下方案后再执行</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">{plan.summary}</p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{COST_TIER_LABELS[plan.costTier]}</Badge>
          <Badge variant="secondary">
            {plan.executionMode === "in_place" ? "就地更新" : "Fork 新版本"}
          </Badge>
          {plan.requiresFullRender && (
            <Badge variant="outline">需整片重渲染</Badge>
          )}
        </div>
        {plan.affectedSceneIds && plan.affectedSceneIds.length > 0 && (
          <p className="text-xs text-muted-foreground">
            受影响分镜：{plan.affectedSceneIds.join("、")}
          </p>
        )}
        {plan.affectedSlotIds && plan.affectedSlotIds.length > 0 && (
          <p className="text-xs text-muted-foreground">
            受影响槽位：{plan.affectedSlotIds.join("、")}
            {plan.executionMode === "fork" && plan.intents.some((i) => i.executionTool === "material_regen")
              ? "（仅重生成这些槽位素材）"
              : plan.executionMode === "in_place" &&
                  plan.intents.some((i) => i.executionTool === "packaging_scene_patch")
                ? "（就地更新包装 overlay，保留已有素材）"
                : null}
          </p>
        )}
        {plan.executionSteps.length > 0 && (
          <ul className="space-y-1 text-sm text-muted-foreground">
            {plan.executionSteps.map((step, index) => (
              <li key={`${step.tool}-${index}`}>
                {step.description ?? step.tool}
              </li>
            ))}
          </ul>
        )}
        <EditIntentList intents={plan.intents} />
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={busy} onClick={() => void onConfirm()}>
            {busy ? "正在执行…" : "确认执行"}
          </Button>
          {onReviseInstruction && (
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onReviseInstruction}
            >
              修改指令
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            onClick={() => void onCancel()}
          >
            取消
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
