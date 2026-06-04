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

type GenerationRunHistoryPanelProps = {
  projectId: string;
  activeRunId?: string | null;
  onSelectRun?: (runId: string) => void;
};

export function GenerationRunHistoryPanel({
  projectId,
  activeRunId,
  onSelectRun,
}: GenerationRunHistoryPanelProps) {
  const [runs, setRuns] = useState<GenerationRunSummary[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const { data } = await listGenerationRuns(projectId);
      setRuns(data.runs);
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSelect = async (runId: string) => {
    onSelectRun?.(runId);
    try {
      await getGenerationRun(projectId, runId);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>生成历史</CardTitle>
        <CardDescription>按批次/run 查看多次生成结果，不会互相覆盖。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {runs.length === 0 && !loading && (
          <p className="text-sm text-muted-foreground">暂无生成记录。</p>
        )}
        {runs.map((run) => (
          <div
            key={run.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2"
          >
            <div className="space-y-1">
              <p className="font-mono text-xs">{run.id}</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{run.status}</Badge>
                <span className="text-xs text-muted-foreground">{run.createdAt}</span>
              </div>
            </div>
            <Button
              type="button"
              size="sm"
              variant={activeRunId === run.id ? "default" : "outline"}
              onClick={() => void handleSelect(run.id)}
            >
              查看
            </Button>
          </div>
        ))}
        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
