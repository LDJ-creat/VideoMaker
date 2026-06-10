"use client";

import type { TaskEvent, TaskStatus } from "@videomaker/contracts";
import { useState } from "react";

import { StructureMigrationPanel } from "@/features/structure-migration/StructureMigrationPanel";
import { buildSlotMigrationRows } from "@/features/structure-migration/buildSlotMigrationRows";
import {
  isGenerationMigrationStage,
} from "@/features/structure-migration/generationMigrationStages";
import {
  useGenerationMigrationArtifacts,
  type MigrationProgressContext,
} from "@/features/structure-migration/useGenerationMigrationArtifacts";
import { normalizeMigrationSlotId } from "@/lib/migrationSlotId";
import { parseTaskMaterialProgress } from "@/lib/parseTaskMaterialProgress";
import { cn } from "@/lib/utils";

type GenerationMigrationProgressPanelProps = {
  context: MigrationProgressContext;
  event: TaskEvent | null;
  defaultExpanded?: boolean;
};

const ACTIVE_MIGRATION_TASK_STATUSES = new Set<TaskStatus>([
  "running",
  "retrying",
  "queued",
  "awaiting_review",
]);

function shouldShowMigrationShell(event: TaskEvent | null): boolean {
  if (!event) return false;
  if (ACTIVE_MIGRATION_TASK_STATUSES.has(event.status)) return true;
  return isGenerationMigrationStage(event.stage);
}

export function GenerationMigrationProgressPanel({
  context,
  event,
  defaultExpanded = true,
}: GenerationMigrationProgressPanelProps) {
  const { artifacts, progressGroup } = useGenerationMigrationArtifacts({
    projectId: context.projectId,
    generationId: context.generationId,
    event,
  });

  if (!event || !shouldShowMigrationShell(event)) {
    return null;
  }

  const materialProgress = parseTaskMaterialProgress(event.message);
  const isPreMigration =
    progressGroup === "pending" && !materialProgress.actionLabel;
  const activeSlotId =
    progressGroup === "completing"
      ? normalizeMigrationSlotId(materialProgress.slotId)
      : null;

  if (!context.structure) {
    return (
      <MigrationProgressShell
        defaultExpanded={defaultExpanded}
        variantLabel={context.variantLabel}
      >
        <p className="text-sm text-muted-foreground">
          等待样例结构加载…完成样例分析后将显示槽位映射与补全进度。
        </p>
      </MigrationProgressShell>
    );
  }

  if (isPreMigration) {
    return (
      <MigrationProgressShell
        defaultExpanded={defaultExpanded}
        variantLabel={context.variantLabel}
      >
        <div className="space-y-3" data-testid="migration-pre-stage-shell">
          <p className="text-sm text-muted-foreground">
            {event.stage === "analyzing_assets"
              ? "等待进入槽位匹配…资产理解完成后将显示结构迁移表。"
              : "等待进入结构迁移阶段…"}
          </p>
          <div className="space-y-2" aria-hidden>
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="h-10 animate-pulse rounded-md bg-muted/60"
              />
            ))}
          </div>
        </div>
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
    activeSlotId,
    completedActionIds: artifacts?.materialState?.completedActionIds,
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
      variantLabel={context.variantLabel}
    >
      <p className="text-sm text-muted-foreground">{stageHint}</p>
      {materialProgress.summary ? (
        <p
          className="text-xs font-medium text-foreground/90"
          data-testid="migration-active-action"
        >
          {materialProgress.summary}
        </p>
      ) : null}
      <StructureMigrationPanel
        rows={rows}
        title="槽位映射与补全"
        defaultExpanded
        collapsible={false}
        compact
        activeSlotId={activeSlotId}
        data-testid="generation-migration-progress-panel"
      />
    </MigrationProgressShell>
  );
}

function MigrationProgressShell({
  children,
  defaultExpanded,
  variantLabel,
}: {
  children: React.ReactNode;
  defaultExpanded: boolean;
  variantLabel?: string;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className="relative mt-1 min-h-[120px] border-l-2 border-primary/30 pl-4"
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
