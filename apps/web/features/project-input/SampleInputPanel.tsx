"use client";

import { Link2 } from "lucide-react";
import { useState } from "react";

import { FileDropzone } from "@/components/file-dropzone";
import { PaginatedGrid } from "@/components/paginated-grid";
import { Badge } from "@/components/ui/badge";
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
import type { ActiveSampleSummary } from "@/lib/apiClient";
import { importSampleFromUrl, uploadSampleVideo } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { validateHttpUrl, validateUploadSize } from "@/lib/validation";

const SAMPLE_PAGE_SIZE = 4;

type SampleInputPanelProps = {
  projectId: string;
  samples?: ActiveSampleSummary[];
  activeSample?: ActiveSampleSummary | null;
  className?: string;
  onTaskStarted: (taskId: string, sampleId: string) => void;
  onSampleReady: (sampleId: string) => void;
  onSampleChanged?: () => void;
};

function SamplePreviewCard({ sample }: { sample: ActiveSampleSummary }) {
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{sample.sourceKind}</Badge>
        <Badge variant="outline">{sample.status}</Badge>
        {sample.hasStructure && <Badge variant="ai">已分析</Badge>}
      </div>
      {sample.previewUrl ? (
        <video
          src={sample.previewUrl}
          controls
          className="max-h-36 w-full rounded-md bg-black"
        />
      ) : (
        <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-border bg-muted/20 text-xs text-muted-foreground">
          {sample.status === "importing" ? "视频导入中…" : "暂无可预览视频"}
        </div>
      )}
      <p className="font-mono text-xs text-muted-foreground truncate">
        {sample.fileName ?? sample.id}
      </p>
      {sample.sourceUrl && (
        <p className="text-xs text-muted-foreground truncate">
          来源：{sample.sourceUrl}
        </p>
      )}
    </div>
  );
}

export function SampleInputPanel({
  projectId,
  samples = [],
  activeSample,
  className,
  onTaskStarted,
  onSampleReady,
  onSampleChanged,
}: SampleInputPanelProps) {
  const [url, setUrl] = useState(activeSample?.sourceUrl ?? "");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const handleLocalUpload = async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    const sizeError = validateUploadSize(file);
    if (sizeError) {
      setStatus(sizeError);
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const { data: result } = await uploadSampleVideo(projectId, file);
      setStatus(`已上传样例：${result.id}（可点击「开始样例分析」）`);
      onSampleReady(result.id);
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

  const previewSamples =
    samples.length > 0
      ? samples
      : activeSample
        ? [activeSample]
        : [];

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="shrink-0">
        <CardTitle>样例视频</CardTitle>
        <CardDescription>
          本地文件或视频链接；链接导入由服务端下载，前端不调用 yt-dlp。
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
              disabled={busy}
              title="上传样例视频"
              hint="点击选择或拖拽视频文件到此处，仅支持单个视频文件"
              onFiles={(files) => void handleLocalUpload(files)}
            />
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
            renderItem={(sample) => <SamplePreviewCard sample={sample} />}
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
