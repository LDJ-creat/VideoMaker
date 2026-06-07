"use client";

import { CheckCircle2, ImageIcon, Loader2, Save } from "lucide-react";
import { useCallback, useEffect, useId, useState } from "react";

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
import {
  getStockMediaStatus,
  testStockMediaConnection,
  updateStockMediaSettings,
  type StockMediaStatusResponse,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

type StockMediaSettingsPanelProps = {
  defaultExpanded?: boolean;
};

export function StockMediaSettingsPanel({
  defaultExpanded = false,
}: StockMediaSettingsPanelProps) {
  const apiKeyInputId = useId();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [status, setStatus] = useState<StockMediaStatusResponse | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await getStockMediaStatus();
      setStatus(data);
    } catch (err) {
      setStatus(null);
      setError(getErrorMessage(err));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setError("请输入 Pexels API Key");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await updateStockMediaSettings({ apiKey: apiKey.trim() });
      setStatus(data);
      setApiKey("");
      setMessage("Pexels API Key 已保存");
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setSaving(false);
  };

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    setMessage(null);
    try {
      const { data } = await testStockMediaConnection(
        apiKey.trim() ? { apiKey: apiKey.trim() } : undefined,
      );
      setMessage(`连接成功，示例搜索结果 ${data.sampleResultCount ?? 0} 条`);
    } catch (err) {
      setError(getErrorMessage(err));
    }
    setTesting(false);
  };

  return (
    <Card>
      <CardHeader className="cursor-pointer" onClick={() => setExpanded((value) => !value)}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Pexels 素材库</CardTitle>
              <CardDescription>
                缺口补全时优先搜索免费 stock 图片/视频；未配置则自动使用 AIGC
              </CardDescription>
            </div>
          </div>
          <Badge variant={status?.configured ? "success" : "secondary"}>
            {loading ? "加载中" : status?.configured ? "已配置" : "未配置"}
          </Badge>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="space-y-4 border-t pt-4">
          <p className="text-sm text-muted-foreground">
            在{" "}
            <a
              href="https://www.pexels.com/api/"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              pexels.com/api
            </a>{" "}
            免费申请 API Key（默认 200 次/小时）。使用素材需署名摄影师与 Pexels 链接。
          </p>
          <div className="space-y-2">
            <Label htmlFor={apiKeyInputId}>Pexels API Key</Label>
            <Input
              id={apiKeyInputId}
              type="password"
              placeholder={status?.hasApiKey ? "已保存（输入新 Key 可覆盖）" : "粘贴 API Key"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {message && (
            <p className="flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              {message}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void handleSave()} disabled={saving || loading}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              保存
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleTest()}
              disabled={testing || loading}
            >
              {testing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              测试连接
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
