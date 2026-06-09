"use client";

import type { TaskEvent } from "@videomaker/contracts";
import { useState } from "react";

import { StructureMigrationPanel } from "@/features/structure-migration/StructureMigrationPanel";
import { buildSlotMigrationRows } from "@/features/structure-migration/buildSlotMigrationRows";
import { isGenerationMigrationStage } from "@/features/structure-migration/generationMigrationStages";
import {
  useGenerationMigrationArtifacts,
  type MigrationProgressContext,
} from "@/features/structure-migration/useGenerationMigrationArtifacts";
import { cn } from "@/lib/utils";

type GenerationMigrationProgressPanelProps = {
  context: MigrationProgressContext;
  event: TaskEvent | null;
  defaultExpanded?: boolean;
};

export function GenerationMigrationProgressPanel({
  context,
  event,
  defaultExpanded = true,
}: GenerationMigrationProgressPanelProps) {
  const { artifacts, progressGroup, loading } = useGenerationMigrationArtifacts({
    projectId: context.projectId,
    generationId: context.generationId,
    event,
  });

  if (!event || !isGenerationMigrationStage(event.stage)) {
    return null;
  }

  if (!context.structure) {
    return (
      <MigrationProgressShell defaultExpanded={defaultExpanded} loading={loading}>
        <p className="text-sm text-muted-foreground">
          等待样例结构加载…完成样例分析后将显示槽位映射与补全进度。
        </p>
      </MigrationProgressShell>
    );
  }

  const rows = buildSlotMigrationRows({
    structure: context.structure,
    gapReport: artifacts?.gapReport,
    slotMatches: artifacts?.slotMatches,
    completionActions: artifacts?.completionActions,
    mode: "progress",
    progressGroup,
    taskSucceeded: event.status === "succeeded",
  });

  const stageHint =
    progressGroup === "mapping"
      ? "正在把样例结构槽位与你的 Brief / 素材做语义匹配。"
      : progressGroup === "planning"
        ? "匹配结果已写入；正在为缺口槽位选择 Pexels / HyperFrames / AIGC 补全策略。"
        : progressGroup === "completing"
          ? "补全策略已确定，正在生成或渲染各槽位素材。"
          : "结构迁移进度将随任务阶段自动更新。";

  return (
    <MigrationProgressShell
      defaultExpanded={defaultExpanded}
      loading={loading}
      variantLabel={context.variantLabel}
    >
      <p className="text-sm text-muted-foreground">{stageHint}</p>
      <StructureMigrationPanel
        rows={rows}
        title="槽位映射与补全"
        defaultExpanded
        collapsible={false}
        compact
        data-testid="generation-migration-progress-panel"
      />
    </MigrationProgressShell>
  );
}

function MigrationProgressShell({
  children,
  defaultExpanded,
  loading,
  variantLabel,
}: {
  children: React.ReactNode;
  defaultExpanded: boolean;
  loading?: boolean;
  variantLabel?: string;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className="relative mt-1 border-l-2 border-primary/30 pl-4"
      data-testid="generation-migration-progress-shell"
    >
      <span
        className="absolute -left-[5px] top-0 h-2 w-2 rounded-full bg-primary"
        aria-hidden
      />
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium">结构迁移进度</p>
          {variantLabel ? (
            <span className="text-xs text-muted-foreground">{variantLabel}</span>
          ) : null}
          {loading ? (
            <span className="text-xs text-muted-foreground">同步中…</span>
          ) : null}
        </div>
        <button
          type="button"
          className={cn(
            "text-xs text-muted-foreground transition-colors hover:text-foreground",
          )}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收起详情" : "展开详情"}
        </button>
      </div>
      {expanded ? children : null}
    </div>
  );
}
