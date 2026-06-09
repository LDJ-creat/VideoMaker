"use client";

import { useState } from "react";

import type { TaskEvent } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TaskArtifactPreview } from "@/features/tasks/TaskArtifactPreview";
import { GenerationMigrationProgressPanel } from "@/features/structure-migration/GenerationMigrationProgressPanel";
import type { MigrationProgressContext } from "@/features/structure-migration/useGenerationMigrationArtifacts";
import { getTaskStageLabel } from "@/features/tasks/stageLabels";
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";
import {
  assetUnderstandingRouteLabel,
  inferAssetUnderstandingRouteFromEvent,
} from "@/lib/assetUnderstandingRouteLabels";
import { formatTaskError } from "@/lib/formatTaskError";
import { formatTaskMessage } from "@/lib/taskMessageLabels";
import {
  getTaskStatusBadgeVariant,
  getTaskStatusLabel,
} from "@/lib/taskStatusLabels";
import {
  shouldSmoothModelCallProgress,
  useSmoothedModelCallProgress,
} from "@/lib/useSmoothedModelCallProgress";
import { cn } from "@/lib/utils";

type TaskProgressPanelProps = {
  projectId?: string;
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
  title?: string;
  subtitle?: string;
  compact?: boolean;
  onRetry?: () => void;
  retryBusy?: boolean;
  retryLabel?: string;
  onGoToScriptReview?: () => void;
  migrationContext?: MigrationProgressContext;
};

function shortTaskId(taskId: string): string {
  return taskId.length > 8 ? `${taskId.slice(0, 8)}…` : taskId;
}

export function TaskProgressPanel({
  projectId,
  event,
  mode,
  sseFailureCount,
  error,
  title = "任务进度",
  subtitle,
  compact = false,
  onRetry,
  retryBusy = false,
  retryLabel = "重试任务",
  onGoToScriptReview,
  migrationContext,
}: TaskProgressPanelProps) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const displayProgress = useSmoothedModelCallProgress(event);
  const formattedError = formatTaskError(event?.error);
  const assetRoute = inferAssetUnderstandingRouteFromEvent(event);

  if (!event) {
    return (
      <Card>
        <CardHeader className={compact ? "pb-3" : undefined}>
          <CardTitle className={compact ? "text-base" : undefined}>{title}</CardTitle>
          <CardDescription>
            暂无进行中的任务。若样例已分析完成，请前往「样例分析」查看结果；开始新任务后进度会显示在这里。
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const stageLabel = getTaskStageLabel(event.stage);
  const statusLabel = getTaskStatusLabel(event.status);
  const message = formatTaskMessage(event.message);
  const showPollingNotice = sseFailureCount > 0 && mode === "polling";
  const isModelCallSmoothing = shouldSmoothModelCallProgress(event);
  const progressLabel = Number.isInteger(displayProgress)
    ? `${displayProgress}%`
    : `${displayProgress.toFixed(1)}%`;

  return (
    <Card
      className={cn(
        event.status === "awaiting_review"
          ? "border-amber-500/40 border-ai/20"
          : "border-ai/20",
        compact && "shadow-none",
      )}
    >
      <CardHeader
        className={cn(
          "flex flex-row items-start justify-between gap-4",
          compact && "space-y-0 p-4 pb-2",
        )}
      >
        <div className="min-w-0 space-y-1">
          <CardTitle
            className={cn("flex flex-wrap items-center gap-2", compact && "text-base")}
          >
            <span className="truncate">{subtitle ?? title}</span>
            <Badge
              variant={getTaskStatusBadgeVariant(event.status)}
              data-testid="task-status-badge"
            >
              {statusLabel}
            </Badge>
          </CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {!subtitle ? null : (
              <span className="text-xs">{title}</span>
            )}
            <span>{stageLabel}</span>
            {assetRoute ? (
              <Badge variant="secondary" className="text-xs font-normal">
                {assetUnderstandingRouteLabel(assetRoute)}
              </Badge>
            ) : null}
            {showPollingNotice ? (
              <span className="text-xs text-amber-600 dark:text-amber-400">
                实时连接不稳定，已切换为定时刷新
              </span>
            ) : null}
          </CardDescription>
        </div>
        {!compact ? (
          <div className="shrink-0 text-right text-xs text-muted-foreground">
            <p>{progressLabel}</p>
            {subtitle ? (
              <p className="font-mono">{shortTaskId(event.taskId)}</p>
            ) : null}
          </div>
        ) : (
          <span className="shrink-0 text-sm font-medium tabular-nums">
            {progressLabel}
          </span>
        )}
      </CardHeader>
      <CardContent className={cn("space-y-4", compact && "space-y-3 p-4 pt-0")}>
        <div className="space-y-2" aria-live="polite" aria-atomic="true">
          <p className={cn("text-sm", compact ? "text-muted-foreground" : "text-foreground")}>
            {message}
          </p>
          {(event.stage === "extracting_structure_direct" ||
            event.stage === "running_agent") &&
          event.status === "running" &&
          event.progress >= 55 &&
          event.progress < 88 ? (
            <p className="text-xs text-muted-foreground">
              {isModelCallSmoothing
                ? "模型分析中（约 1–3 分钟），进度条会平滑推进至校验阶段。"
                : "模型分析通常需要 1–3 分钟，进度会在校验与保存阶段继续推进。"}
            </p>
          ) : null}
          <Progress value={displayProgress} />
        </div>

        {migrationContext ? (
          <GenerationMigrationProgressPanel
            context={migrationContext}
            event={event}
            defaultExpanded
          />
        ) : null}

        {!compact && projectId ? (
          <TaskArtifactPreview
            projectId={projectId}
            artifactRefs={event.artifactRefs}
            stage={event.stage}
          />
        ) : null}

        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        {formattedError ? (
          <div
            className="space-y-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm"
            role="alert"
          >
            <p className="font-medium text-destructive">{formattedError.title}</p>
            {formattedError.hint ? (
              <p className="text-muted-foreground">{formattedError.hint}</p>
            ) : null}
            {formattedError.technical ? (
              <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-muted/50 p-2 font-mono text-xs text-muted-foreground">
                {formattedError.technical}
              </pre>
            ) : null}
          </div>
        ) : null}

        {event.status === "awaiting_review" && onGoToScriptReview ? (
          <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              生成已暂停，等待您审核脚本后继续。
            </p>
            <Button type="button" variant="outline" onClick={onGoToScriptReview}>
              前往脚本审核
            </Button>
          </div>
        ) : null}

        {event.status === "failed" && onRetry ? (
          <div className="space-y-2">
            <Button
              type="button"
              variant="outline"
              disabled={retryBusy}
              onClick={() => void onRetry()}
            >
              {retryBusy ? "正在重新提交…" : retryLabel}
            </Button>
            {!compact ? (
              <p className="text-xs text-muted-foreground">
                重试会从上次 checkpoint 继续执行，复用同一任务 ID 与已完成阶段的中间产物。
              </p>
            ) : null}
          </div>
        ) : null}

        {!compact ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowTechnicalDetails((open) => !open)}
          >
            {showTechnicalDetails ? "隐藏技术详情" : "查看技术详情"}
          </Button>
        ) : null}

        {showTechnicalDetails && !compact ? (
          <div className="rounded-md border border-border bg-muted/30 p-3 font-mono text-xs text-muted-foreground">
            <p>taskId={event.taskId}</p>
            <p>stage={event.stage}</p>
            <p>status={event.status}</p>
            <p>progress={event.progress}</p>
            <p>updatedAt={event.updatedAt}</p>
            <p>transport={mode}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
