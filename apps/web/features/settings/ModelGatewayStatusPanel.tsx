"use client";

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  getModelGatewayStatus,
  type ModelGatewayStatusResponse,
  type ProviderStatus,
} from "@/lib/apiClient";

const PROVIDER_LABELS: Record<
  keyof ModelGatewayStatusResponse["providers"],
  string
> = {
  text: "文本",
  vision: "视觉",
  tts: "配音",
  image: "生图",
  video: "生视频",
};

const REQUIRED_PROVIDERS: Array<keyof ModelGatewayStatusResponse["providers"]> =
  ["text", "image"];

const ENV_HINTS: Record<keyof ModelGatewayStatusResponse["providers"], string> =
  {
    text: "TEXT_API_KEY, TEXT_MODEL",
    vision: "VISION_API_KEY, VISION_MODEL",
    tts: "TTS_API_KEY, TTS_MODEL",
    image: "IMAGE_API_KEY, IMAGE_MODEL",
    video: "VIDEO_API_BASE, VIDEO_MODEL",
  };

function ProviderRow({
  name,
  status,
}: {
  name: keyof ModelGatewayStatusResponse["providers"];
  status: ProviderStatus;
}) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">{PROVIDER_LABELS[name]}</span>
      <div className="flex items-center gap-2">
        {status.configured ? (
          <>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />
            <span className="text-xs text-muted-foreground">
              {status.model ?? status.driver ?? "已配置"}
            </span>
          </>
        ) : (
          <>
            <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
            <span className="text-xs text-amber-600 dark:text-amber-400">
              未配置
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export function ModelGatewayStatusPanel() {
  const [status, setStatus] = useState<ModelGatewayStatusResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await getModelGatewayStatus();
      setStatus(data);
      setLoadError(null);
    } catch (err) {
      setStatus(null);
      setLoadError(err instanceof Error ? err.message : "无法加载模型状态");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const missingRequired =
    status &&
    REQUIRED_PROVIDERS.some((key) => !status.providers[key].configured);

  return (
    <Card className="border-dashed" data-testid="model-gateway-status-panel">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          模型服务
          {status?.fixtureMode && (
            <Badge variant="secondary">
              <Info className="mr-1 h-3 w-3" />
              Fixture 模式
            </Badge>
          )}
        </CardTitle>
        <CardDescription>服务端 ModelGateway 配置状态（不含密钥）</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {loadError && (
          <p className="text-sm text-destructive" role="alert">
            {loadError}
          </p>
        )}

        {status && (
          <>
            {missingRequired && (
              <div
                className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200"
                role="status"
              >
                <p className="font-medium">
                  模型服务未就绪，请在服务端配置环境变量
                </p>
                <ul className="mt-1 list-inside list-disc text-xs">
                  {REQUIRED_PROVIDERS.filter(
                    (key) => !status.providers[key].configured,
                  ).map((key) => (
                    <li key={key}>
                      {PROVIDER_LABELS[key]}：{ENV_HINTS[key]}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="space-y-2">
              {(
                Object.keys(PROVIDER_LABELS) as Array<
                  keyof ModelGatewayStatusResponse["providers"]
                >
              ).map((key) => (
                <ProviderRow key={key} name={key} status={status.providers[key]} />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
