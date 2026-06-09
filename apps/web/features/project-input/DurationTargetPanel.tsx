"use client";

import type { DurationTarget } from "@videomaker/contracts";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";

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
  formatDurationSec,
  generationStrategyHint,
} from "@/lib/durationTargetLabels";
import {
  getDurationRecommendation,
  type DurationRecommendationResponse,
} from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";

export type DurationTargetPanelHandle = {
  getDurationTarget: () => DurationTarget | undefined;
};

type DurationTargetPanelProps = {
  projectId: string;
  initialTarget?: DurationTarget | null;
};

export const DurationTargetPanel = forwardRef<
  DurationTargetPanelHandle,
  DurationTargetPanelProps
>(function DurationTargetPanel({ projectId, initialTarget }, ref) {
  const [recommendation, setRecommendation] =
    useState<DurationRecommendationResponse | null>(null);
  const [targetSec, setTargetSec] = useState<string>("");
  const [minSec, setMinSec] = useState<string>("");
  const [maxSec, setMaxSec] = useState<string>("");
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
      })
      .catch((err) => {
        if (!cancelled) setStatus(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, initialTarget?.maxSec, initialTarget?.minSec, initialTarget?.targetSec]);

  const parsedTarget = Number.parseFloat(targetSec);
  const maxTarget = recommendation?.maxTargetSec ?? 600;

  const strategyHint = useMemo(() => {
    if (!Number.isFinite(parsedTarget) || parsedTarget <= 0) return null;
    return generationStrategyHint(parsedTarget);
  }, [parsedTarget]);

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
    if (result.minSec != null && result.targetSec < result.minSec) {
      result.targetSec = result.minSec;
    }
    if (result.maxSec != null && result.targetSec > result.maxSec) {
      result.targetSec = result.maxSec;
    }
    return result;
  };

  useImperativeHandle(ref, () => ({ getDurationTarget: buildDurationTarget }), [
    maxSec,
    maxTarget,
    minSec,
    parsedTarget,
    recommendation,
  ]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>目标时长</CardTitle>
        <CardDescription>
          {recommendation
            ? `样例推荐 ${formatDurationSec(recommendation.recommendedSec)}，可在此调整目标生成时长`
            : "加载样例时长推荐…"}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
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
        </div>
        <div className="space-y-2">
          <Label htmlFor="duration-min-sec">可选下限（秒）</Label>
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
          <Label htmlFor="duration-max-sec">可选上限（秒）</Label>
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
        {strategyHint && (
          <p className="text-sm text-muted-foreground sm:col-span-3">{strategyHint}</p>
        )}
        {status && (
          <p className="text-sm text-destructive sm:col-span-3" role="alert">
            {status}
          </p>
        )}
      </CardContent>
    </Card>
  );
});
