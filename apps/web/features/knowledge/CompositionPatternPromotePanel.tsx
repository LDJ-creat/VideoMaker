"use client";

import { useCallback, useEffect, useState } from "react";

import { CheckCircle2 } from "lucide-react";

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
  getCompositionPatterns,
  promoteCompositionPattern,
  type CompositionPatternCandidate,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type CompositionPatternPromotePanelProps = {
  projectId: string;
  generationId: string;
  videoReady: boolean;
};

type LoadState = "idle" | "loading" | "loaded" | "error";

export function CompositionPatternPromotePanel({
  projectId,
  generationId,
  videoReady,
}: CompositionPatternPromotePanelProps) {
  const [patterns, setPatterns] = useState<CompositionPatternCandidate[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadingSlotId, setLoadingSlotId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<string | null>(null);

  const loadPatterns = useCallback(async () => {
    if (!generationId || !videoReady) {
      setPatterns([]);
      setLoadState("idle");
      return;
    }
    setLoadState("loading");
    try {
      const result = await getCompositionPatterns(generationId);
      setPatterns(result.data.patterns ?? []);
      setLoadState("loaded");
    } catch (error) {
      setPatterns([]);
      setLoadState("error");
      setErrorStatus(getErrorMessage(error));
    }
  }, [generationId, videoReady]);

  useEffect(() => {
    if (!videoReady) {
      setPatterns([]);
      setLoadState("idle");
      setErrorStatus(null);
      return;
    }
    void loadPatterns();
  }, [loadPatterns, videoReady]);

  if (!videoReady) {
    return null;
  }

  const handlePromote = async (slotId: string) => {
    setLoadingSlotId(slotId);
    setStatus(null);
    setErrorStatus(null);
    try {
      const result = await promoteCompositionPattern(projectId, {
        generationId,
        slotId,
        confirm: true,
      });
      setPatterns((current) =>
        current.map((item) =>
          item.slotId === slotId
            ? {
                ...item,
                publishedEntry: {
                  id: result.data.entry.id,
                  title: result.data.entry.title,
                  updatedAt: result.data.entry.updatedAt,
                },
              }
            : item,
        ),
      );
      setStatus("已加入全局知识库。");
    } catch (error) {
      setErrorStatus(getErrorMessage(error));
    } finally {
      setLoadingSlotId(null);
    }
  };

  const unpublishedCount = patterns.filter((item) => !item.publishedEntry?.id).length;

  return (
    <Card data-testid="composition-pattern-promote-panel">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">包装动效入库</CardTitle>
        <CardDescription>
          根据成片效果，将 HyperFrames 包装动效沉淀到全局知识库供后续复用。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {loadState === "loading" ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="composition-pattern-loading"
          >
            正在检查可入库的 HyperFrames 包装分镜…
          </p>
        ) : null}

        {loadState === "loaded" && patterns.length === 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="composition-pattern-empty"
          >
            本次生成没有可入库的 HyperFrames 包装动效（需分镜经 hyperframes_material
            完成且 lint 通过）。若刚完成改片，可刷新页面后再看。
          </p>
        ) : null}

        {loadState === "loaded" && patterns.length > 0 ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="composition-pattern-hint"
          >
            发现 {patterns.length} 个可入库分镜
            {unpublishedCount > 0 ? `，其中 ${unpublishedCount} 个尚未加入知识库` : "，均已入库"}。
          </p>
        ) : null}

        {patterns.map((pattern) => {
          const published = Boolean(pattern.publishedEntry?.id);
          const summary =
            pattern.storyboardSummary?.trim() ||
            `${pattern.slotRole || pattern.slotId} 包装分镜`;
          return (
            <div
              key={pattern.slotId}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card/80 px-3 py-2"
              data-testid={`composition-pattern-row-${pattern.slotId}`}
            >
              <div className="min-w-0">
                <p className="text-xs font-medium text-foreground">
                  {pattern.slotRole || pattern.slotId}
                </p>
                <p className="truncate text-xs text-muted-foreground">{summary}</p>
              </div>
              {published ? (
                <Badge variant="default" data-testid="composition-pattern-published-badge">
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  已入库
                </Badge>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  disabled={loadingSlotId !== null}
                  onClick={() => void handlePromote(pattern.slotId)}
                  data-testid={`composition-pattern-promote-${pattern.slotId}`}
                >
                  {loadingSlotId === pattern.slotId ? "正在沉淀动效模式…" : "加入知识库"}
                </Button>
              )}
            </div>
          );
        })}
        {loadState === "error" && errorStatus ? (
          <p className="text-xs text-destructive" data-testid="composition-pattern-error">
            无法加载可入库分镜：{errorStatus}
          </p>
        ) : null}
        {loadState !== "error" && errorStatus ? (
          <p className="text-xs text-destructive" data-testid="composition-pattern-error">
            {errorStatus}
          </p>
        ) : null}
        {status ? (
          <p className="text-xs text-muted-foreground" data-testid="composition-pattern-status">
            {status}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
