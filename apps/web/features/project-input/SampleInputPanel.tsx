"use client";

import { Link2, Upload } from "lucide-react";
import { useState } from "react";

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
import {
  importSampleFromUrl,
  uploadSampleVideo,
} from "@/lib/apiClient";

type SampleInputPanelProps = {
  apiBaseUrl: string;
  projectId: string;
  onTaskStarted: (taskId: string, sampleId: string) => void;
};

export function SampleInputPanel({
  apiBaseUrl,
  projectId,
  onTaskStarted,
}: SampleInputPanelProps) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const handleLocalUpload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setStatus(null);
    try {
      const result = await uploadSampleVideo(apiBaseUrl, projectId, file);
      setStatus(`已上传样例：${result.id}`);
      if (result.taskId) {
        onTaskStarted(result.taskId, result.id);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  };

  const handleUrlImport = async () => {
    if (!url.trim()) return;
    setBusy(true);
    setStatus(null);
    try {
      // Backend runs yt-dlp; frontend only calls API.
      const result = await importSampleFromUrl(apiBaseUrl, projectId, {
        url: url.trim(),
      });
      setStatus(`URL 导入已提交：${result.id}`);
      if (result.taskId) {
        onTaskStarted(result.taskId, result.id);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "URL 导入失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>样例视频</CardTitle>
        <CardDescription>
          本地文件或视频链接；链接导入由服务端下载，前端不调用 yt-dlp。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="local">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="local" className="gap-2">
              <Upload className="h-4 w-4" />
              本地上传
            </TabsTrigger>
            <TabsTrigger value="url" className="gap-2">
              <Link2 className="h-4 w-4" />
              URL 导入
            </TabsTrigger>
          </TabsList>
          <TabsContent value="local" className="space-y-3">
            <Label htmlFor="sample-file">选择视频文件</Label>
            <Input
              id="sample-file"
              type="file"
              accept="video/*"
              disabled={busy}
              onChange={(e) => void handleLocalUpload(e.target.files?.[0])}
            />
          </TabsContent>
          <TabsContent value="url" className="space-y-3">
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
        {status && (
          <p className="mt-3 text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
