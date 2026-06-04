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
import type { ProjectSampleSelection, SampleRecommendation } from "@/lib/apiClient";
import {
  getSampleSelection,
  listProjectSamples,
  recommendSamples,
  resetSampleSelection,
  updateSampleSelection,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type SampleSelectionPanelProps = {
  projectId: string;
  onSelectionChanged?: () => void;
};

export function SampleSelectionPanel({
  projectId,
  onSelectionChanged,
}: SampleSelectionPanelProps) {
  const [selection, setSelection] = useState<ProjectSampleSelection | null>(null);
  const [recommendation, setRecommendation] = useState<SampleRecommendation | null>(
    null,
  );
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    try {
      const [selectionResult, recommendResult, samplesResult] = await Promise.all([
        getSampleSelection(projectId),
        recommendSamples(projectId),
        listProjectSamples(projectId),
      ]);
      setSelection(selectionResult.data.selection);
      setRecommendation(recommendResult.data.recommendation);
      void samplesResult;
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSelectPrimary = async (sampleId: string) => {
    setLoading(true);
    try {
      await updateSampleSelection(projectId, {
        primarySampleId: sampleId,
        referenceSampleIds: selection?.referenceSampleIds ?? [],
        activeUploadBatchId: selection?.activeUploadBatchId,
      });
      await refresh();
      onSelectionChanged?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const toggleReference = async (sampleId: string) => {
    if (!selection?.primarySampleId || sampleId === selection.primarySampleId) {
      return;
    }
    const refs = new Set(selection.referenceSampleIds ?? []);
    if (refs.has(sampleId)) {
      refs.delete(sampleId);
    } else {
      refs.add(sampleId);
    }
    setLoading(true);
    try {
      await updateSampleSelection(projectId, {
        primarySampleId: selection.primarySampleId,
        referenceSampleIds: Array.from(refs),
        activeUploadBatchId: selection.activeUploadBatchId,
      });
      await refresh();
      onSelectionChanged?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      await resetSampleSelection(projectId);
      await refresh();
      onSelectionChanged?.();
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>样例选择</CardTitle>
        <CardDescription>
          主样例决定生成骨架；参考样例会在合成阶段迁移结构与风格。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{selection?.mode ?? "auto"}</Badge>
          {selection?.activeUploadBatchId && (
            <Badge variant="secondary">
              批次 {selection.activeUploadBatchId.slice(0, 8)}
            </Badge>
          )}
        </div>
        <p className="text-sm">
          主样例：{" "}
          <span className="font-mono text-xs">
            {selection?.primarySampleId ?? "未选择"}
          </span>
        </p>
        {(selection?.referenceSampleIds?.length ?? 0) > 0 && (
          <p className="text-xs text-muted-foreground">
            参考样例：{selection?.referenceSampleIds?.join(", ")}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={loading}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "收起候选" : "展开候选"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={loading}
            onClick={() => void handleReset()}
          >
            恢复默认
          </Button>
        </div>
        {expanded && recommendation && (
          <ul className="space-y-2">
            {recommendation.candidates.map((candidate) => {
              const isPrimary = candidate.sampleId === selection?.primarySampleId;
              const isReference = selection?.referenceSampleIds?.includes(
                candidate.sampleId,
              );
              return (
                <li
                  key={candidate.sampleId}
                  className="rounded-md border border-border p-2 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs">{candidate.sampleId}</span>
                    <Badge variant="outline">{candidate.status}</Badge>
                    {candidate.hasStructure && <Badge variant="ai">已分析</Badge>}
                    {isPrimary && <Badge>主样例</Badge>}
                    {isReference && <Badge variant="secondary">参考</Badge>}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant={isPrimary ? "default" : "outline"}
                      disabled={loading}
                      onClick={() => void handleSelectPrimary(candidate.sampleId)}
                    >
                      设为主样例
                    </Button>
                    {!isPrimary && candidate.hasStructure && (
                      <Button
                        type="button"
                        size="sm"
                        variant={isReference ? "secondary" : "outline"}
                        disabled={loading}
                        onClick={() => void toggleReference(candidate.sampleId)}
                      >
                        {isReference ? "取消参考" : "加入参考"}
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
