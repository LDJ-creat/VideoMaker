"use client";

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
import { uploadAsset } from "@/lib/apiClient";

type AssetInputPanelProps = {
  apiBaseUrl: string;
  projectId: string;
};

export function AssetInputPanel({ apiBaseUrl, projectId }: AssetInputPanelProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    const names: string[] = [];
    try {
      for (const file of Array.from(files)) {
        const result = await uploadAsset(apiBaseUrl, projectId, file);
        names.push(result.id);
      }
      setStatus(`已上传 ${names.length} 个素材`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "素材上传失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>用户素材</CardTitle>
        <CardDescription>支持图片与视频，用于结构槽匹配</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Label htmlFor="asset-files">图片 / 视频</Label>
        <Input
          id="asset-files"
          type="file"
          accept="image/*,video/*"
          multiple
          disabled={busy}
          onChange={(e) => void handleUpload(e.target.files)}
        />
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={() => {
            const input = document.getElementById(
              "asset-files",
            ) as HTMLInputElement | null;
            void handleUpload(input?.files ?? null);
          }}
        >
          重新提交当前选择
        </Button>
        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
