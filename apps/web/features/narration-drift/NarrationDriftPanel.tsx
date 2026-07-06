"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  fixNarrationScriptSlot,
  getNarrationDrift,
  getNarrationTiming,
  getTask,
} from "@/lib/apiClient";
import { generationCanonicalNarrationAudioUrl } from "@/lib/artifactUrl";
import { formatDurationSec } from "@/lib/durationTargetLabels";
import { getErrorMessage, isNarrationTimingNotReadyError } from "@/lib/errors";

type DriftSlot = {
  slotId: string;
  estimatedSec: number;
  measuredSec: number;
  driftRatio: number;
  rootCause: string;
  resolutionPath: string;
  warnings?: string[];
};

type NarrationDriftPanelProps = {
  projectId: string;
  generationId: string;
  enabled?: boolean;
  onDraftUpdated?: () => void;
};

async function waitForTaskCompletion(taskId: string): Promise<void> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const { data } = await getTask(taskId);
    const status = data.status ?? "";
    if (status === "succeeded" || status === "failed" || status === "cancelled") {
      if (status === "failed") {
        throw new Error(data.message || "Fix narration script failed");
      }
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Timed out waiting for narration script fix");
}

export function NarrationDriftPanel({
  projectId,
  generationId,
  enabled = true,
  onDraftUpdated,
}: NarrationDriftPanelProps) {
  const [timing, setTiming] = useState<Record<string, unknown> | null>(null);
  const [drift, setDrift] = useState<{ slots?: DriftSlot[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busySlotId, setBusySlotId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!enabled) {
      return;
    }
    setError(null);
    try {
      const [{ data: timingData }, { data: driftData }] = await Promise.all([
        getNarrationTiming(generationId),
        getNarrationDrift(generationId),
      ]);
      setTiming(timingData);
      setDrift(driftData as { slots?: DriftSlot[] });
    } catch (err) {
      setTiming(null);
      setDrift(null);
      if (isNarrationTimingNotReadyError(err)) {
        setError(null);
        return;
      }
      setError(getErrorMessage(err));
    }
  }, [enabled, generationId]);

  useEffect(() => {
    if (!enabled) {
      setTiming(null);
      setDrift(null);
      setError(null);
      return;
    }
    void reload();
  }, [enabled, reload]);

  const slots = drift?.slots ?? [];
  const durationSec =
    typeof timing?.durationSec === "number" ? timing.durationSec : null;
  const canonicalAudioUrl = generationCanonicalNarrationAudioUrl(
    projectId,
    generationId,
  );

  async function handleFixScript(slotId: string) {
    setBusySlotId(slotId);
    setError(null);
    try {
      const { data } = await fixNarrationScriptSlot(generationId, slotId, {});
      if (data.queued && data.taskId) {
        await waitForTaskCompletion(data.taskId);
      }
      await reload();
      onDraftUpdated?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusySlotId(null);
    }
  }

  if (!enabled) {
    return null;
  }

  if (!timing && !drift && !error) {
    return null;
  }

  return (
    <Card data-testid="narration-drift-panel">
      <CardHeader>
        <CardTitle>定稿口播时长</CardTitle>
        <CardDescription>
          分镜审核后的 canonical TTS 实测窗口；偏差较大时会自动适配画面节奏或提示修正文案。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {durationSec != null ? (
          <p className="text-sm text-muted-foreground">
            全片口播时长 {formatDurationSec(durationSec)}
          </p>
        ) : null}
        {timing ? (
          <audio controls src={canonicalAudioUrl} className="w-full" data-testid="canonical-narration-audio" />
        ) : null}
        {slots.length > 0 ? (
          <ul className="space-y-2">
            {slots.map((slot) => {
              const driftPct = Math.round(Math.abs(slot.driftRatio - 1) * 100);
              const needsFix =
                slot.resolutionPath === "user_pending" ||
                slot.resolutionPath === "script_revise";
              return (
                <li
                  key={slot.slotId}
                  className="rounded-md border p-3 text-sm"
                  data-testid={`drift-slot-${slot.slotId}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{slot.slotId}</span>
                    <Badge variant={needsFix ? "destructive" : "secondary"}>
                      {slot.rootCause}
                    </Badge>
                    {driftPct > 15 ? (
                      <Badge variant="outline">偏差 {driftPct}%</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    预估 {formatDurationSec(slot.estimatedSec)} → 实测{" "}
                    {formatDurationSec(slot.measuredSec)}
                  </p>
                  {needsFix ? (
                    <Button
                      type="button"
                      size="sm"
                      className="mt-2"
                      disabled={busySlotId === slot.slotId}
                      onClick={() => void handleFixScript(slot.slotId)}
                      data-testid={`fix-script-${slot.slotId}`}
                    >
                      修正本镜文案并重合成口播
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
