"use client";

import { Link2 } from "lucide-react";
import { useState } from "react";

import { SamplePreviewDialog } from "@/components/sample-preview-dialog";
import { FileDropzone } from "@/components/file-dropzone";
import { PaginatedGrid } from "@/components/paginated-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CookieUploadPanel } from "@/features/project-input/CookieUploadPanel";
import { SampleVideoCard } from "@/features/project-input/SampleVideoCard";
import type { ActiveSampleSummary } from "@/lib/apiClient";
import {
  analyzeSampleBatch,
  importSampleFromUrl,
  uploadSampleBatch,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { validateHttpUrl, validateUploadSize } from "@/lib/validation";

const SAMPLE_PAGE_SIZE = 6;

type SampleInputPanelProps = {
  projectId: string;
  samples?: ActiveSampleSummary[];
  activeSample?: ActiveSampleSummary | null;
  selectedSampleId?: string | null;
  embedded?: boolean;
  className?: string;
  onTaskStarted: (taskId: string, sampleId: string) => void;
  onBatchAnalysisStarted?: (
    tasks: Array<{ sampleId: string; taskId: string }>,
    maxConcurrent: number,
  ) => void;
  onSampleReady: (sampleId: string) => void;
  onSampleChanged?: () => void;
  onSelectSample?: (sampleId: string) => void;
};

function SampleListSection({
  previewSamples,
  effectiveSelectedId,
  embedded,
  onSelectSample,
  onPreview,
}: {
  previewSamples: ActiveSampleSummary[];
  effectiveSelectedId: string | null;
  embedded: boolean;
  onSelectSample?: (sampleId: string) => void;
  onPreview: (sample: ActiveSampleSummary) => void;
}) {
  const renderCard = (sample: ActiveSampleSummary) => (
    <SampleVideoCard
      sample={sample}
      variant="filmstrip"
      density={embedded ? "compact" : "default"}
      selected={sample.id === effectiveSelectedId}
      onSelect={onSelectSample}
      onPreview={onPreview}
    />
  );

  return (
    <div className="border-t border-border pt-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium">
          已上传样例
          {previewSamples.length > 0 ? (
            <span className="ml-1.5 font-normal text-muted-foreground">
              ({previewSamples.length})
            </span>
          ) : null}
        </p>
      </div>

      {previewSamples.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          上传第一个样例视频开始结构迁移
        </p>
      ) : embedded ? (
        <div
          className="grid grid-cols-2 gap-2 sm:grid-cols-1 xl:grid-cols-2"
          data-testid="sample-filmstrip-grid"
        >
          {previewSamples.map((sample) => (
            <div key={sample.id}>{renderCard(sample)}</div>
          ))}
        </div>
      ) : (
        <PaginatedGrid
          items={previewSamples}
          pageSize={SAMPLE_PAGE_SIZE}
          resetKey={previewSamples.map((sample) => sample.id).join(",")}
          getKey={(sample) => sample.id}
          gridClassName="grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
          renderItem={renderCard}
          emptyMessage="暂无样例视频，请上传或导入。"
        />
      )}
    </div>
  );
}

export function SampleInputPanel({
  projectId,
  samples = [],
  activeSample,
  selectedSampleId,
  embedded = false,
  className,
  onTaskStarted,
  onBatchAnalysisStarted,
  onSampleReady,
  onSampleChanged,
  onSelectSample,
}: SampleInputPanelProps) {
  const [url, setUrl] = useState(activeSample?.sourceUrl ?? "");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [lastBatchId, setLastBatchId] = useState<string | null>(null);
  const [previewSample, setPreviewSample] = useState<ActiveSampleSummary | null>(
    null,
  );

  const handleLocalUpload = async (files: File[]) => {
    if (files.length === 0) return;
    for (const file of files) {
      const sizeError = validateUploadSize(file);
      if (sizeError) {
        setStatus(sizeError);
        return;
      }
    }
    setBusy(true);
    setStatus(null);
    try {
      const { data: result } = await uploadSampleBatch(projectId, files);
      setLastBatchId(result.batchId);
      const first = result.samples[0];
      if (first) {
        onSampleReady(first.id);
      }
      setStatus(`已上传 ${result.samples.length} 个样例（批次 ${result.batchId.slice(0, 8)}）`);
      onSampleChanged?.();
    } catch (err) {
      setStatus(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleAnalyzeLatestBatch = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const { data } = await analyzeSampleBatch(
        projectId,
        lastBatchId ? { uploadBatchId: lastBatchId } : undefined,
      );
      if (data.tasks.length === 0) {
        setStatus("当前批次没有待分析样例。");
        return;
      }
      onBatchAnalysisStarted?.(data.tasks, data.maxConcurrent);
      setStatus(`已提交 ${data.tasks.length} 个分析任务`);
    } catch (err) {
      setStatus(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleUrlImport = async () => {
    const urlError = validateHttpUrl(url);
    if (urlError) {
      setStatus(urlError);
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const { data: result } = await importSampleFromUrl(projectId, {
        url: url.trim(),
      });
      setStatus(`URL 导入已提交：${result.id}`);
      onSampleChanged?.();
      if (result.taskId) {
        onTaskStarted(result.taskId, result.id);
      }
    } catch (err) {
      setStatus(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const previewSamples = (samples.length > 0 ? samples : activeSample ? [activeSample] : []).filter(
    (sample) => sample.sourceKind !== "knowledge",
  );

  const effectiveSelectedId =
    selectedSampleId ?? activeSample?.id ?? previewSamples[0]?.id ?? null;

  const content = (
    <div className={cn("flex flex-col gap-3", embedded && "min-h-0")}>
      <Tabs defaultValue="local" className="w-full">
        <div className="flex items-center gap-2">
          <TabsList className="h-9 shrink-0">
            <TabsTrigger value="local" className="px-3 text-xs sm:text-sm">
              本地上传
            </TabsTrigger>
            <TabsTrigger value="url" className="gap-1.5 px-3 text-xs sm:text-sm">
              <Link2 className="h-3.5 w-3.5" />
              URL 导入
            </TabsTrigger>
          </TabsList>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="ml-auto shrink-0"
            disabled={busy}
            onClick={() => void handleAnalyzeLatestBatch()}
          >
            分析最近批次
          </Button>
        </div>

        <TabsContent value="local" className="mt-2.5">
          <FileDropzone
            accept="video/*"
            multiple
            disabled={busy}
            size={embedded ? "compact" : "default"}
            title="上传样例视频"
            hint="点击选择或拖拽多个视频文件到此处"
            onFiles={(files) => void handleLocalUpload(files)}
          />
        </TabsContent>

        <TabsContent value="url" className="mt-2.5 space-y-3">
          <CookieUploadPanel />
          <div className="space-y-2">
            <Label htmlFor="sample-url">视频页面 URL</Label>
            <Input
              id="sample-url"
              placeholder="https://..."
              value={url}
              disabled={busy}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <Button
            type="button"
            size="sm"
            disabled={busy || !url.trim()}
            onClick={() => void handleUrlImport()}
          >
            开始 URL 导入
          </Button>
        </TabsContent>
      </Tabs>

      <SampleListSection
        previewSamples={previewSamples}
        effectiveSelectedId={effectiveSelectedId}
        embedded={embedded}
        onSelectSample={onSelectSample}
        onPreview={setPreviewSample}
      />

      {status ? (
        <p className="text-xs text-muted-foreground" role="status">
          {status}
        </p>
      ) : null}

      <SamplePreviewDialog
        sample={previewSample}
        open={previewSample != null}
        onClose={() => setPreviewSample(null)}
      />
    </div>
  );

  if (embedded) {
    return <div className={cn(className)}>{content}</div>;
  }

  return (
    <div className={cn("space-y-4 rounded-2xl border bg-card p-6 shadow-sm", className)}>
      <div>
        <h3 className="font-serif text-lg font-semibold">样例视频</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          支持一次上传多个视频；链接导入由服务端下载，前端不调用 yt-dlp。
        </p>
      </div>
      {content}
    </div>
  );
}
