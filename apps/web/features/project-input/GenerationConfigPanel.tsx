"use client";

import type { AspectRatio, DurationTarget } from "@videomaker/contracts";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { VariantPicker } from "@/features/generation-variants/VariantPicker";
import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import {
  ASPECT_RATIO_OPTIONS,
  aspectRatioDefaultHint,
  aspectRatioLabel,
} from "@/lib/aspectRatioLabels";
import {
  formatDurationSec,
  generationStrategyHint,
} from "@/lib/durationTargetLabels";
import {
  getDurationRecommendation,
  type DurationRecommendationResponse,
  type ProjectAsset,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

export type GenerationConfigPanelHandle = {
  getDurationTarget: () => DurationTarget | undefined;
  getAspectRatio: () => AspectRatio | undefined;
};

type GenerationConfigPanelProps = {
  projectId: string;
  assets: ProjectAsset[];
  initialTarget?: DurationTarget | null;
  initialAspectRatio?: AspectRatio | null;
  selectedVariantIds: string[];
  onVariantChange: (variantIds: string[]) => void;
  variantsDisabled?: boolean;
  onAssetsChanged?: () => void;
};

export const GenerationConfigPanel = forwardRef<
  GenerationConfigPanelHandle,
  GenerationConfigPanelProps
>(function GenerationConfigPanel(
  {
    projectId,
    assets,
    initialTarget,
    initialAspectRatio,
    selectedVariantIds,
    onVariantChange,
    variantsDisabled,
    onAssetsChanged,
  },
  ref,
) {
  const [recommendation, setRecommendation] =
    useState<DurationRecommendationResponse | null>(null);
  const [targetSec, setTargetSec] = useState<string>("");
  const [minSec, setMinSec] = useState<string>("");
  const [maxSec, setMaxSec] = useState<string>("");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(
    initialAspectRatio ?? "9:16",
  );
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getDurationRecommendation(projectId)
      .then(({ data }) => {
        if (cancelled) return;
        setRecommendation(data);
        const initial = initialTarget?.targetSec ?? data.defaultTargetSec;
        setTargetSec(String(initial));
        if (initialTarget?.minSec != null) {
          setMinSec(String(initialTarget.minSec));
        }
        if (initialTarget?.maxSec != null) {
          setMaxSec(String(initialTarget.maxSec));
        }
        if (initialAspectRatio) {
          setAspectRatio(initialAspectRatio);
        }
      })
      .catch((err) => {
        if (!cancelled) setStatus(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [
    projectId,
    initialAspectRatio,
    initialTarget?.maxSec,
    initialTarget?.minSec,
    initialTarget?.targetSec,
  ]);

  const parsedTarget = Number.parseFloat(targetSec);
  const maxTarget = recommendation?.maxTargetSec ?? 600;

  const strategyHint = useMemo(() => {
    if (!Number.isFinite(parsedTarget) || parsedTarget <= 0) return null;
    return generationStrategyHint(parsedTarget);
  }, [parsedTarget]);

  const aspectHint = useMemo(() => aspectRatioDefaultHint(), []);

  const buildDurationTarget = (): DurationTarget | undefined => {
    if (!Number.isFinite(parsedTarget) || parsedTarget <= 0) return undefined;
    const clamped = Math.max(1, Math.min(parsedTarget, maxTarget));
    const result: DurationTarget = {
      targetSec: clamped,
      source: "user",
    };
    if (recommendation) {
      result.recommendedSec = recommendation.recommendedSec;
    }
    const min = Number.parseFloat(minSec);
    const max = Number.parseFloat(maxSec);
    if (Number.isFinite(min) && min > 0) result.minSec = min;
    if (Number.isFinite(max) && max > 0) result.maxSec = max;
    return result;
  };

  useImperativeHandle(
    ref,
    () => ({
      getDurationTarget: buildDurationTarget,
      getAspectRatio: () => aspectRatio,
    }),
    [aspectRatio, maxSec, maxTarget, minSec, parsedTarget, recommendation],
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 rounded-xl border border-border bg-muted/10 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2 sm:col-span-1">
          <Label htmlFor="duration-target-sec">目标时长（秒）</Label>
          <Input
            id="duration-target-sec"
            type="number"
            min={1}
            max={maxTarget}
            step={1}
            value={targetSec}
            onChange={(event) => setTargetSec(event.target.value)}
          />
          {recommendation ? (
            <p className="text-xs text-muted-foreground">
              推荐 {formatDurationSec(recommendation.recommendedSec)}
            </p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="duration-min-sec">可选下限</Label>
          <Input
            id="duration-min-sec"
            type="number"
            min={1}
            placeholder="不限"
            value={minSec}
            onChange={(event) => setMinSec(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="duration-max-sec">可选上限</Label>
          <Input
            id="duration-max-sec"
            type="number"
            min={1}
            max={maxTarget}
            placeholder="不限"
            value={maxSec}
            onChange={(event) => setMaxSec(event.target.value)}
          />
        </div>
        <div className="flex items-end">
          {strategyHint ? (
            <p className="text-xs text-muted-foreground">{strategyHint}</p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2 rounded-xl border border-border bg-muted/10 p-4">
        <Label>成片画幅</Label>
        <div className="flex flex-wrap gap-2">
          {ASPECT_RATIO_OPTIONS.map((option) => (
            <Button
              key={option}
              type="button"
              size="sm"
              variant={aspectRatio === option ? "default" : "outline"}
              onClick={() => setAspectRatio(option)}
            >
              {aspectRatioLabel(option)}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{aspectHint}</p>
        <p className="text-xs text-muted-foreground">
          画幅将同步影响渲染分辨率、素材库检索方向与字幕安全区。
        </p>
      </div>

      <VariantPicker
        selectedVariantIds={selectedVariantIds}
        onChange={onVariantChange}
        disabled={variantsDisabled}
      />

      <AssetInputPanel
        projectId={projectId}
        assets={assets}
        embedded
        onAssetsChanged={onAssetsChanged}
      />

      {status ? (
        <p className="text-sm text-destructive" role="alert">
          {status}
        </p>
      ) : null}
    </div>
  );
});
