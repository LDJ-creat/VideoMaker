"use client";

import type { AgentRunLog } from "@videomaker/contracts";
import { Bot, X } from "lucide-react";
import { useCallback, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getGenerationAgentRuns } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type AgentRunsDrawerProps = {
  generationId: string;
};

export function AgentRunsDrawer({ generationId }: AgentRunsDrawerProps) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<AgentRunLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await getGenerationAgentRuns(generationId);
      setRuns(data.runs);
      setOpen(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [generationId]);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={loading}
        onClick={() => void loadRuns()}
        data-testid="agent-runs-trigger"
      >
        <Bot className="mr-2 h-4 w-4" />
        {loading ? "加载中…" : "查看 AI 调用链"}
      </Button>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {open && (
        <Card
          className="mt-4 border-ai/30"
          data-testid="agent-runs-drawer"
        >
          <CardHeader className="flex flex-row items-start justify-between gap-2 pb-3">
            <div>
              <CardTitle className="text-base">AI 调用链</CardTitle>
              <CardDescription className="font-mono text-xs">
                {generationId}
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="关闭"
              onClick={() => setOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="pt-0">
            <ScrollArea className="h-64">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground">
                    <th className="pb-2 pr-2 font-medium">Agent</th>
                    <th className="pb-2 pr-2 font-medium">模型</th>
                    <th className="pb-2 pr-2 font-medium">延迟</th>
                    <th className="pb-2 pr-2 font-medium">有效</th>
                    <th className="pb-2 font-medium">Prompt</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-b border-border/50">
                      <td className="py-2 pr-2 font-mono text-xs">
                        {run.agentName}
                      </td>
                      <td className="py-2 pr-2 text-xs">{run.model}</td>
                      <td className="py-2 pr-2 text-xs">{run.latencyMs}ms</td>
                      <td className="py-2 pr-2">
                        <Badge
                          variant={run.outputValid ? "default" : "destructive"}
                        >
                          {run.outputValid ? "是" : "否"}
                        </Badge>
                      </td>
                      <td className="py-2 font-mono text-xs text-muted-foreground">
                        {run.promptVersion}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {runs.length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  暂无调用记录
                </p>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </>
  );
}
