"use client";

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
import { ScrollArea } from "@/components/ui/scroll-area";
import { TaskArtifactPreview } from "@/features/tasks/TaskArtifactPreview";
import { getTaskStageLabel } from "@/features/tasks/stageLabels";
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";
import {
  assetUnderstandingRouteLabel,
  inferAssetUnderstandingRouteFromEvent,
} from "@/lib/assetUnderstandingRouteLabels";
import { formatTaskError } from "@/lib/formatTaskError";

type TaskProgressPanelProps = {
  projectId?: string;
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
  onRetry?: () => void;
  retryBusy?: boolean;
  retryLabel?: string;
  onGoToScriptReview?: () => void;
};

const MODE_LABEL: Record<TaskProgressMode, string> = {
  sse: "SSE 实时",
  polling: "轮询降级",
  idle: "空闲",
  completed: "已完成",
};

export function TaskProgressPanel({
  projectId,
  event,
  mode,
  sseFailureCount,
  error,
  onRetry,
  retryBusy = false,
  retryLabel = "重试任务",
  onGoToScriptReview,
}: TaskProgressPanelProps) {
  const formattedError = formatTaskError(event?.error);
  const assetRoute = inferAssetUnderstandingRouteFromEvent(event);

  if (!event) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>任务进度</CardTitle>
          <CardDescription>等待任务启动…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const stageLabel = getTaskStageLabel(event.stage);
  const modeLabel =
    mode === "completed" && event.status === "failed"
      ? "已结束"
      : MODE_LABEL[mode];

  return (
    <Card
      className={
        event.status === "awaiting_review"
          ? "border-amber-500/40 border-ai/20"
          : "border-ai/20"
      }
    >
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            任务进度
            <Badge variant="ai">{event.status}</Badge>
          </CardTitle>
          <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm text-muted-foreground">
            <span className="font-mono text-xs">{event.taskId}</span>
            <span aria-hidden>·</span>
            <span>{stageLabel}</span>
            {assetRoute ? (
              <>
                <span aria-hidden>·</span>
                <Badge variant="secondary" className="text-xs font-normal">
                  {assetUnderstandingRouteLabel(assetRoute)}
                </Badge>
              </>
            ) : null}
          </div>
        </div>
        <Badge variant="outline">{modeLabel}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2" aria-live="polite" aria-atomic="true">
          <div className="flex justify-between text-sm">
            <span>{event.message}</span>
            <span className="font-mono text-muted-foreground">
              {event.progress}%
            </span>
          </div>
          <Progress value={event.progress} />
        </div>

        {projectId && (
          <TaskArtifactPreview
            projectId={projectId}
            artifactRefs={event.artifactRefs}
            stage={event.stage}
          />
        )}

        {sseFailureCount > 0 && mode === "sse" && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            SSE 连接不稳定（{sseFailureCount}/{3}），即将切换轮询…
          </p>
        )}

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        {formattedError && (
          <div className="space-y-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm" role="alert">
            <p className="font-medium text-destructive">{formattedError.title}</p>
            {formattedError.hint && (
              <p className="text-muted-foreground">{formattedError.hint}</p>
            )}
            {formattedError.technical && (
              <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-muted/50 p-2 font-mono text-xs text-muted-foreground">
                {formattedError.technical}
              </pre>
            )}
          </div>
        )}

        {event.status === "awaiting_review" && onGoToScriptReview && (
          <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              生成已暂停，等待您审核脚本后继续。
            </p>
            <Button type="button" variant="outline" onClick={onGoToScriptReview}>
              前往脚本审核
            </Button>
          </div>
        )}

        {event.status === "failed" && onRetry && (
          <div className="space-y-2">
            <Button
              type="button"
              variant="outline"
              disabled={retryBusy}
              onClick={() => void onRetry()}
            >
              {retryBusy ? "正在重新提交…" : retryLabel}
            </Button>
            <p className="text-xs text-muted-foreground">
              重试会从上次 checkpoint 继续执行，复用同一任务 ID 与已完成阶段的中间产物。
            </p>
          </div>
        )}

        <ScrollArea className="h-28 rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
          <p>[{event.updatedAt}] stage={event.stage}</p>
          <p>status={event.status} progress={event.progress}</p>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
