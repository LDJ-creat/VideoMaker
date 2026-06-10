"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Eye,
  Film,
  ImageIcon,
  Info,
  Loader2,
  MessageSquare,
  Mic,
  Save,
  ScanEye,
  type LucideIcon,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

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
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getModelGatewayStatus,
  testModelGatewayProvider,
  updateModelGatewaySettings,
  type ModelGatewayProviderProbeResponse,
  type ModelGatewaySettingsUpdate,
  type ModelGatewayStatusResponse,
  type ProviderStatus,
  type TtsPreferences,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

type ProviderKey = keyof ModelGatewayStatusResponse["providers"];

const PROVIDER_META: Record<
  ProviderKey,
  { label: string; description: string; icon: LucideIcon; required?: boolean }
> = {
  text: {
    label: "文本",
    description: "结构分析 Agent、语义映射与故事板编排",
    icon: MessageSquare,
    required: true,
  },
  vision: {
    label: "视觉",
    description: "样本关键帧理解、结构证据与多模态分析",
    icon: Eye,
    required: true,
  },
  videoUnderstanding: {
    label: "视频理解",
    description: "样例视频直连多模态结构分析 + 用户素材统一理解（Doubao/Ark）",
    icon: ScanEye,
    required: true,
  },
  image: {
    label: "生图",
    description: "缺口补全时的图片生成",
    icon: ImageIcon,
  },
  video: {
    label: "生视频",
    description: "视觉槽位的视频素材生成",
    icon: Film,
  },
  tts: {
    label: "配音",
    description: "旁白与口播语音合成",
    icon: Mic,
    required: true,
  },
};

const PROVIDER_GROUPS: Array<{
  id: string;
  title: string;
  description: string;
  providers: ProviderKey[];
}> = [
  {
    id: "analysis",
    title: "分析与推理",
    description: "用于样本结构分析、证据提取与 Agent 编排",
    providers: ["text", "vision", "videoUnderstanding"],
  },
  {
    id: "generation",
    title: "内容生成",
    description: "用于缺口补全时的图片与视频素材生成",
    providers: ["image", "video"],
  },
  {
    id: "tts",
    title: "配音",
    description: "用于全片旁白与口播",
    providers: ["tts"],
  },
];

const PROVIDER_ORDER: ProviderKey[] = [
  "text",
  "vision",
  "videoUnderstanding",
  "image",
  "video",
  "tts",
];

const DEFAULT_BASE_URL = "https://api.openai.com/v1";
const DEFAULT_VIDEO_UNDERSTANDING_BASE_URL =
  "https://ark.cn-beijing.volces.com/api/v3";
const DEFAULT_VOLCENGINE_TTS_BASE_URL =
  "https://openspeech.bytedance.com/api/v3/tts/unidirectional";
const DEFAULT_SEEDDANCE_MODEL = "doubao-seedance-2-0-260128";

const VIDEO_DRIVER_OPTIONS = [
  { value: "dashscope_wan", label: "阿里云百炼 Wan" },
  { value: "volcengine_seeddance", label: "火山方舟 SeedDance 2.0" },
  { value: "generic_job", label: "自定义 Job API（高级）" },
] as const;

const DEFAULT_TTS_PREFERENCES: TtsPreferences = {
  resourceId: "seed-tts-2.0",
  speaker: "zh_female_vv_uranus_bigtts",
  modelVariant: "seed-tts-2.0-expressive",
  speechRate: 0,
  loudnessRate: 0,
  emotion: null,
  emotionScale: 4,
  contextTexts: "",
  explicitLanguage: "zh",
  format: "pcm",
  sampleRate: 24000,
  chunkCharLimit: 400,
};

const REQUIRED_PROVIDERS: ProviderKey[] = [
  "text",
  "vision",
  "videoUnderstanding",
  "tts",
];

function defaultBaseUrlForProvider(key: ProviderKey): string {
  if (key === "videoUnderstanding") {
    return DEFAULT_VIDEO_UNDERSTANDING_BASE_URL;
  }
  if (key === "tts") {
    return DEFAULT_VOLCENGINE_TTS_BASE_URL;
  }
  return DEFAULT_BASE_URL;
}

function defaultDriverForProvider(key: ProviderKey): string {
  if (key === "video") {
    return "generic_job";
  }
  if (key === "tts") {
    return "volcengine_tts";
  }
  return "openai_compatible";
}

function applyVideoDriverSideEffects(
  form: ProviderFormState,
  driver: string,
): ProviderFormState {
  const next = { ...form, driver };
  if (driver === "volcengine_seeddance") {
    const base = form.baseUrl.trim();
    if (!base || base === DEFAULT_BASE_URL) {
      next.baseUrl = DEFAULT_VIDEO_UNDERSTANDING_BASE_URL;
    }
    if (!form.model.trim()) {
      next.model = DEFAULT_SEEDDANCE_MODEL;
    }
  }
  return next;
}

function ttsPrefsFromStatus(status: ModelGatewayStatusResponse): TtsPreferences {
  return { ...DEFAULT_TTS_PREFERENCES, ...status.ttsPreferences };
}

function isTtsPrefsDirty(
  form: TtsPreferences,
  saved: TtsPreferences,
): boolean {
  return (Object.keys(DEFAULT_TTS_PREFERENCES) as Array<keyof TtsPreferences>).some(
    (key) => form[key] !== saved[key],
  );
}

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
  key: ProviderKey,
  provider: ProviderStatus,
): ProviderFormState {
  return {
    baseUrl: provider.baseUrl ?? defaultBaseUrlForProvider(key),
    model: provider.model ?? "",
    apiKey: "",
    driver: provider.driver ?? defaultDriverForProvider(key),
  };
}

function isProviderDirty(
  key: ProviderKey,
  form: ProviderFormState,
  provider: ProviderStatus,
): boolean {
  const savedBase = provider.baseUrl ?? defaultBaseUrlForProvider(key);
  const savedModel = provider.model ?? "";
  const savedDriver = provider.driver ?? defaultDriverForProvider(key);
  return (
    form.baseUrl.trim() !== savedBase.trim() ||
    form.model.trim() !== savedModel.trim() ||
    form.apiKey.trim().length > 0 ||
    (key === "video" && form.driver.trim() !== savedDriver.trim()) ||
    (key === "tts" && form.driver.trim() !== savedDriver.trim())
  );
}

function ProviderChip({
  name,
  status,
  dirty,
  active,
  onNavigate,
}: {
  name: ProviderKey;
  status: ProviderStatus;
  dirty?: boolean;
  active?: boolean;
  onNavigate: (name: ProviderKey) => void;
}) {
  const meta = PROVIDER_META[name];
  const Icon = meta.icon;

  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onNavigate(name);
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs transition-colors",
        "hover:ring-1 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active && "ring-1 ring-ring/60",
        status.configured
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
          : "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200",
      )}
      aria-label={`跳转到${meta.label}配置`}
      aria-current={active ? "true" : undefined}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      {status.configured ? (
        <CheckCircle2 className="h-3 w-3 shrink-0" aria-hidden />
      ) : (
        <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden />
      )}
      <span>
        {meta.label}
        {meta.required ? (
          <span className="text-amber-600 dark:text-amber-400">*</span>
        ) : null}
      </span>
      {status.model && (
        <span className="max-w-[8rem] truncate text-muted-foreground">
          {status.model}
        </span>
      )}
      {dirty ? (
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
          title="有未保存的修改"
          aria-hidden
        />
      ) : null}
    </button>
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

function ProviderProbeResultBanner({
  result,
}: {
  result: ModelGatewayProviderProbeResponse;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-xs",
        result.ok
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
          : "border-destructive/40 bg-destructive/10 text-destructive",
      )}
      role="status"
    >
      <p className="font-medium">
        {result.ok ? "测试通过" : "测试失败"} · {result.message}
        {result.latencyMs > 0 ? ` · ${result.latencyMs}ms` : ""}
      </p>
      {result.replyPreview ? (
        <p className="mt-1 text-muted-foreground">
          模型回复：{result.replyPreview}
        </p>
      ) : null}
      {!result.ok && result.detail ? (
        <p className="mt-1 break-all opacity-90">{result.detail}</p>
      ) : null}
    </div>
  );
}

function ProviderFormFields({
  providerKey,
  form,
  status,
  busy,
  probing,
  probeResult,
  onFieldChange,
  onTestConnection,
}: {
  providerKey: ProviderKey;
  form: ProviderFormState;
  status: ProviderStatus;
  busy: boolean;
  probing?: boolean;
  probeResult?: ModelGatewayProviderProbeResponse | null;
  onFieldChange: (
    field: keyof ProviderFormState,
    value: string,
  ) => void;
  onTestConnection?: () => void;
}) {
  const meta = PROVIDER_META[providerKey];
  const Icon = meta.icon;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
            <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
          </span>
          <div>
            <p className="text-sm font-medium">
              {meta.label}
              {meta.required ? (
                <span className="ml-0.5 text-amber-600 dark:text-amber-400">
                  *
                </span>
              ) : null}
            </p>
            <p className="text-xs text-muted-foreground">{meta.description}</p>
          </div>
        </div>
        <ProviderStatusLine status={status} />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor={`${providerKey}-base-url`}>Base URL</Label>
          <Input
            id={`${providerKey}-base-url`}
            value={form.baseUrl}
            onChange={(e) => onFieldChange("baseUrl", e.target.value)}
            placeholder={DEFAULT_BASE_URL}
            disabled={busy}
          />
          {providerKey === "text" ? (
            <p className="text-xs text-muted-foreground">
              支持 OpenAI 风格根路径（如 https://api.openai.com/v1）或已含
              /chat/completions 的完整 endpoint（如火山方舟）。
            </p>
          ) : null}
          {providerKey === "tts" ? (
            <p className="text-xs text-muted-foreground">
              豆包语音请使用 openspeech 端点；API Key 来自豆包语音控制台，与方舟
              Ark Key 不同。
            </p>
          ) : null}
          {providerKey === "video" ? (
            <p className="text-xs text-muted-foreground">
              SeedDance 使用火山方舟端点；API Key 来自方舟控制台，与豆包语音 Key
              不同。
            </p>
          ) : null}
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${providerKey}-model`}>Model</Label>
          <Input
            id={`${providerKey}-model`}
            value={form.model}
            onChange={(e) => onFieldChange("model", e.target.value)}
            disabled={busy}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${providerKey}-api-key`}>API Key</Label>
          <Input
            id={`${providerKey}-api-key`}
            type="password"
            value={form.apiKey}
            onChange={(e) => onFieldChange("apiKey", e.target.value)}
            placeholder={
              status.hasApiKey ? "留空则不修改" : "输入 API Key"
            }
            disabled={busy}
            autoComplete="off"
          />
        </div>
        {providerKey === "video" && (
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`${providerKey}-driver`}>Driver</Label>
            <NativeSelect
              id={`${providerKey}-driver`}
              className="h-9 py-1"
              value={form.driver || defaultDriverForProvider("video")}
              onChange={(e) => onFieldChange("driver", e.target.value)}
              disabled={busy}
            >
              {VIDEO_DRIVER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
        {providerKey === "tts" && (
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor={`${providerKey}-driver`}>Driver</Label>
            <NativeSelect
              id={`${providerKey}-driver`}
              className="h-9 py-1"
              value={form.driver || defaultDriverForProvider("tts")}
              onChange={(e) => onFieldChange("driver", e.target.value)}
              disabled={busy}
            >
              <option value="volcengine_tts">豆包语音 V3</option>
              <option value="openai_compatible">OpenAI 兼容</option>
            </NativeSelect>
          </div>
        )}
      </div>

      {onTestConnection ? (
        <div className="space-y-2 border-t border-border/50 pt-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy || probing}
            onClick={onTestConnection}
          >
            {probing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : null}
            {probing ? "测试中…" : "测试连接"}
          </Button>
          {probeResult ? <ProviderProbeResultBanner result={probeResult} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function TtsPreferencesFields({
  form,
  busy,
  onChange,
}: {
  form: TtsPreferences;
  busy: boolean;
  onChange: (field: keyof TtsPreferences, value: string | number | null) => void;
}) {
  return (
    <div className="space-y-3 border-t border-border/50 pt-3">
      <p className="text-xs font-medium text-muted-foreground">豆包 TTS 精细参数</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="tts-resource-id">Resource ID</Label>
          <Input
            id="tts-resource-id"
            value={form.resourceId}
            onChange={(e) => onChange("resourceId", e.target.value)}
            disabled={busy}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="tts-speaker">Speaker（音色 ID）</Label>
          <Input
            id="tts-speaker"
            value={form.speaker}
            onChange={(e) => onChange("speaker", e.target.value)}
            disabled={busy}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="tts-model-variant">Model Variant</Label>
          <NativeSelect
            id="tts-model-variant"
            className="h-9 py-1"
            value={form.modelVariant}
            onChange={(e) => onChange("modelVariant", e.target.value)}
            disabled={busy}
          >
            <option value="seed-tts-2.0-expressive">seed-tts-2.0-expressive</option>
            <option value="seed-tts-2.0-standard">seed-tts-2.0-standard</option>
          </NativeSelect>
        </div>
        <div className="space-y-1">
          <Label htmlFor="tts-emotion">Emotion（可选）</Label>
          <Input
            id="tts-emotion"
            value={form.emotion ?? ""}
            onChange={(e) => onChange("emotion", e.target.value || null)}
            disabled={busy}
            placeholder="如 happy / sad"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="tts-speech-rate">语速 speechRate ({form.speechRate})</Label>
          <input
            id="tts-speech-rate"
            type="range"
            min={-50}
            max={100}
            value={form.speechRate}
            onChange={(e) => onChange("speechRate", Number(e.target.value))}
            disabled={busy}
            className="w-full"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="tts-loudness-rate">音量 loudnessRate ({form.loudnessRate})</Label>
          <input
            id="tts-loudness-rate"
            type="range"
            min={-50}
            max={100}
            value={form.loudnessRate}
            onChange={(e) => onChange("loudnessRate", Number(e.target.value))}
            disabled={busy}
            className="w-full"
          />
        </div>
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor="tts-context-texts">语气指令 contextTexts</Label>
          <Textarea
            id="tts-context-texts"
            value={form.contextTexts}
            onChange={(e) => onChange("contextTexts", e.target.value)}
            disabled={busy}
            rows={3}
            placeholder="短视频口播，语气自然有起伏"
          />
          <p className="text-xs text-muted-foreground">
            会与样本 structure.audio.voProfile 自动映射的指令拼接；2.0 音色需
            seed-tts-2.0-expressive。
          </p>
        </div>
      </div>
    </div>
  );
}

function initialGroupTabs(): Record<string, ProviderKey> {
  return Object.fromEntries(
    PROVIDER_GROUPS.map((group) => [group.id, group.providers[0]!]),
  );
}

export function ModelGatewayStatusPanel({
  defaultExpanded = false,
}: ModelGatewayStatusPanelProps = {}) {
  const detailsId = useId();
  const groupRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [status, setStatus] = useState<ModelGatewayStatusResponse | null>(null);
  const [forms, setForms] = useState<Record<string, ProviderFormState> | null>(
    null,
  );
  const [groupTabs, setGroupTabs] = useState<Record<string, ProviderKey>>(
    initialGroupTabs,
  );
  const [focusedProvider, setFocusedProvider] = useState<ProviderKey | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [probingProvider, setProbingProvider] = useState<ProviderKey | null>(
    null,
  );
  const [probeResults, setProbeResults] = useState<
    Partial<Record<ProviderKey, ModelGatewayProviderProbeResponse>>
  >({});
  const [ttsPrefs, setTtsPrefs] = useState<TtsPreferences>(DEFAULT_TTS_PREFERENCES);

  const refresh = useCallback(async () => {
    try {
      const { data } = await getModelGatewayStatus();
      setStatus(data);
      setTtsPrefs(ttsPrefsFromStatus(data));
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

  const dirtyProviders = useMemo(() => {
    if (!status || !forms) return new Set<ProviderKey>();
    const dirty = new Set<ProviderKey>();
    for (const key of PROVIDER_ORDER) {
      if (isProviderDirty(key, forms[key], status.providers[key])) {
        dirty.add(key);
      }
    }
    return dirty;
  }, [forms, status]);

  const focusProvider = useCallback((key: ProviderKey) => {
    setExpanded(true);
    setFocusedProvider(key);
    const group = PROVIDER_GROUPS.find((item) => item.providers.includes(key));
    if (group) {
      setGroupTabs((prev) => ({ ...prev, [group.id]: key }));
      requestAnimationFrame(() => {
        groupRefs.current[group.id]?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      });
    }
  }, []);

  const updateField = (
    provider: ProviderKey,
    field: keyof ProviderFormState,
    value: string,
  ) => {
    setForms((prev) => {
      if (!prev) return prev;
      let nextForm = { ...prev[provider], [field]: value };
      if (provider === "video" && field === "driver") {
        nextForm = applyVideoDriverSideEffects(nextForm, value);
      }
      return {
        ...prev,
        [provider]: nextForm,
      };
    });
    setProbeResults((prev) => {
      if (!prev[provider]) return prev;
      const next = { ...prev };
      delete next[provider];
      return next;
    });
  };

  const handleTestConnection = async (provider: ProviderKey) => {
    if (!forms || (provider !== "text" && provider !== "videoUnderstanding")) {
      return;
    }
    const form = forms[provider];
    setProbingProvider(provider);
    setProbeResults((prev) => {
      const next = { ...prev };
      delete next[provider];
      return next;
    });
    try {
      const { data } = await testModelGatewayProvider({
        provider,
        baseUrl: form.baseUrl.trim() || undefined,
        model: form.model.trim() || undefined,
        ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
      });
      setProbeResults((prev) => ({ ...prev, [provider]: data }));
    } catch (err) {
      setProbeResults((prev) => ({
        ...prev,
        [provider]: {
          provider,
          ok: false,
          latencyMs: 0,
          message: getErrorMessage(err),
          detail: null,
          replyPreview: null,
        },
      }));
    } finally {
      setProbingProvider(null);
    }
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
        if (key === "tts" && form.driver.trim()) {
          entry.driver = form.driver.trim();
        }
        if (form.apiKey.trim()) {
          entry.apiKey = form.apiKey.trim();
        }
        if (Object.keys(entry).length > 0) {
          providers[key] = entry;
        }
      }
      if (Object.keys(providers).length === 0 && !preferencesDirty) {
        setSaveError("请至少填写一个提供方的 Base URL、Model 或 API Key");
        setBusy(false);
        return;
      }
      const body: ModelGatewaySettingsUpdate = {};
      if (Object.keys(providers).length > 0) {
        body.providers = providers;
      }
      if (status && isTtsPrefsDirty(ttsPrefs, ttsPrefsFromStatus(status))) {
        body.preferences = { tts: ttsPrefs };
      }
      const { data } = await updateModelGatewaySettings(body);
      setStatus(data);
      setTtsPrefs(ttsPrefsFromStatus(data));
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

  const hasDirtyChanges = dirtyProviders.size > 0;

  const preferencesDirty =
    status != null && isTtsPrefsDirty(ttsPrefs, ttsPrefsFromStatus(status));

  const renderProviderForm = (key: ProviderKey) => (
    <div className="space-y-3">
      <ProviderFormFields
        providerKey={key}
        form={forms![key]}
        status={status!.providers[key]}
        busy={busy}
        probing={probingProvider === key}
        probeResult={probeResults[key] ?? null}
        onFieldChange={(field, value) => updateField(key, field, value)}
        onTestConnection={
          key === "text" || key === "videoUnderstanding"
            ? () => void handleTestConnection(key)
            : undefined
        }
      />
      {key === "tts" &&
      (forms![key].driver === "volcengine_tts" ||
        status!.providers.tts.driver === "volcengine_tts") ? (
        <TtsPreferencesFields
          form={ttsPrefs}
          busy={busy}
          onChange={(field, value) =>
            setTtsPrefs((prev) => ({
              ...prev,
              [field]: value,
            }))
          }
        />
      ) : null}
    </div>
  );

  return (
    <Card className="border-dashed" data-testid="model-gateway-status-panel">
      <CardHeader className="space-y-3 pb-3">
        <button
          type="button"
          className="flex w-full items-start gap-3 text-left"
          aria-expanded={expanded}
          aria-controls={detailsId}
          aria-label={expanded ? "收起模型服务配置" : "展开模型服务配置"}
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
              {hasDirtyChanges && expanded && (
                <Badge
                  variant="secondary"
                  className="border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200"
                >
                  有未保存修改
                </Badge>
              )}
            </div>
            <CardDescription className="text-left">
              全局模型凭据（本机 SQLite，密钥不回显）。点击标签可快速跳转；默认走真实模型，无
              Key 冒烟时可设 VIDEOMAKER_FIXTURE_MODE=true
            </CardDescription>
          </div>
        </button>
        {status && !loadError && (
          <div className="flex flex-wrap gap-1.5 pl-8">
            {PROVIDER_ORDER.map((key) => (
              <ProviderChip
                key={key}
                name={key}
                status={status.providers[key]}
                dirty={dirtyProviders.has(key)}
                active={focusedProvider === key}
                onNavigate={focusProvider}
              />
            ))}
          </div>
        )}
      </CardHeader>

      {loadError && (
        <CardContent className="pt-0">
          <p className="text-sm text-destructive" role="alert">
            {loadError}
          </p>
        </CardContent>
      )}

      {expanded && status && forms && (
        <CardContent id={detailsId} className="space-y-6 border-t pt-6">
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
                  <li key={key}>
                    {PROVIDER_META[key].label}
                    <span className="text-amber-600 dark:text-amber-400">
                      {" "}
                      (必需)
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-8">
            {PROVIDER_GROUPS.map((group, index) => (
              <section
                key={group.id}
                ref={(node: HTMLDivElement | null) => {
                  groupRefs.current[group.id] = node;
                }}
                className={cn(
                  "overflow-hidden rounded-xl border border-border bg-card shadow-sm",
                  index > 0 && "mt-2",
                )}
                data-testid={`provider-group-${group.id}`}
              >
                <div className="border-b border-border/60 bg-muted/30 px-5 py-4">
                  <h3 className="text-sm font-semibold tracking-tight">
                    {group.title}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {group.description}
                  </p>
                </div>

                <div className="px-5 py-5">
                  {group.providers.length === 1 ? (
                    renderProviderForm(group.providers[0]!)
                  ) : (
                    <Tabs
                      value={groupTabs[group.id]}
                      onValueChange={(value) => {
                        const key = value as ProviderKey;
                        setGroupTabs((prev) => ({ ...prev, [group.id]: key }));
                        setFocusedProvider(key);
                      }}
                    >
                      <TabsList
                        className={cn(
                          "grid w-full",
                          group.providers.length === 2
                            ? "grid-cols-2"
                            : "grid-cols-3",
                        )}
                      >
                        {group.providers.map((key) => {
                          const meta = PROVIDER_META[key];
                          const Icon = meta.icon;
                          const providerStatus = status.providers[key];
                          return (
                            <TabsTrigger
                              key={key}
                              value={key}
                              className="gap-1.5"
                            >
                              <Icon className="h-3.5 w-3.5" aria-hidden />
                              {meta.label}
                              {meta.required ? (
                                <span className="text-amber-600 dark:text-amber-400">
                                  *
                                </span>
                              ) : null}
                              {!providerStatus.configured && (
                                <AlertTriangle
                                  className="h-3 w-3 text-amber-500"
                                  aria-hidden
                                />
                              )}
                              {dirtyProviders.has(key) && (
                                <span
                                  className="h-1.5 w-1.5 rounded-full bg-amber-500"
                                  aria-hidden
                                />
                              )}
                            </TabsTrigger>
                          );
                        })}
                      </TabsList>
                      {group.providers.map((key) => (
                        <TabsContent key={key} value={key}>
                          {renderProviderForm(key)}
                        </TabsContent>
                      ))}
                    </Tabs>
                  )}
                </div>
              </section>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border/50 pt-4">
            <Button
              type="button"
              size="sm"
              disabled={busy}
              onClick={() => void handleSave()}
            >
              <Save className="mr-2 h-4 w-4" />
              {busy ? "保存中…" : "保存全部配置"}
            </Button>
            {hasDirtyChanges || preferencesDirty ? (
              <p className="text-xs text-muted-foreground">
                {dirtyProviders.size > 0
                  ? `${dirtyProviders.size} 项有未保存修改`
                  : "配音参数有未保存修改"}
              </p>
            ) : null}
          </div>

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
            Live 演示前请展开并配置文本、视觉、视频理解、配音等凭据。
          </p>
        </CardContent>
      )}
    </Card>
  );
}
