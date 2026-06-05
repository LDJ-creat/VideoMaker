"use client";

import { Link2 } from "lucide-react";
import { useState } from "react";

import { FileDropzone } from "@/components/file-dropzone";
import { PaginatedGrid } from "@/components/paginated-grid";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

const SAMPLE_PAGE_SIZE = 4;

type SampleInputPanelProps = {
  projectId: string;
  samples?: ActiveSampleSummary[];
  activeSample?: ActiveSampleSummary | null;
  selectedSampleId?: string | null;
  className?: string;
  onTaskStarted: (taskId: string, sampleId: string) => void;
  onBatchAnalysisStarted?: (
    tasks: Array<{ sampleId: string; taskId: string }>,
  ) => void;
  onSampleReady: (sampleId: string) => void;
  onSampleChanged?: () => void;
  onSelectSample?: (sampleId: string) => void;
};

export function SampleInputPanel({
  projectId,
  samples = [],
  activeSample,
  selectedSampleId,
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
      onBatchAnalysisStarted?.(data.tasks);
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

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="shrink-0">
        <CardTitle>样例视频</CardTitle>
        <CardDescription>
          支持一次上传多个视频；链接导入由服务端下载，前端不调用 yt-dlp。
        </CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
        <Tabs defaultValue="local" className="shrink-0">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="local">本地上传</TabsTrigger>
            <TabsTrigger value="url" className="gap-2">
              <Link2 className="h-4 w-4" />
              URL 导入
            </TabsTrigger>
          </TabsList>
          <TabsContent value="local" className="mt-3 space-y-3">
            <FileDropzone
              accept="video/*"
              multiple
              disabled={busy}
              title="上传样例视频"
              hint="点击选择或拖拽多个视频文件到此处"
              onFiles={(files) => void handleLocalUpload(files)}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => void handleAnalyzeLatestBatch()}
            >
              分析最近批次
            </Button>
          </TabsContent>
          <TabsContent value="url" className="mt-3 space-y-4">
            <CookieUploadPanel />
            <Label htmlFor="sample-url">视频页面 URL</Label>
            <Input
              id="sample-url"
              placeholder="https://..."
              value={url}
              disabled={busy}
              onChange={(e) => setUrl(e.target.value)}
            />
            <Button
              type="button"
              disabled={busy || !url.trim()}
              onClick={() => void handleUrlImport()}
            >
              开始 URL 导入
            </Button>
          </TabsContent>
        </Tabs>

        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <p className="shrink-0 text-sm font-medium">已上传样例</p>
          <PaginatedGrid
            items={previewSamples}
            pageSize={SAMPLE_PAGE_SIZE}
            resetKey={previewSamples.map((sample) => sample.id).join(",")}
            getKey={(sample) => sample.id}
            renderItem={(sample) => (
              <SampleVideoCard
                sample={sample}
                selected={sample.id === effectiveSelectedId}
                onSelect={onSelectSample}
              />
            )}
            emptyMessage="暂无样例视频，请上传或导入。"
          />
        </div>

        {status && (
          <p className="shrink-0 text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
