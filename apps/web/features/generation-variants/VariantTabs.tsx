"use client";

import type { GenerationPlan } from "@videomaker/contracts";

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { GenerationResultView } from "@/features/generation-result/GenerationResultView";
import { getVariantLabel } from "@/lib/variantRegistry";

export type VariantGenerationTab = {
  generationId: string;
  variant: string;
  label?: string;
  plan?: GenerationPlan | null;
};

type VariantTabsProps = {
  tabs: VariantGenerationTab[];
  activeGenerationId: string;
  onActiveChange: (generationId: string) => void;
  loading?: boolean;
};

export function VariantTabs({
  tabs,
  activeGenerationId,
  onActiveChange,
  loading,
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
            <GenerationResultView plan={tab.plan} showTimeline />
          ) : (
            <p className="text-sm text-muted-foreground">
              变体 {tab.label ?? tab.variant} 暂无计划数据
            </p>
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}
