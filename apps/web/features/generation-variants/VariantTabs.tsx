"use client";

import type { GenerationPlan } from "@videomaker/contracts";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { generationStatusLabel } from "@/lib/generationRunLabels";
import { getVariantLabel } from "@/lib/variantRegistry";

export type VariantGenerationTab = {
  generationId: string;
  variant: string;
  label?: string;
  status?: string;
  taskId?: string;
  plan?: GenerationPlan | null;
  renderVideoUrl?: string;
};

type VariantTabsProps = {
  tabs: VariantGenerationTab[];
  activeGenerationId: string;
  onActiveChange: (generationId: string) => void;
  loading?: boolean;
  retryBusy?: boolean;
  onRetryTask?: (taskId: string) => void;
  renderPlan?: (plan: GenerationPlan, tab: VariantGenerationTab) => ReactNode;
};

function FailedVariantResult({
  tab,
  retryBusy,
  onRetryTask,
}: {
  tab: VariantGenerationTab;
  retryBusy?: boolean;
  onRetryTask?: (taskId: string) => void;
}) {
  const canRetry =
    (tab.status === "failed" || tab.status === "cancelled") &&
    Boolean(tab.taskId) &&
    Boolean(onRetryTask);

  return (
    <div
      className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 p-4"
      data-testid={`variant-failed-${tab.generationId}`}
    >
      <p className="text-sm text-muted-foreground">
        变体 {tab.label ?? getVariantLabel(tab.variant)}{" "}
        {tab.status ? generationStatusLabel(tab.status) : "暂无计划数据"}
      </p>
      {canRetry ? (
        <Button
          type="button"
          size="sm"
          disabled={retryBusy}
          onClick={() => onRetryTask!(tab.taskId!)}
        >
          {retryBusy ? "正在重新提交…" : "重试生成"}
        </Button>
      ) : null}
    </div>
  );
}

export function VariantTabs({
  tabs,
  activeGenerationId,
  onActiveChange,
  loading,
  retryBusy = false,
  onRetryTask,
  renderPlan,
}: VariantTabsProps) {
  if (tabs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="variant-tabs-empty">
        暂无变体生成结果
      </p>
    );
  }

  const activeValue = tabs.some((tab) => tab.generationId === activeGenerationId)
    ? activeGenerationId
    : tabs[0]!.generationId;

  return (
    <Tabs
      value={activeValue}
      onValueChange={onActiveChange}
      data-testid="variant-tabs"
    >
      <TabsList className="flex h-auto flex-wrap justify-start gap-1">
        {tabs.map((tab) => (
          <TabsTrigger key={tab.generationId} value={tab.generationId}>
            {tab.label ?? getVariantLabel(tab.variant)}
          </TabsTrigger>
        ))}
      </TabsList>

      {tabs.map((tab) => (
        <TabsContent key={tab.generationId} value={tab.generationId}>
          {loading && !tab.plan ? (
            <p className="text-sm text-muted-foreground">正在加载变体结果…</p>
          ) : tab.plan ? (
            renderPlan ? (
              renderPlan(tab.plan, tab)
            ) : (
              <GenerationResultView
                plan={tab.plan}
                videoHref={tab.renderVideoUrl}
              />
            )
          ) : (
            <FailedVariantResult
              tab={tab}
              retryBusy={retryBusy}
              onRetryTask={onRetryTask}
            />
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}
