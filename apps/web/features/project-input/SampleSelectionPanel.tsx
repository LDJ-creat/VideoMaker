"use client";

import { HelpCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  embedded?: boolean;
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
  embedded = false,
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

  const analyzedCount = useMemo(
    () => samples.filter((sample) => sample.hasStructure).length,
    [samples],
  );

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

  if (analyzedCount === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        完成样例分析后，可在此选择主样例与参考样例（最多 4 个参考）。
      </p>
    );
  }

  const autoRulesTitle =
    "优先使用最新 upload-batch；若无批次 ID，则按上传时间间隔（默认 30 分钟）划分虚拟批次。主样例优先选当前批次内已分析的样例。";

  const content = (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{modeLabel}</Badge>
        {selection?.activeUploadBatchId && (
          <Badge variant="secondary">
            批次 {selection.activeUploadBatchId.slice(0, 8)}
          </Badge>
        )}
        <span
          className="inline-flex items-center gap-1 text-xs text-muted-foreground"
          title={autoRulesTitle}
        >
          <HelpCircle className="h-3.5 w-3.5" />
          自动规则
        </span>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">主样例</p>
        {primarySample ? (
          <SampleVideoCard sample={primarySample} variant="filmstrip" selected />
        ) : (
          <p className="text-sm text-muted-foreground">尚未选择主样例</p>
        )}
      </div>

      {referenceSamples.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">参考样例</p>
          <div className="space-y-2">
            {referenceSamples.map((sample) => (
              <SampleVideoCard key={sample.id} sample={sample} variant="filmstrip" />
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
        <ul className="space-y-2">
          {displaySamples.map((sample) => {
            const isPrimary = sample.id === selection?.primarySampleId;
            const isReference = selection?.referenceSampleIds?.includes(sample.id);
            const inBatch = batchCandidateIds.has(sample.id);
            return (
              <li key={sample.id}>
                <SampleVideoCard
                  sample={sample}
                  variant="filmstrip"
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

      {status && (
        <p className="text-sm text-muted-foreground" role="status">
          {status}
        </p>
      )}
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <div className="space-y-4 rounded-2xl border bg-card p-6 shadow-sm">
      <div>
        <h3 className="font-serif text-lg font-semibold">样例选择</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          主样例决定生成骨架；参考样例在合成阶段迁移结构与风格（最多 4 个）。
        </p>
      </div>
      {content}
    </div>
  );
}
