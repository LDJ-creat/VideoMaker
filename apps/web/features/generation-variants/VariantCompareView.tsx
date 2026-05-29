"use client";

import type { GenerationPlan } from "@videomaker/contracts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getVariantLabel } from "@/lib/variantRegistry";

type VariantCompareViewProps = {
  plans: GenerationPlan[];
};

export function VariantCompareView({ plans }: VariantCompareViewProps) {
  if (plans.length === 0) {
    return null;
  }

  return (
    <Card data-testid="variant-compare-view">
      <CardHeader>
        <CardTitle>变体对比</CardTitle>
        <CardDescription>分镜数量、时间线时长与包装摘要</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className="rounded-lg border border-border p-4"
              data-testid={`variant-compare-${plan.variant}`}
            >
              <p className="font-medium">
                {getVariantLabel(plan.variant)}
              </p>
              <dl className="mt-2 space-y-1 text-sm text-muted-foreground">
                <div className="flex justify-between gap-4">
                  <dt>分镜数</dt>
                  <dd className="font-mono text-foreground">
                    {plan.storyboard.length}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt>时间线时长</dt>
                  <dd className="font-mono text-foreground">
                    {plan.timeline.durationSec}s
                  </dd>
                </div>
                <div>
                  <dt className="mb-1">包装摘要</dt>
                  <dd>{plan.packagingPlan.styleSummary}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
