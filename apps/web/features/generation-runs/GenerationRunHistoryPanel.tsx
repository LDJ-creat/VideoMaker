"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  GitBranch,
  Layers,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  GenerationRunSummary,
  ReviseGenerationSummary,
} from "@/lib/apiClient";
import {
  deleteGeneration,
  getGenerationRun,
  listGenerationRuns,
  listReviseGenerations,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import {
  formatGenerationRunMetaLine,
  formatGenerationRunTitle,
  formatShortRunId,
} from "@/lib/formatGenerationRunDisplay";
import {
  collectKnownGenerationIds,
  countDirectReviseForks,
  indexRevisionsBySource,
  listOrphanRevisions,
} from "@/lib/groupGenerationHistory";
import {
  generationRunStatusLabel,
  generationStatusBadgeVariant,
  generationStatusLabel,
} from "@/lib/generationRunLabels";
import type { GenerationRunGenerationSummary } from "@/lib/reloadGenerationRunResults";
import { getVariantLabel } from "@/lib/variantRegistry";
import { canRetryGenerationTask } from "@/lib/generationTaskHydration";
import { cn } from "@/lib/utils";

type GenerationRunHistoryPanelProps = {
  projectId: string;
  activeRunId?: string | null;
  activeReviseGenerationId?: string | null;
  activeVariantGenerationId?: string | null;
  onSelectRun?: (runId: string) => void;
  onSelectGeneration?: (generationId: string) => void;
  onSelectReviseFork?: (generationId: string) => void;
  onRetryTask?: (taskId: string) => void;
  onDeleted?: (deletedGenerationIds: string[]) => void;
  retryBusy?: boolean;
  deleteBusy?: boolean;
};

function orderGenerationsForRun(
  run: GenerationRunSummary,
  generations: GenerationRunGenerationSummary[],
): GenerationRunGenerationSummary[] {
  if (run.variantIds.length === 0) return generations;
  const byVariant = new Map(
    generations.map((entry) => [entry.variant ?? "", entry]),
  );
  const ordered: GenerationRunGenerationSummary[] = [];
  for (const variantId of run.variantIds) {
    const match = byVariant.get(variantId);
    if (match) ordered.push(match);
  }
  for (const entry of generations) {
    if (!ordered.includes(entry)) {
      ordered.push(entry);
    }
  }
  return ordered;
}

function formatReviseInstruction(instruction: string | null | undefined): string {
  const text = (instruction ?? "").trim();
  if (!text) return "改片";
  return text.length > 56 ? `${text.slice(0, 56)}…` : text;
}

function formatReviseUpdatedAt(value: string | null | undefined): string {
  if (!value) return "时间未知";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildDeleteConfirmMessage(
  label: string,
  forkCount: number,
): string {
  if (forkCount > 0) {
    return `确定删除「${label}」及其 ${forkCount} 个改片结果和相关产物？此操作不可撤销。`;
  }
  return `确定删除「${label}」及其相关产物？此操作不可撤销。`;
}

type HistoryIconButtonProps = {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  tone?: "default" | "destructive";
};

function HistoryIconButton({
  icon: Icon,
  label,
  onClick,
  disabled = false,
  busy = false,
  tone = "default",
}: HistoryIconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled || busy}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-md",
        "border border-transparent text-muted-foreground transition-colors",
        "hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        tone === "destructive" &&
          "hover:border-destructive/25 hover:bg-destructive/10 hover:text-destructive",
        (disabled || busy) && "pointer-events-none opacity-45",
      )}
    >
      {busy ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <Icon className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}

type HistoryRowActionsProps = {
  viewLabel: string;
  isActive: boolean;
  onView: () => void;
  onDelete: () => void;
  deleteLabel: string;
  deleteBusy?: boolean;
  canRetry?: boolean;
  onRetry?: () => void;
  retryBusy?: boolean;
};

function HistoryRowActions({
  viewLabel,
  isActive,
  onView,
  onDelete,
  deleteLabel,
  deleteBusy = false,
  canRetry = false,
  onRetry,
  retryBusy = false,
}: HistoryRowActionsProps) {
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      {canRetry && onRetry ? (
        <HistoryIconButton
          icon={RefreshCw}
          label="重新渲染"
          onClick={onRetry}
          busy={retryBusy}
          disabled={retryBusy}
        />
      ) : null}
      <HistoryIconButton
        icon={Trash2}
        label={deleteLabel}
        onClick={onDelete}
        busy={deleteBusy}
        disabled={deleteBusy}
        tone="destructive"
      />
      <Button
        type="button"
        size="sm"
        variant={isActive ? "default" : "outline"}
        className="ml-1 h-8 shrink-0 px-3"
        onClick={onView}
      >
        {viewLabel}
      </Button>
    </div>
  );
}

type GenerationRowProps = {
  variantId: string;
  generationId: string;
  status?: string;
  taskId?: string | null;
  plan?: GenerationRunGenerationSummary["plan"];
  isActive: boolean;
  viewLabel: string;
  forkCount?: number;
  onView: () => void;
  onDelete: () => void;
  onRetryTask?: (taskId: string) => void;
  retryBusy?: boolean;
  deleteBusy?: boolean;
};

function GenerationResultRow({
  variantId,
  generationId,
  status,
  taskId,
  plan,
  isActive,
  viewLabel,
  forkCount = 0,
  onView,
  onDelete,
  onRetryTask,
  retryBusy = false,
  deleteBusy = false,
}: GenerationRowProps) {
  const canRetry =
    canRetryGenerationTask({
      status,
      taskId,
      renderVideoUrl: plan?.renderVideoUrl,
      plan,
    }) && Boolean(onRetryTask);

  return (
    <div data-testid={`generation-row-${generationId}`}>
      <div
        className={cn(
          "rounded-lg border p-3 transition-colors",
          isActive
            ? "border-primary/45 bg-primary/[0.06] shadow-sm"
            : "border-border/60 bg-muted/10 hover:bg-muted/20",
        )}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted/50 text-muted-foreground">
            <Layers className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={generationStatusBadgeVariant(status)}>
                {getVariantLabel(variantId)} · {generationStatusLabel(status)}
              </Badge>
              {forkCount > 0 ? (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <GitBranch className="h-3 w-3" aria-hidden="true" />
                  {forkCount} 个改片
                </span>
              ) : null}
            </div>
            <p
              className="font-mono text-[11px] text-muted-foreground/80"
              title={generationId}
            >
              结果 {formatShortRunId(generationId)}
            </p>
          </div>
          <HistoryRowActions
            viewLabel={viewLabel}
            isActive={isActive}
            onView={onView}
            onDelete={onDelete}
            deleteLabel={`删除${getVariantLabel(variantId)}生成结果`}
            deleteBusy={deleteBusy}
            canRetry={canRetry}
            onRetry={canRetry ? () => onRetryTask!(taskId!) : undefined}
            retryBusy={retryBusy}
          />
        </div>
      </div>
    </div>
  );
}

type ReviseForkRowProps = {
  entry: ReviseGenerationSummary;
  sourceGenerationId: string;
  isActive: boolean;
  onView: () => void;
  onDelete: () => void;
  onRetryTask?: (taskId: string) => void;
  retryBusy?: boolean;
  deleteBusy?: boolean;
};

function ReviseForkTimelineGroup({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative ml-4 mt-2"
      data-testid="revise-fork-timeline"
    >
      <div
        className="absolute bottom-2 left-0 top-2 w-px bg-primary/30"
        aria-hidden="true"
      />
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

function ReviseForkRow({
  entry,
  sourceGenerationId,
  isActive,
  onView,
  onDelete,
  onRetryTask,
  retryBusy = false,
  deleteBusy = false,
}: ReviseForkRowProps) {
  const variantId = entry.variant ?? entry.plan?.variant ?? "default";
  const canRetry =
    canRetryGenerationTask({
      status: entry.status,
      taskId: entry.taskId,
      renderVideoUrl: entry.plan?.renderVideoUrl,
      plan: entry.plan,
    }) && Boolean(onRetryTask);

  return (
    <div
      className="relative pl-6"
      data-testid={`revise-fork-${entry.generationId}`}
    >
      <span
        className="absolute left-0 top-7 z-10 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-primary/50 bg-background shadow-sm ring-2 ring-background"
        aria-hidden="true"
      />
      <div
        className={cn(
          "rounded-lg border border-dashed p-3 transition-colors",
          isActive
            ? "border-primary/40 bg-primary/[0.04]"
            : "border-border/70 bg-background/30 hover:bg-muted/15",
        )}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary/80">
            <GitBranch className="h-4 w-4" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <p className="text-xs font-medium text-primary/90">改片</p>
              <span className="text-[11px] text-muted-foreground">
                基于 {formatShortRunId(sourceGenerationId)}
              </span>
            </div>
            <p className="line-clamp-2 text-sm leading-snug text-foreground/90">
              {formatReviseInstruction(entry.instruction)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={generationStatusBadgeVariant(entry.status)}>
                {getVariantLabel(variantId)} · {generationStatusLabel(entry.status)}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {formatReviseUpdatedAt(entry.updatedAt)} · 槽位{" "}
                {(entry.affectedSlotIds ?? []).join(", ") || "—"}
              </span>
            </div>
          </div>
          <HistoryRowActions
            viewLabel={isActive ? "当前查看" : "查看改片"}
            isActive={isActive}
            onView={onView}
            onDelete={onDelete}
            deleteLabel="删除改片结果"
            deleteBusy={deleteBusy}
            canRetry={canRetry}
            onRetry={canRetry ? () => onRetryTask!(entry.taskId!) : undefined}
            retryBusy={retryBusy}
          />
        </div>
      </div>
    </div>
  );
}

export function GenerationRunHistoryPanel({
  projectId,
  activeRunId,
  activeReviseGenerationId,
  activeVariantGenerationId,
  onSelectRun,
  onSelectGeneration,
  onSelectReviseFork,
  onRetryTask,
  onDeleted,
  retryBusy = false,
  deleteBusy = false,
}: GenerationRunHistoryPanelProps) {
  const [runs, setRuns] = useState<GenerationRunSummary[]>([]);
  const [revisions, setRevisions] = useState<ReviseGenerationSummary[]>([]);
  const [runGenerations, setRunGenerations] = useState<
    Record<string, GenerationRunGenerationSummary[]>
  >({});
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deletingGenerationId, setDeletingGenerationId] = useState<string | null>(
    null,
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const [{ data: runData }, { data: reviseData }] = await Promise.all([
        listGenerationRuns(projectId),
        listReviseGenerations(projectId),
      ]);
      setRuns(runData.runs);
      setRevisions(reviseData.revisions);

      const detailEntries = await Promise.all(
        runData.runs.map(async (run) => {
          try {
            const { data: detail } = await getGenerationRun(projectId, run.id);
            return [run.id, detail.generations] as const;
          } catch {
            return [run.id, []] as const;
          }
        }),
      );
      setRunGenerations(Object.fromEntries(detailEntries));
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const revisionsBySource = useMemo(
    () => indexRevisionsBySource(revisions),
    [revisions],
  );
  const knownGenerationIds = useMemo(
    () => collectKnownGenerationIds(runGenerations),
    [runGenerations],
  );
  const orphanRevisions = useMemo(
    () => listOrphanRevisions(revisions, knownGenerationIds),
    [revisions, knownGenerationIds],
  );

  const handleDelete = useCallback(
    async (generationId: string, label: string, forkCount: number) => {
      if (
        typeof window !== "undefined" &&
        !window.confirm(buildDeleteConfirmMessage(label, forkCount))
      ) {
        return;
      }
      setDeletingGenerationId(generationId);
      setStatus(null);
      try {
        const { data } = await deleteGeneration(projectId, generationId, {
          cascade: true,
        });
        await refresh();
        onDeleted?.(data.deletedGenerationIds);
      } catch (error) {
        setStatus(getErrorMessage(error));
      } finally {
        setDeletingGenerationId(null);
      }
    },
    [onDeleted, projectId, refresh],
  );

  const isDeleting = deleteBusy || deletingGenerationId !== null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>生成历史</CardTitle>
        <CardDescription>
          按批次查看变体结果；改片嵌套在对应源结果下方，便于追溯修改关系。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && runs.length === 0 && revisions.length === 0 ? (
          <p className="text-sm text-muted-foreground">正在加载生成记录…</p>
        ) : null}

        {runs.length === 0 && revisions.length === 0 && !loading && (
          <p className="text-sm text-muted-foreground">暂无生成记录。</p>
        )}

        {runs.map((run, index) => {
          const generations = orderGenerationsForRun(
            run,
            runGenerations[run.id] ?? [],
          );
          const variantSummaries = generations.map((entry) => ({
            variant: entry.variant ?? entry.plan?.variant,
            status: entry.status,
          }));
          const runIsActive = activeRunId === run.id;

          return (
            <div
              key={run.id}
              className={cn(
                "space-y-3 rounded-xl border p-4 transition-colors",
                runIsActive
                  ? "border-primary/30 bg-primary/[0.03]"
                  : "border-border bg-card/40",
              )}
              data-testid={`generation-run-${run.id}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/50 pb-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p
                      className="text-sm font-medium leading-snug"
                      data-testid={`run-title-${run.id}`}
                    >
                      {formatGenerationRunTitle(run.createdAt, index, runs.length)}
                    </p>
                    {runIsActive ? (
                      <Badge variant="secondary" className="h-5 px-2 text-[10px]">
                        当前批次
                      </Badge>
                    ) : null}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatGenerationRunMetaLine(
                      run.createdAt,
                      run.status,
                      variantSummaries,
                    )}
                  </p>
                  <p
                    className="font-mono text-[11px] text-muted-foreground/70"
                    title={run.id}
                  >
                    批次 ID {formatShortRunId(run.id)}
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant={runIsActive ? "default" : "outline"}
                  className="shrink-0"
                  onClick={() => onSelectRun?.(run.id)}
                >
                  {runIsActive ? "当前批次" : "查看批次"}
                </Button>
              </div>

              <div className="space-y-2.5">
                {generations.length > 0 ? (
                  generations.map((entry) => {
                    const variantId =
                      entry.variant ?? entry.plan?.variant ?? "default";
                    const nestedRevisions =
                      revisionsBySource.get(entry.generationId) ?? [];
                    const forkCount = countDirectReviseForks(
                      revisions,
                      entry.generationId,
                    );
                    const isActiveGeneration =
                      activeVariantGenerationId === entry.generationId &&
                      activeReviseGenerationId == null;

                    return (
                      <div key={entry.generationId} className="space-y-2">
                        <GenerationResultRow
                          variantId={variantId}
                          generationId={entry.generationId}
                          status={entry.status}
                          taskId={entry.taskId}
                          plan={entry.plan}
                          isActive={isActiveGeneration}
                          viewLabel={isActiveGeneration ? "当前查看" : "查看结果"}
                          forkCount={forkCount}
                          onView={() => {
                            onSelectRun?.(run.id);
                            onSelectGeneration?.(entry.generationId);
                          }}
                          onDelete={() => {
                            void handleDelete(
                              entry.generationId,
                              `${getVariantLabel(variantId)} 生成结果`,
                              forkCount,
                            );
                          }}
                          onRetryTask={onRetryTask}
                          retryBusy={retryBusy}
                          deleteBusy={
                            isDeleting && deletingGenerationId === entry.generationId
                          }
                        />
                        {nestedRevisions.length > 0 ? (
                          <ReviseForkTimelineGroup>
                            {nestedRevisions.map((revision) => (
                              <ReviseForkRow
                                key={revision.generationId}
                                entry={revision}
                                sourceGenerationId={entry.generationId}
                                isActive={
                                  activeReviseGenerationId === revision.generationId
                                }
                                onView={() =>
                                  onSelectReviseFork?.(revision.generationId)
                                }
                                onDelete={() => {
                                  void handleDelete(
                                    revision.generationId,
                                    "改片结果",
                                    0,
                                  );
                                }}
                                onRetryTask={onRetryTask}
                                retryBusy={retryBusy}
                                deleteBusy={
                                  isDeleting &&
                                  deletingGenerationId === revision.generationId
                                }
                              />
                            ))}
                          </ReviseForkTimelineGroup>
                        ) : null}
                      </div>
                    );
                  })
                ) : run.variantIds.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {run.variantIds.map((variantId) => (
                      <Badge key={variantId} variant="outline">
                        {getVariantLabel(variantId)} · 加载中
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <Badge variant="outline">
                    {generationRunStatusLabel(run.status)}
                  </Badge>
                )}
              </div>
            </div>
          );
        })}

        {orphanRevisions.length > 0 ? (
          <div className="space-y-2 rounded-xl border border-dashed border-border p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              未归属批次的改片
            </p>
            <ReviseForkTimelineGroup>
              {orphanRevisions.map((revision) => (
                <ReviseForkRow
                  key={revision.generationId}
                  entry={revision}
                  sourceGenerationId={String(revision.sourceGenerationId ?? "unknown")}
                  isActive={activeReviseGenerationId === revision.generationId}
                  onView={() => onSelectReviseFork?.(revision.generationId)}
                  onDelete={() => {
                    void handleDelete(revision.generationId, "改片结果", 0);
                  }}
                  onRetryTask={onRetryTask}
                  retryBusy={retryBusy}
                  deleteBusy={
                    isDeleting && deletingGenerationId === revision.generationId
                  }
                />
              ))}
            </ReviseForkTimelineGroup>
          </div>
        ) : null}

        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
