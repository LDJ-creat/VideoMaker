"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Info,
  Save,
} from "lucide-react";
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
  getModelGatewayStatus,
  updateModelGatewaySettings,
  type ModelGatewaySettingsUpdate,
  type ModelGatewayStatusResponse,
  type ProviderStatus,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

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

const PROVIDER_ORDER: Array<keyof ModelGatewayStatusResponse["providers"]> = [
  "text",
  "vision",
  "tts",
  "image",
  "video",
];

const SUMMARY_PROVIDERS: Array<keyof ModelGatewayStatusResponse["providers"]> = [
  "text",
  "image",
  "vision",
  "tts",
  "video",
];

const REQUIRED_PROVIDERS: Array<keyof ModelGatewayStatusResponse["providers"]> =
  ["text", "image"];

const DEFAULT_BASE_URL = "https://api.openai.com/v1";

type ProviderFormState = {
  baseUrl: string;
  model: string;
  apiKey: string;
  driver: string;
};

type ModelGatewayStatusPanelProps = {
  /** Collapsed by default on /projects; shows summary + expand for full form */
  defaultExpanded?: boolean;
};

function formFromStatus(
  key: keyof ModelGatewayStatusResponse["providers"],
  provider: ProviderStatus,
): ProviderFormState {
  return {
    baseUrl: provider.baseUrl ?? DEFAULT_BASE_URL,
    model: provider.model ?? "",
    apiKey: "",
    driver:
      provider.driver ?? (key === "video" ? "generic_job" : "openai_compatible"),
  };
}

function ProviderChip({
  name,
  status,
}: {
  name: keyof ModelGatewayStatusResponse["providers"];
  status: ProviderStatus;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs",
        status.configured
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
          : "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200",
      )}
    >
      {status.configured ? (
        <CheckCircle2 className="h-3 w-3 shrink-0" aria-hidden />
      ) : (
        <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden />
      )}
      <span>{PROVIDER_LABELS[name]}</span>
      {status.model && (
        <span className="max-w-[8rem] truncate text-muted-foreground">
          {status.model}
        </span>
      )}
    </span>
  );
}

function ProviderStatusLine({ status }: { status: ProviderStatus }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {status.configured ? (
        <>
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
          <span>已配置{status.model ? ` · ${status.model}` : ""}</span>
        </>
      ) : (
        <>
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden />
          <span>未配置</span>
        </>
      )}
      {status.hasApiKey && <span>· API Key 已保存</span>}
    </div>
  );
}

export function ModelGatewayStatusPanel({
  defaultExpanded = false,
}: ModelGatewayStatusPanelProps = {}) {
  const detailsId = useId();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [status, setStatus] = useState<ModelGatewayStatusResponse | null>(null);
  const [forms, setForms] = useState<Record<string, ProviderFormState> | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await getModelGatewayStatus();
      setStatus(data);
      const next: Record<string, ProviderFormState> = {};
      for (const key of PROVIDER_ORDER) {
        next[key] = formFromStatus(key, data.providers[key]);
      }
      setForms(next);
      setLoadError(null);
    } catch (err) {
      setStatus(null);
      setForms(null);
      setLoadError(getErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const updateField = (
    provider: keyof ModelGatewayStatusResponse["providers"],
    field: keyof ProviderFormState,
    value: string,
  ) => {
    setForms((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [provider]: { ...prev[provider], [field]: value },
      };
    });
  };

  const handleSave = async () => {
    if (!forms) return;
    setBusy(true);
    setSaveError(null);
    try {
      const providers: ModelGatewaySettingsUpdate["providers"] = {};
      for (const key of PROVIDER_ORDER) {
        const form = forms[key];
        const entry: NonNullable<
          ModelGatewaySettingsUpdate["providers"]
        >[typeof key] = {};
        const baseUrl = form.baseUrl.trim();
        const model = form.model.trim();
        if (baseUrl) entry.baseUrl = baseUrl;
        if (model) entry.model = model;
        if (key === "video" && form.driver.trim()) {
          entry.driver = form.driver.trim();
        }
        if (form.apiKey.trim()) {
          entry.apiKey = form.apiKey.trim();
        }
        if (Object.keys(entry).length > 0) {
          providers[key] = entry;
        }
      }
      if (Object.keys(providers).length === 0) {
        setSaveError("请至少填写一个提供方的 Base URL、Model 或 API Key");
        setBusy(false);
        return;
      }
      const { data } = await updateModelGatewaySettings({ providers });
      setStatus(data);
      const next: Record<string, ProviderFormState> = {};
      for (const key of PROVIDER_ORDER) {
        next[key] = formFromStatus(key, data.providers[key]);
      }
      setForms(next);
    } catch (err) {
      setSaveError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const missingRequired =
    status &&
    !status.fixtureMode &&
    REQUIRED_PROVIDERS.some((key) => !status.providers[key].configured);

  const liveReady =
    status &&
    !status.fixtureMode &&
    REQUIRED_PROVIDERS.every((key) => status.providers[key].configured);

  return (
    <Card className="border-dashed" data-testid="model-gateway-status-panel">
      <CardHeader className="pb-3">
        <button
          type="button"
          className="flex w-full items-start gap-3 text-left"
          aria-expanded={expanded}
          aria-controls={detailsId}
          aria-label={
            expanded ? "收起模型服务配置" : "展开模型服务配置"
          }
          onClick={() => setExpanded((value) => !value)}
        >
          <ChevronDown
            className={cn(
              "mt-0.5 h-5 w-5 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
            aria-hidden
          />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">模型服务</CardTitle>
              {status?.fixtureMode && (
                <Badge variant="secondary">
                  <Info className="mr-1 h-3 w-3" />
                  Fixture 模式
                </Badge>
              )}
              {status && !status.fixtureMode && liveReady && (
                <Badge
                  variant="secondary"
                  className="border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
                >
                  Live 已就绪
                </Badge>
              )}
              {missingRequired && (
                <Badge
                  variant="secondary"
                  className="border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200"
                >
                  需配置
                </Badge>
              )}
            </div>
            <CardDescription className="text-left">
              全局模型凭据（本机 SQLite，密钥不回显）。展开可编辑；默认走真实模型，无
              Key 冒烟时可设 VIDEOMAKER_FIXTURE_MODE=true
            </CardDescription>
            {status && !loadError && (
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {SUMMARY_PROVIDERS.map((key) => (
                  <ProviderChip
                    key={key}
                    name={key}
                    status={status.providers[key]}
                  />
                ))}
              </div>
            )}
          </div>
        </button>
      </CardHeader>

      {loadError && (
        <CardContent className="pt-0">
          <p className="text-sm text-destructive" role="alert">
            {loadError}
          </p>
        </CardContent>
      )}

      {expanded && status && forms && (
        <CardContent id={detailsId} className="space-y-4 border-t pt-4">
          {missingRequired && (
            <div
              className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200"
              role="status"
            >
              <p className="font-medium">模型服务未就绪，请填写并保存</p>
              <ul className="mt-1 list-inside list-disc text-xs">
                {REQUIRED_PROVIDERS.filter(
                  (key) => !status.providers[key].configured,
                ).map((key) => (
                  <li key={key}>{PROVIDER_LABELS[key]}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-4">
            {PROVIDER_ORDER.map((key) => (
              <div
                key={key}
                className="space-y-2 rounded-md border border-border/60 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">
                    {PROVIDER_LABELS[key]}
                  </span>
                  <ProviderStatusLine status={status.providers[key]} />
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1 sm:col-span-2">
                    <Label htmlFor={`${key}-base-url`}>Base URL</Label>
                    <Input
                      id={`${key}-base-url`}
                      value={forms[key].baseUrl}
                      onChange={(e) =>
                        updateField(key, "baseUrl", e.target.value)
                      }
                      placeholder={DEFAULT_BASE_URL}
                      disabled={busy}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`${key}-model`}>Model</Label>
                    <Input
                      id={`${key}-model`}
                      value={forms[key].model}
                      onChange={(e) =>
                        updateField(key, "model", e.target.value)
                      }
                      disabled={busy}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`${key}-api-key`}>API Key</Label>
                    <Input
                      id={`${key}-api-key`}
                      type="password"
                      value={forms[key].apiKey}
                      onChange={(e) =>
                        updateField(key, "apiKey", e.target.value)
                      }
                      placeholder={
                        status.providers[key].hasApiKey
                          ? "留空则不修改"
                          : "输入 API Key"
                      }
                      disabled={busy}
                      autoComplete="off"
                    />
                  </div>
                  {key === "video" && (
                    <div className="space-y-1 sm:col-span-2">
                      <Label htmlFor={`${key}-driver`}>Driver</Label>
                      <Input
                        id={`${key}-driver`}
                        value={forms[key].driver}
                        onChange={(e) =>
                          updateField(key, "driver", e.target.value)
                        }
                        disabled={busy}
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <Button
            type="button"
            size="sm"
            disabled={busy}
            onClick={() => void handleSave()}
          >
            <Save className="mr-2 h-4 w-4" />
            {busy ? "保存中…" : "保存配置"}
          </Button>

          {saveError && (
            <p className="text-sm text-destructive" role="alert">
              {saveError}
            </p>
          )}
        </CardContent>
      )}

      {!expanded && missingRequired && !loadError && (
        <CardContent className="border-t pt-3">
          <p className="text-xs text-amber-700 dark:text-amber-300">
            Live 演示前请展开并配置文本、生图等凭据。
          </p>
        </CardContent>
      )}
    </Card>
  );
}
