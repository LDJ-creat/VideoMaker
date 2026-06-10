"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { GenerationRunSummary } from "@/lib/apiClient";
import { getGenerationRun, listGenerationRuns } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import {
  formatGenerationRunMetaLine,
  formatGenerationRunTitle,
  formatShortRunId,
} from "@/lib/formatGenerationRunDisplay";
import {
  generationRunStatusLabel,
  generationStatusBadgeVariant,
  generationStatusLabel,
} from "@/lib/generationRunLabels";
import type { GenerationRunGenerationSummary } from "@/lib/reloadGenerationRunResults";
import { getVariantLabel } from "@/lib/variantRegistry";
import { canRetryGenerationTask } from "@/lib/generationTaskHydration";

type GenerationRunHistoryPanelProps = {
  projectId: string;
  activeRunId?: string | null;
  onSelectRun?: (runId: string) => void;
  onRetryTask?: (taskId: string) => void;
  retryBusy?: boolean;
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

export function GenerationRunHistoryPanel({
  projectId,
  activeRunId,
  onSelectRun,
  onRetryTask,
  retryBusy = false,
}: GenerationRunHistoryPanelProps) {
  const [runs, setRuns] = useState<GenerationRunSummary[]>([]);
  const [runGenerations, setRunGenerations] = useState<
    Record<string, GenerationRunGenerationSummary[]>
  >({});
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await listGenerationRuns(projectId);
      setRuns(data.runs);

      const detailEntries = await Promise.all(
        data.runs.map(async (run) => {
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>生成历史</CardTitle>
        <CardDescription>
          按时间查看每次生成的变体结果，成功与失败互不影响。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">正在加载生成记录…</p>
        ) : null}
        {runs.length === 0 && !loading && (
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

          return (
            <div
              key={run.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-border p-3"
            >
              <div className="min-w-0 flex-1 space-y-2">
                <div className="space-y-1">
                  <p
                    className="text-sm font-medium leading-snug"
                    data-testid={`run-title-${run.id}`}
                  >
                    {formatGenerationRunTitle(run.createdAt, index, runs.length)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatGenerationRunMetaLine(
                      run.createdAt,
                      run.status,
                      variantSummaries,
                    )}
                  </p>
                  <p
                    className="font-mono text-[11px] text-muted-foreground/80"
                    title={run.id}
                  >
                    批次 ID {formatShortRunId(run.id)}
                  </p>
                </div>

                {generations.length > 0 ? (
                  <div
                    className="flex flex-wrap gap-2"
                    data-testid={`run-variant-status-${run.id}`}
                  >
                    {generations.map((entry) => {
                      const variantId =
                        entry.variant ?? entry.plan?.variant ?? "default";
                      const canRetry =
                        canRetryGenerationTask({
                          status: entry.status,
                          taskId: entry.taskId,
                          renderVideoUrl: entry.plan?.renderVideoUrl,
                          plan: entry.plan,
                        }) && Boolean(onRetryTask);
                      return (
                        <div
                          key={entry.generationId}
                          className="flex flex-wrap items-center gap-1.5"
                        >
                          <Badge
                            variant={generationStatusBadgeVariant(entry.status)}
                          >
                            {getVariantLabel(variantId)} ·{" "}
                            {generationStatusLabel(entry.status)}
                          </Badge>
                          {canRetry ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-7 px-2"
                              disabled={retryBusy}
                              onClick={() => {
                                if (activeRunId !== run.id) {
                                  onSelectRun?.(run.id);
                                }
                                onRetryTask!(entry.taskId!);
                              }}
                            >
                              {retryBusy ? "正在重新提交…" : "重新渲染"}
                            </Button>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
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
              <Button
                type="button"
                size="sm"
                variant={activeRunId === run.id ? "default" : "outline"}
                className="shrink-0"
                onClick={() => onSelectRun?.(run.id)}
              >
                {activeRunId === run.id ? "当前查看" : "查看结果"}
              </Button>
            </div>
          );
        })}
        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
