"use client";

import { Cookie, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type CookieUploadMode,
  getCookieStatus,
  uploadCookies,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

export function CookieUploadPanel() {
  const [configured, setConfigured] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [domains, setDomains] = useState<string[]>([]);
  const [uploadMode, setUploadMode] = useState<CookieUploadMode>("merge");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const { data } = await getCookieStatus();
      setConfigured(data.configured);
      setUpdatedAt(data.updatedAt ?? null);
      setDomains(data.domains ?? []);
    } catch {
      setConfigured(false);
      setUpdatedAt(null);
      setDomains([]);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const handleUpload = async (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".txt")) {
      setStatus("请上传 Netscape 格式的 cookies.txt 文件");
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const { data } = await uploadCookies(file, uploadMode);
      const modeLabel = uploadMode === "merge" ? "已合并" : "已替换";
      setStatus(
        `Cookie ${modeLabel}（本机全局，所有项目共用）。可重试 URL 导入。`,
      );
      if (data.domains?.length) {
        setDomains(data.domains);
      }
      await refreshStatus();
    } catch (err) {
      setStatus(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Cookie className="h-4 w-4" />
          平台 Cookie（全局 · URL 导入）
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <div className="flex flex-wrap gap-2 text-xs">
          <Button
            type="button"
            size="sm"
            variant={uploadMode === "merge" ? "default" : "outline"}
            disabled={busy}
            onClick={() => setUploadMode("merge")}
          >
            合并上传（推荐）
          </Button>
          <Button
            type="button"
            size="sm"
            variant={uploadMode === "replace" ? "default" : "outline"}
            disabled={busy}
            onClick={() => setUploadMode("replace")}
          >
            完全替换
          </Button>
        </div>
        <div className="space-y-2">
          <Label htmlFor="cookie-file">上传 cookies.txt</Label>
          <Input
            id="cookie-file"
            type="file"
            accept=".txt,text/plain"
            disabled={busy}
            onChange={(e) => void handleUpload(e.target.files?.[0])}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          状态：{configured ? "已配置（全局）" : "未配置"}
          {updatedAt ? ` · 更新于 ${updatedAt}` : ""}
        </p>
        {domains.length > 0 && (
          <p className="text-xs text-muted-foreground">
            已收录域名（节选）：{domains.slice(0, 6).join(", ")}
            {domains.length > 6 ? ` 等 ${domains.length} 个` : ""}
          </p>
        )}
        {status && (
          <p className="text-sm text-muted-foreground" role="status">
            {status}
          </p>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() => void refreshStatus()}
        >
          <Upload className="mr-2 h-3 w-3" />
          刷新状态
        </Button>
      </CardContent>
    </Card>
  );
}
