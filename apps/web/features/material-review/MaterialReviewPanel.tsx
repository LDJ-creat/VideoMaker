"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { MaterialReviewReport, MaterialReviewState } from "@videomaker/contracts";

import {
  approveMaterialReview,
  fetchMaterialReview,
  getTask,
  resolveGenerationByTask,
  reviseMaterialSlot,
} from "@/lib/apiClient";

type MaterialReviewPanelProps = {
  projectId: string;
  generationId: string | null;
  taskId?: string | null;
  stage: string | undefined;
  refreshKey?: number;
  onApproved?: () => void;
};

export function MaterialReviewPanel({
  projectId,
  generationId,
  taskId,
  stage,
  refreshKey = 0,
  onApproved,
}: MaterialReviewPanelProps) {
  const [state, setState] = useState<MaterialReviewState | null>(null);
  const [reports, setReports] = useState<Record<string, MaterialReviewReport>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvedGenerationId, setResolvedGenerationId] = useState<string | null>(
    null,
  );
  const effectiveGenerationId = generationId ?? resolvedGenerationId;
  const [reviseContext, setReviseContext] = useState<{
    scope: string;
    sourceGenerationId: string;
    affectedSlotIds?: string[];
  } | null>(null);
  const [awaitingSlotRegen, setAwaitingSlotRegen] = useState(false);

  useEffect(() => {
    setResolvedGenerationId(null);
  }, [generationId, taskId]);

  const visible =
    stage === "awaiting_material_review" && Boolean(generationId || taskId);
  const affectedSlotIds = useMemo(
    () => new Set(reviseContext?.affectedSlotIds ?? []),
    [reviseContext],
  );

  const load = useCallback(async () => {
    let targetGenerationId = generationId;
    if (!targetGenerationId && taskId) {
      try {
        const resolved = await resolveGenerationByTask(taskId);
        targetGenerationId = resolved.data.generationId;
      } catch (err) {
        setError(err instanceof Error ? err.message : "无法解析改片 generation");
        return;
      }
    }
    if (!targetGenerationId) return;
    setResolvedGenerationId(targetGenerationId);
    try {
      const result = await fetchMaterialReview(targetGenerationId);
      setState(result.data.state);
      setReports(result.data.reports);
      setPreviewUrls(result.data.slotPreviewUrls ?? {});
      setReviseContext(result.data.reviseContext ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载素材审核状态失败");
    }
  }, [generationId, taskId]);

  useEffect(() => {
    if (!visible) return;
    void load();
  }, [visible, load, refreshKey]);

  useEffect(() => {
    if (!visible || !awaitingSlotRegen || !taskId) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const result = await getTask(taskId);
        if (cancelled) return;
        const task = result.data;
        if (
          task.status === "awaiting_review" &&
          task.stage === "awaiting_material_review"
        ) {
          await load();
          setAwaitingSlotRegen(false);
          return;
        }
        if (task.status === "failed" || task.status === "cancelled") {
          setAwaitingSlotRegen(false);
          setError(task.message ?? "Slot 改片任务失败");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "轮询改片进度失败");
        }
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [visible, awaitingSlotRegen, taskId, load]);

  const slotIds = useMemo(() => Object.keys(state?.slots ?? {}), [state]);

  useEffect(() => {
    if (!selectedSlotId && slotIds.length > 0) {
      const preferred =
        reviseContext?.affectedSlotIds?.find((slotId) => slotIds.includes(slotId)) ??
        slotIds[0] ??
        null;
      setSelectedSlotId(preferred);
    }
  }, [slotIds, selectedSlotId, reviseContext]);

  const selectedReport = selectedSlotId ? reports[selectedSlotId] : undefined;
  const selectedPreviewUrl = selectedSlotId ? previewUrls[selectedSlotId] : undefined;
  const selectedPreviewKey =
    selectedSlotId && selectedPreviewUrl
      ? `${selectedSlotId}:${state?.slots?.[selectedSlotId]?.previewArtifactRef?.createdAt ?? selectedPreviewUrl}`
      : selectedSlotId ?? "none";

  async function handleRevise() {
    if (!effectiveGenerationId || !selectedSlotId || !instruction.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await reviseMaterialSlot(
        effectiveGenerationId,
        selectedSlotId,
        instruction.trim(),
      );
      setInstruction("");
      setAwaitingSlotRegen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交改片失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!effectiveGenerationId) return;
    setBusy(true);
    setError(null);
    try {
      await approveMaterialReview(effectiveGenerationId);
      onApproved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批准失败");
    } finally {
      setBusy(false);
    }
  }

  if (!visible) {
    return null;
  }

  return (
    <section className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 space-y-4">
      <header>
        <h3 className="text-base font-semibold">素材预览审核</h3>
        <p className="text-sm text-muted-foreground">
          预览各 slot 补全片段（无最终配音），可 NL 修改单 slot 后批准继续成片。
        </p>
        {reviseContext ? (
          <p className="text-xs text-muted-foreground mt-1">
            改片 fork · 来源 {reviseContext.sourceGenerationId || "上一版"}
            {reviseContext.affectedSlotIds?.length
              ? ` · 本次需审：${reviseContext.affectedSlotIds.join("、")}`
              : null}
          </p>
        ) : null}
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        {slotIds.map((slotId) => {
          const entry = state?.slots?.[slotId];
          const active = slotId === selectedSlotId;
          const inherited =
            reviseContext &&
            affectedSlotIds.size > 0 &&
            !affectedSlotIds.has(slotId) &&
            entry?.status === "agent_passed";
          const reviseTarget = affectedSlotIds.has(slotId);
          return (
            <button
              key={slotId}
              type="button"
              className={`rounded-md border px-3 py-1 text-sm ${active ? "border-primary bg-primary/10" : "border-border"}`}
              onClick={() => setSelectedSlotId(slotId)}
            >
              {slotId}
              {entry?.status ? ` · ${entry.status}` : ""}
              {inherited ? " · 继承" : reviseTarget ? " · 改片" : ""}
            </button>
          );
        })}
      </div>
      {selectedPreviewUrl ? (
        <div className="rounded-md border border-border overflow-hidden bg-black">
          <video
            key={selectedPreviewKey}
            src={selectedPreviewUrl}
            controls
            playsInline
            className="w-full max-h-80 object-contain"
          />
          <p className="px-3 py-2 text-xs text-muted-foreground">
            素材预览（无最终配音）· {projectId}
          </p>
        </div>
      ) : selectedSlotId ? (
        <p className="text-sm text-muted-foreground">该 slot 暂无可播放预览。</p>
      ) : null}
      {selectedReport ? (
        <div className="rounded-md border border-border p-3 text-sm space-y-2">
          <p>
            审阅结果：
            {selectedReport.approved ? "通过" : "未通过"}
            {selectedReport.reviewInputs?.mode ? ` (${selectedReport.reviewInputs.mode})` : ""}
          </p>
          {selectedReport.issues?.length ? (
            <ul className="list-disc pl-5">
              {selectedReport.issues.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {selectedReport.suggestions?.length ? (
            <ul className="list-disc pl-5 text-muted-foreground">
              {selectedReport.suggestions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="material-slot-revise">
          NL 修改当前 slot
        </label>
        <textarea
          id="material-slot-revise"
          className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="描述希望如何调整该 slot 的视觉包装…"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md bg-secondary px-3 py-2 text-sm"
            disabled={busy || !instruction.trim() || !selectedSlotId}
            onClick={() => void handleRevise()}
          >
            提交 slot 改片
          </button>
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
            disabled={busy || state?.status === "approved"}
            onClick={() => void handleApprove()}
          >
            批准素材并继续成片
          </button>
        </div>
      </div>
    </section>
  );
}
