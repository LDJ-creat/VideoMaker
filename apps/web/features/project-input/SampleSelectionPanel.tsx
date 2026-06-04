"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SampleVideoCard } from "@/features/project-input/SampleVideoCard";
import type {
  ActiveSampleSummary,
  ProjectSampleSelection,
  SampleRecommendation,
} from "@/lib/apiClient";
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

function sortSamplesForDisplay(samples: ActiveSampleSummary[]): ActiveSampleSummary[] {
  return [...samples].sort((a, b) => {
    if (a.hasStructure !== b.hasStructure) {
      return a.hasStructure ? -1 : 1;
    }
    const aBatch = a.batchCreatedAt ?? "";
    const bBatch = b.batchCreatedAt ?? "";
    if (aBatch !== bBatch) {
      return bBatch.localeCompare(aBatch);
    }
    return b.id.localeCompare(a.id);
  });
}

export function SampleSelectionPanel({
  projectId,
  onSelectionChanged,
}: SampleSelectionPanelProps) {
  const [selection, setSelection] = useState<ProjectSampleSelection | null>(null);
  const [recommendation, setRecommendation] = useState<SampleRecommendation | null>(
    null,
  );
  const [samples, setSamples] = useState<ActiveSampleSummary[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const sampleById = useMemo(
    () => new Map(samples.map((sample) => [sample.id, sample])),
    [samples],
  );

  const batchCandidateIds = useMemo(
    () => new Set(recommendation?.candidates.map((item) => item.sampleId) ?? []),
    [recommendation],
  );

  const displaySamples = useMemo(() => sortSamplesForDisplay(samples), [samples]);

  const primarySample = selection?.primarySampleId
    ? sampleById.get(selection.primarySampleId)
    : undefined;

  const referenceSamples = (selection?.referenceSampleIds ?? [])
    .map((id) => sampleById.get(id))
    .filter((sample): sample is ActiveSampleSummary => sample !== undefined);

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
      setSamples(samplesResult.data.samples);
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

  const modeLabel =
    selection?.mode === "user_override"
      ? "手动"
      : selection?.mode === "auto"
        ? "自动"
        : "未设置";

  return (
    <Card>
      <CardHeader>
        <CardTitle>样例选择</CardTitle>
        <CardDescription>
          主样例决定生成骨架；参考样例在合成阶段迁移结构与风格（最多 4 个）。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground leading-relaxed">
          <p>
            <span className="font-medium text-foreground">自动规则：</span>
            优先使用最新 upload-batch；若无批次 ID，则按上传时间间隔（默认 30
            分钟）划分虚拟批次。主样例优先选当前批次内
            <span className="text-foreground">已分析</span>
            的样例，其余已分析样例可作为参考。
          </p>
          {selection?.activeUploadBatchId && (
            <p className="mt-1">
              当前批次：{selection.activeUploadBatchId.slice(0, 8)}…（候选{" "}
              {batchCandidateIds.size} 个，项目共 {samples.length} 个样例）
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{modeLabel}</Badge>
          {selection?.activeUploadBatchId && (
            <Badge variant="secondary">
              批次 {selection.activeUploadBatchId.slice(0, 8)}
            </Badge>
          )}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">主样例</p>
          {primarySample ? (
            <SampleVideoCard sample={primarySample} selected compact />
          ) : (
            <p className="text-sm text-muted-foreground">尚未选择主样例</p>
          )}
        </div>

        {referenceSamples.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">参考样例</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {referenceSamples.map((sample) => (
                <SampleVideoCard key={sample.id} sample={sample} compact />
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={loading}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? "收起候选" : `展开全部样例（${displaySamples.length}）`}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={loading}
            onClick={() => void handleReset()}
          >
            恢复自动推荐
          </Button>
        </div>

        {expanded && (
          <ul className="grid gap-3 sm:grid-cols-2">
            {displaySamples.map((sample) => {
              const isPrimary = sample.id === selection?.primarySampleId;
              const isReference = selection?.referenceSampleIds?.includes(sample.id);
              const inBatch = batchCandidateIds.has(sample.id);
              return (
                <li key={sample.id}>
                  <SampleVideoCard
                    sample={sample}
                    selected={isPrimary}
                    footer={
                      <div className="space-y-2 pt-1">
                        <div className="flex flex-wrap gap-1">
                          {inBatch && <Badge variant="secondary">当前批次</Badge>}
                          {isPrimary && <Badge>主样例</Badge>}
                          {isReference && <Badge variant="outline">参考</Badge>}
                          {!sample.hasStructure && (
                            <Badge variant="outline">需先分析</Badge>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant={isPrimary ? "default" : "outline"}
                            disabled={loading}
                            onClick={() => void handleSelectPrimary(sample.id)}
                          >
                            设为主样例
                          </Button>
                          {!isPrimary && sample.hasStructure && (
                            <Button
                              type="button"
                              size="sm"
                              variant={isReference ? "secondary" : "outline"}
                              disabled={loading}
                              onClick={() => void toggleReference(sample.id)}
                            >
                              {isReference ? "取消参考" : "加入参考"}
                            </Button>
                          )}
                        </div>
                      </div>
                    }
                  />
                </li>
              );
            })}
          </ul>
        )}

        {expanded && displaySamples.length === 0 && (
          <p className="text-sm text-muted-foreground">暂无样例，请先上传视频。</p>
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
