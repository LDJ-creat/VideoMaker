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
import type { TaskProgressMode } from "@/features/tasks/useTaskProgress";
import { formatTaskError } from "@/lib/formatTaskError";

type TaskProgressPanelProps = {
  event: TaskEvent | null;
  mode: TaskProgressMode;
  sseFailureCount: number;
  error: string | null;
  onRetry?: () => void;
  retryBusy?: boolean;
  retryLabel?: string;
};

const MODE_LABEL: Record<TaskProgressMode, string> = {
  sse: "SSE 实时",
  polling: "轮询降级",
  idle: "空闲",
  completed: "已完成",
};

export function TaskProgressPanel({
  event,
  mode,
  sseFailureCount,
  error,
  onRetry,
  retryBusy = false,
  retryLabel = "重试任务",
}: TaskProgressPanelProps) {
  const formattedError = formatTaskError(event?.error);

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

  return (
    <Card className="border-ai/20">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            任务进度
            <Badge variant="ai">{event.status}</Badge>
          </CardTitle>
          <CardDescription className="font-mono text-xs">
            {event.taskId} · {event.stage}
          </CardDescription>
        </div>
        <Badge variant="outline">{MODE_LABEL[mode]}</Badge>
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
          {event.artifactRefs?.map((ref) => (
            <p key={ref.id}>
              artifact {ref.type}: {ref.uri}
            </p>
          ))}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
