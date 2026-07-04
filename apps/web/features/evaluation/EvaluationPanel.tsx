"use client";

import type { EvaluationReport } from "@videomaker/contracts";
import { BarChart3, RefreshCw } from "lucide-react";
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
import {
  getGenerationEvaluation,
  rebuildGenerationEvaluation,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type EvaluationPanelProps = {
  generationId: string;
};

type LoadState = "idle" | "loading" | "loaded" | "error";

const USAGE_LABELS: Record<string, string> = {
  text_chat: "文本 Chat",
  vision_chat: "视觉 Chat",
  tts: "TTS",
  image_gen: "生图",
  video_gen: "生视频",
};

function verdictVariant(status: string | undefined): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "pass":
      return "default";
    case "warn":
      return "secondary";
    case "block":
      return "destructive";
    case "partial":
      return "outline";
    default:
      return "outline";
  }
}

function formatMs(ms: number | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const min = Math.floor(sec / 60);
  const rem = Math.round(sec % 60);
  return `${min}m ${rem}s`;
}

function UsageCard({ category, data }: { category: string; data: Record<string, unknown> }) {
  const billingUnit = String(data.billingUnit ?? "");
  return (
    <div className="rounded-md border p-3 text-sm">
      <div className="mb-1 font-medium">{USAGE_LABELS[category] ?? category}</div>
      <div className="text-muted-foreground space-y-0.5">
        {billingUnit === "tokens" ? (
          <>
            <div>总 Token：{Number(data.totalTokens ?? 0).toLocaleString()}</div>
            <div>调用：{Number(data.calls ?? 0)}</div>
          </>
        ) : null}
        {billingUnit === "chars" ? (
          <>
            <div>总字符：{Number(data.totalChars ?? 0).toLocaleString()}</div>
            <div>调用：{Number(data.calls ?? 0)}</div>
          </>
        ) : null}
        {billingUnit === "images" ? (
          <>
            <div>成功张数：{Number(data.successfulImages ?? 0)}</div>
            <div>失败：{Number(data.failedCalls ?? 0)}</div>
          </>
        ) : null}
        {billingUnit === "video_seconds" ? (
          <>
            <div>成功任务：{Number(data.successfulJobs ?? 0)}</div>
            <div>总秒数：{Number(data.totalDurationSec ?? 0).toFixed(1)} s</div>
          </>
        ) : null}
        <div>延迟：{formatMs(Number(data.latencyMs ?? 0))}</div>
      </div>
    </div>
  );
}

export function EvaluationPanel({ generationId }: EvaluationPanelProps) {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  const loadReport = useCallback(async () => {
    if (!generationId) {
      setReport(null);
      setLoadState("idle");
      return;
    }
    setLoadState("loading");
    setError(null);
    try {
      const result = await getGenerationEvaluation(generationId);
      setReport(result.data.report);
      setLoadState("loaded");
    } catch (err) {
      setReport(null);
      setLoadState("error");
      setError(getErrorMessage(err));
    }
  }, [generationId]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const handleRebuild = async () => {
    setRebuilding(true);
    setError(null);
    try {
      const result = await rebuildGenerationEvaluation(generationId);
      setReport(result.data.report);
      setLoadState("loaded");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRebuilding(false);
    }
  };

  if (!generationId) return null;

  const usage = report?.observability?.usageByCategory ?? {};
  const timing = report?.observability?.timing;
  const stages = timing?.stages ?? [];
  const core = report?.scores?.core;
  const migration = report?.scores?.migration as Record<string, unknown> | undefined;
  const knowledgeFit = report?.scores?.knowledgeFit as Record<string, unknown> | undefined;
  const modelLatency = timing?.modelLatency ?? {};
  const estimatedCost = report?.observability?.estimatedCostUsd;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4" />
            评测与用量
          </CardTitle>
          <CardDescription>
            质量分、分模型用量与阶段耗时（L0–L2，无 VLM）
          </CardDescription>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={rebuilding || loadState === "loading"}
          onClick={() => void handleRebuild()}
        >
          <RefreshCw className={`mr-1 h-3.5 w-3.5 ${rebuilding ? "animate-spin" : ""}`} />
          重算
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {loadState === "loading" ? (
          <p className="text-muted-foreground text-sm">加载评测报告…</p>
        ) : null}
        {error ? <p className="text-destructive text-sm">{error}</p> : null}
        {report ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={verdictVariant(report.verdict?.status)}>
                {report.verdict?.status ?? "unknown"}
              </Badge>
              {report.partial ? <Badge variant="outline">partial</Badge> : null}
              {report.observability?.incomplete ? (
                <Badge variant="outline">用量不完整</Badge>
              ) : null}
              <span className="text-muted-foreground text-xs">
                {report.profile?.inputMode}
              </span>
            </div>

            {core ? (
              <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div className="rounded border p-2">
                  <div className="text-muted-foreground text-xs">综合</div>
                  <div className="text-lg font-semibold">{core.weighted ?? "—"}</div>
                </div>
                <div className="rounded border p-2">
                  <div className="text-muted-foreground text-xs">技术 L0</div>
                  <div className="text-lg font-semibold">
                    {core.technical == null ? "待 L0" : core.technical}
                  </div>
                </div>
                <div className="rounded border p-2">
                  <div className="text-muted-foreground text-xs">计划 L1</div>
                  <div className="text-lg font-semibold">{core.plan ?? "—"}</div>
                </div>
                <div className="rounded border p-2">
                  <div className="text-muted-foreground text-xs">感知 L2</div>
                  <div className="text-lg font-semibold">{core.perceptual ?? "—"}</div>
                </div>
              </div>
            ) : null}

            {(report.profile?.enabledModules?.includes("migration") && migration) ||
            (report.profile?.enabledModules?.includes("knowledge_fit") && knowledgeFit) ? (
              <div className="grid grid-cols-2 gap-2 text-sm">
                {report.profile?.enabledModules?.includes("migration") && migration ? (
                  <div className="rounded border p-2">
                    <div className="text-muted-foreground text-xs">迁移分</div>
                    <div className="text-lg font-semibold">
                      {String(migration.weighted ?? "—")}
                    </div>
                  </div>
                ) : null}
                {report.profile?.enabledModules?.includes("knowledge_fit") && knowledgeFit ? (
                  <div className="rounded border p-2">
                    <div className="text-muted-foreground text-xs">知识契合</div>
                    <div className="text-lg font-semibold">
                      {String(knowledgeFit.weighted ?? "—")}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {Object.keys(modelLatency).length > 0 ? (
              <div className="text-sm">
                <div className="mb-1 font-medium">模型延迟（按类别）</div>
                <div className="text-muted-foreground flex flex-wrap gap-3">
                  {Object.entries(modelLatency).map(([key, value]) => (
                    <span key={key}>
                      {USAGE_LABELS[key] ?? key}: {formatMs(Number(value ?? 0))}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {estimatedCost ? (
              <div className="text-muted-foreground text-sm">
                估算成本：${Number(estimatedCost.total ?? 0).toFixed(4)}
                {estimatedCost.confidence ? ` (${estimatedCost.confidence})` : ""}
              </div>
            ) : null}

            {Object.keys(usage).length > 0 ? (
              <div>
                <div className="mb-2 text-sm font-medium">用量（按计费维度）</div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(usage).map(([key, value]) => (
                    <UsageCard key={key} category={key} data={value as Record<string, unknown>} />
                  ))}
                </div>
              </div>
            ) : null}

            {usage.video_gen && Array.isArray((usage.video_gen as { jobs?: unknown[] }).jobs) ? (
              <div className="overflow-x-auto">
                <div className="mb-1 text-sm font-medium">生视频明细</div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-muted-foreground border-b text-left">
                      <th className="py-1 pr-2">slot</th>
                      <th className="py-1 pr-2">请求(s)</th>
                      <th className="py-1 pr-2">实际(s)</th>
                      <th className="py-1">延迟</th>
                    </tr>
                  </thead>
                  <tbody>
                    {((usage.video_gen as { jobs: Array<Record<string, unknown>> }).jobs ?? []).map(
                      (job) => (
                        <tr key={String(job.jobId)} className="border-b">
                          <td className="py-1 pr-2">{String(job.slotId ?? "—")}</td>
                          <td className="py-1 pr-2">{String(job.requestedDurationSec ?? "—")}</td>
                          <td className="py-1 pr-2">{String(job.actualDurationSec ?? "—")}</td>
                          <td className="py-1">{formatMs(Number(job.latencyMs ?? 0))}</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}

            {timing?.wallClock ? (
              <div className="text-sm">
                <div className="mb-1 font-medium">墙钟耗时</div>
                <div className="text-muted-foreground grid grid-cols-2 gap-1 sm:grid-cols-4">
                  <span>总计：{formatMs(timing.wallClock.totalMs)}</span>
                  <span>活跃：{formatMs(timing.wallClock.activeMs)}</span>
                  <span>人工等待：{formatMs(timing.wallClock.humanWaitMs)}</span>
                  <span>排队：{formatMs(timing.wallClock.queuedMs)}</span>
                </div>
              </div>
            ) : null}

            {stages.length > 0 ? (
              <div>
                <div className="mb-2 text-sm font-medium">阶段耗时</div>
                <div className="space-y-1">
                  {stages.map((stage) => {
                    const maxMs = Math.max(
                      ...stages.map((item) => Number(item.durationMs ?? 0)),
                      1,
                    );
                    const width = Math.max(
                      4,
                      Math.round((Number(stage.durationMs ?? 0) / maxMs) * 100),
                    );
                    const isGate = stage.kind === "human_gate";
                    return (
                      <div key={`${stage.stage}-${stage.startedAt ?? ""}`} className="text-xs">
                        <div className="mb-0.5 flex justify-between gap-2">
                          <span className={isGate ? "text-amber-600" : undefined}>
                            {stage.stage}
                            {isGate ? " (gate)" : ""}
                          </span>
                          <span className="text-muted-foreground">
                            {formatMs(Number(stage.durationMs ?? 0))}
                          </span>
                        </div>
                        <div className="bg-muted h-1.5 rounded-full">
                          <div
                            className={`h-1.5 rounded-full ${isGate ? "bg-amber-500" : "bg-primary"}`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
