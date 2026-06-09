"use client";

import type { ScriptDraft, StoryboardScene, TaskEvent } from "@videomaker/contracts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  approveMasterScript,
  approveStoryboardScript,
  getScriptDraft,
  nlReviseScriptDraft,
  updateScriptDraft,
} from "@/lib/apiClient";
import { ScriptNlReviseBar } from "@/features/script-review/ScriptNlReviseBar";
import {
  formatDurationSec,
  generationStrategyLabel,
  scriptReviewGateLabel,
} from "@/lib/durationTargetLabels";
import { getErrorMessage } from "@/lib/errors";
import { getTaskStageLabel } from "@/features/tasks/stageLabels";

export type ScriptReviewVariant = {
  generationId: string;
  variant: string;
  label: string;
  taskEvent: TaskEvent | null;
};

type ScriptReviewPanelProps = {
  projectId: string;
  variants: ScriptReviewVariant[];
  onApproved?: () => void;
};

type VariantDraftState = {
  draft: ScriptDraft | null;
  taskStage: string | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
};

function isMasterReviewStage(stage: string | null | undefined): boolean {
  return stage === "awaiting_master_review";
}

function isStoryboardReviewStage(stage: string | null | undefined): boolean {
  return stage === "awaiting_storyboard_review";
}

function StoryboardEditor({
  scenes,
  onChange,
  disabled,
}: {
  scenes: StoryboardScene[];
  onChange: (next: StoryboardScene[]) => void;
  disabled: boolean;
}) {
  const updateScene = (index: number, patch: Partial<StoryboardScene>) => {
    const next = scenes.map((scene, idx) =>
      idx === index ? { ...scene, ...patch } : scene,
    );
    onChange(next);
  };

  if (scenes.length === 0) {
    return <p className="text-sm text-muted-foreground">暂无分镜，等待 worker 生成…</p>;
  }

  return (
    <div className="space-y-3">
      {scenes.map((scene, index) => (
        <Card key={scene.id ?? index} className="border-dashed">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">
              场景 {index + 1}
              <span className="ml-2 font-mono text-xs text-muted-foreground">
                {scene.startSec}s – {scene.endSec}s
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 pb-4">
            <div className="space-y-1">
              <Label>画面</Label>
              <Textarea
                value={scene.visual}
                disabled={disabled}
                rows={2}
                onChange={(event) =>
                  updateScene(index, { visual: event.target.value })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>口播 / 字幕</Label>
              <Textarea
                value={scene.script}
                disabled={disabled}
                rows={2}
                onChange={(event) =>
                  updateScene(index, { script: event.target.value })
                }
              />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function ScriptReviewPanel({
  projectId,
  variants,
  onApproved,
}: ScriptReviewPanelProps) {
  const [activeId, setActiveId] = useState<string>(
    variants[0]?.generationId ?? "",
  );
  const [byVariant, setByVariant] = useState<Record<string, VariantDraftState>>(
    {},
  );
  const [masterText, setMasterText] = useState<Record<string, string>>({});
  const [nlSummary, setNlSummary] = useState<Record<string, string | null>>({});
  const loadedReviewKeysRef = useRef<Set<string>>(new Set());
  const dirtyMasterRef = useRef<Set<string>>(new Set());

  const reviewWatchKey = useMemo(
    () =>
      variants
        .map(
          (entry) =>
            `${entry.generationId}:${entry.taskEvent?.status ?? ""}:${entry.taskEvent?.stage ?? ""}`,
        )
        .join("|"),
    [variants],
  );

  const loadDraft = useCallback(async (generationId: string, force = false) => {
    if (!force && dirtyMasterRef.current.has(generationId)) {
      return;
    }
    setByVariant((prev) => ({
      ...prev,
      [generationId]: {
        draft: prev[generationId]?.draft ?? null,
        taskStage: prev[generationId]?.taskStage ?? null,
        loading: true,
        saving: false,
        error: null,
      },
    }));
    try {
      const { data } = await getScriptDraft(generationId);
      setByVariant((prev) => ({
        ...prev,
        [generationId]: {
          draft: data.draft,
          taskStage: data.taskStage ?? null,
          loading: false,
          saving: false,
          error: null,
        },
      }));
      setMasterText((prev) => ({
        ...prev,
        [generationId]: data.draft.masterNarration ?? "",
      }));
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [generationId]: {
          draft: prev[generationId]?.draft ?? null,
          taskStage: prev[generationId]?.taskStage ?? null,
          loading: false,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  }, []);

  useEffect(() => {
    if (variants.length === 0) return;
    if (!activeId || !variants.some((entry) => entry.generationId === activeId)) {
      setActiveId(variants[0]!.generationId);
    }
  }, [activeId, variants]);

  useEffect(() => {
    for (const entry of variants) {
      const stage = entry.taskEvent?.stage;
      const needsReview =
        stage === "awaiting_master_review" ||
        stage === "awaiting_storyboard_review" ||
        entry.taskEvent?.status === "awaiting_review";
      if (!needsReview) continue;
      const watchKey = `${entry.generationId}:${entry.taskEvent?.stage ?? entry.taskEvent?.status ?? ""}`;
      if (loadedReviewKeysRef.current.has(watchKey)) continue;
      loadedReviewKeysRef.current.add(watchKey);
      void loadDraft(entry.generationId);
    }
  }, [loadDraft, reviewWatchKey, variants]);

  const activeEntry = variants.find((entry) => entry.generationId === activeId);
  const activeState = byVariant[activeId];
  const activeStage =
    activeEntry?.taskEvent?.stage ?? activeState?.taskStage ?? null;
  const draft = activeState?.draft;
  const masterReview = isMasterReviewStage(activeStage);
  const storyboardReview = isStoryboardReviewStage(activeStage);

  const handleSaveMaster = async () => {
    if (!activeId) return;
    setByVariant((prev) => ({
      ...prev,
      [activeId]: { ...prev[activeId]!, saving: true, error: null },
    }));
    try {
      const { data } = await updateScriptDraft(activeId, {
        masterNarration: masterText[activeId] ?? "",
      });
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          draft: data.draft,
          saving: false,
          error: null,
        },
      }));
      dirtyMasterRef.current.delete(activeId);
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  };

  const handleApproveMaster = async () => {
    if (!activeId) return;
    setByVariant((prev) => ({
      ...prev,
      [activeId]: { ...prev[activeId]!, saving: true, error: null },
    }));
    try {
      await updateScriptDraft(activeId, {
        masterNarration: masterText[activeId] ?? "",
      });
      await approveMasterScript(activeId);
      dirtyMasterRef.current.delete(activeId);
      await loadDraft(activeId, true);
      onApproved?.();
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  };

  const handleSaveStoryboard = async (scenes: StoryboardScene[]) => {
    if (!activeId) return;
    setByVariant((prev) => ({
      ...prev,
      [activeId]: { ...prev[activeId]!, saving: true, error: null },
    }));
    try {
      const { data } = await updateScriptDraft(activeId, { storyboard: scenes });
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          draft: data.draft,
          saving: false,
          error: null,
        },
      }));
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  };

  const handleNlRevise = async (scope: "master" | "storyboard", instruction: string) => {
    if (!activeId) return;
    setByVariant((prev) => ({
      ...prev,
      [activeId]: { ...prev[activeId]!, saving: true, error: null },
    }));
    setNlSummary((prev) => ({ ...prev, [activeId]: null }));
    try {
      if (scope === "master") {
        await updateScriptDraft(activeId, {
          masterNarration: masterText[activeId] ?? "",
        });
      } else if (draft?.storyboard) {
        await updateScriptDraft(activeId, { storyboard: draft.storyboard });
      }
      const { data } = await nlReviseScriptDraft(activeId, { scope, instruction });
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          draft: data.draft,
          saving: false,
          error: null,
        },
      }));
      if (scope === "master") {
        setMasterText((prev) => ({
          ...prev,
          [activeId]: data.draft.masterNarration ?? "",
        }));
        dirtyMasterRef.current.delete(activeId);
      }
      setNlSummary((prev) => ({
        ...prev,
        [activeId]: data.summary ?? null,
      }));
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  };

  const handleApproveStoryboard = async () => {
    if (!activeId || !draft?.storyboard) return;
    setByVariant((prev) => ({
      ...prev,
      [activeId]: { ...prev[activeId]!, saving: true, error: null },
    }));
    try {
      await updateScriptDraft(activeId, { storyboard: draft.storyboard });
      await approveStoryboardScript(activeId);
      await loadDraft(activeId);
      onApproved?.();
    } catch (err) {
      setByVariant((prev) => ({
        ...prev,
        [activeId]: {
          ...prev[activeId]!,
          saving: false,
          error: getErrorMessage(err),
        },
      }));
    }
  };

  if (variants.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>脚本审核</CardTitle>
          <CardDescription>
            当前没有变体处于审核暂停点。人类审核仅在生成流水线暂停于总脚本或分镜阶段时生效；已完成或失败的任务请在「进度」面板查看或重试。
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-amber-500/30">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          脚本审核
          <Badge variant="outline">{scriptReviewGateLabel(activeStage)}</Badge>
        </CardTitle>
        <CardDescription>
          每个变体独立审核总脚本与分镜；项目 {projectId}
          {draft?.durationTargetSec != null && (
            <>
              {" "}
              · 目标时长 {formatDurationSec(draft.durationTargetSec)}
            </>
          )}
          {draft?.generationStrategy && (
            <> · {generationStrategyLabel(draft.generationStrategy)}</>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs value={activeId} onValueChange={setActiveId}>
          <TabsList>
            {variants.map((entry) => {
              const stage = entry.taskEvent?.stage;
              const needsReview =
                entry.taskEvent?.status === "awaiting_review" ||
                stage === "awaiting_master_review" ||
                stage === "awaiting_storyboard_review";
              return (
                <TabsTrigger key={entry.generationId} value={entry.generationId}>
                  {entry.label}
                  {needsReview ? " · 待审" : ""}
                </TabsTrigger>
              );
            })}
          </TabsList>
          {variants.map((entry) => (
            <TabsContent key={entry.generationId} value={entry.generationId}>
              {entry.taskEvent && (
                <p className="mb-3 text-xs text-muted-foreground">
                  {getTaskStageLabel(entry.taskEvent.stage)} ·{" "}
                  {entry.taskEvent.message}
                </p>
              )}
            </TabsContent>
          ))}
        </Tabs>

        {activeState?.loading && (
          <p className="text-sm text-muted-foreground">加载脚本草稿…</p>
        )}
        {activeState?.error && (
          <p className="text-sm text-destructive" role="alert">
            {activeState.error}
          </p>
        )}
        {nlSummary[activeId] && (
          <p className="text-sm text-muted-foreground" data-testid="nl-revise-summary">
            AI 修改说明：{nlSummary[activeId]}
          </p>
        )}

        {masterReview && (
          <div className="space-y-3">
            <ScriptNlReviseBar
              scope="master"
              busy={activeState?.saving}
              disabled={activeState?.loading}
              onSubmit={(instruction) => handleNlRevise("master", instruction)}
            />
            <Label htmlFor="master-narration">总脚本（Master Narration）</Label>
            <Textarea
              id="master-narration"
              rows={8}
              value={masterText[activeId] ?? ""}
              disabled={activeState?.saving}
              onChange={(event) => {
                dirtyMasterRef.current.add(activeId);
                setMasterText((prev) => ({
                  ...prev,
                  [activeId]: event.target.value,
                }));
              }}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={activeState?.saving}
                onClick={() => void handleSaveMaster()}
              >
                保存草稿
              </Button>
              <Button
                type="button"
                disabled={activeState?.saving}
                onClick={() => void handleApproveMaster()}
              >
                批准总脚本并生成分镜
              </Button>
            </div>
          </div>
        )}

        {storyboardReview && draft && (
          <div className="space-y-3">
            <ScriptNlReviseBar
              scope="storyboard"
              busy={activeState?.saving}
              disabled={activeState?.loading}
              onSubmit={(instruction) => handleNlRevise("storyboard", instruction)}
            />
            <StoryboardEditor
              scenes={draft.storyboard ?? []}
              disabled={Boolean(activeState?.saving)}
              onChange={(next) => {
                setByVariant((prev) => ({
                  ...prev,
                  [activeId]: {
                    ...prev[activeId]!,
                    draft: { ...draft, storyboard: next },
                  },
                }));
              }}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={activeState?.saving}
                onClick={() => void handleSaveStoryboard(draft.storyboard ?? [])}
              >
                保存分镜草稿
              </Button>
              <Button
                type="button"
                disabled={activeState?.saving}
                onClick={() => void handleApproveStoryboard()}
              >
                批准分镜并开始生成视频
              </Button>
            </div>
          </div>
        )}

        {!masterReview && !storyboardReview && !activeState?.loading && (
          <p className="text-sm text-muted-foreground">
            当前变体不在审核暂停点；可在进度面板查看任务状态。
          </p>
        )}
      </CardContent>
    </Card>
  );
}
