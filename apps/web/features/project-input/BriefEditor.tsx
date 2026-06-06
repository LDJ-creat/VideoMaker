"use client";

import type { ContentCategory } from "@videomaker/contracts";
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
import { Textarea } from "@/components/ui/textarea";
import type { UserBriefRequest } from "@/lib/apiClient";
import { saveBrief } from "@/lib/apiClient";
import {
  briefFieldLabels,
  CONTENT_CATEGORY_OPTIONS,
  defaultContentCategory,
} from "@/lib/briefFieldLabels";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function linesFromList(values: string[] | undefined): string {
  return (values ?? []).join("\n");
}

export type BriefEditorHandle = {
  getBrief: () => UserBriefRequest;
};

type BriefEditorProps = {
  projectId: string;
  initialBrief?: UserBriefRequest | null;
  embedded?: boolean;
  showSaveButton?: boolean;
  onSaved?: (brief: UserBriefRequest) => void;
  getDurationTarget?: () => UserBriefRequest["durationTarget"];
};

export const BriefEditor = forwardRef<BriefEditorHandle, BriefEditorProps>(
  function BriefEditor(
    {
      projectId,
      initialBrief,
      embedded = false,
      showSaveButton = true,
      onSaved,
      getDurationTarget,
    },
    ref,
  ) {
    const [contentCategory, setContentCategory] = useState<ContentCategory>("general");
    const [topic, setTopic] = useState("");
    const [creativeGoal, setCreativeGoal] = useState("");
    const [subjectName, setSubjectName] = useState("");
    const [keyPoints, setKeyPoints] = useState("");
    const [targetAudience, setTargetAudience] = useState("");
    const [tone, setTone] = useState("");
    const [mustMention, setMustMention] = useState("");
    const [avoidMention, setAvoidMention] = useState("");
    const [supplementalNotes, setSupplementalNotes] = useState("");
    const [status, setStatus] = useState<string | null>(null);

    useEffect(() => {
      if (initialBrief === undefined) return;
      setContentCategory(defaultContentCategory(initialBrief));
      setTopic(initialBrief?.topic ?? "");
      setCreativeGoal(initialBrief?.creativeGoal ?? "");
      setSubjectName(
        initialBrief?.subjectName ?? initialBrief?.productName ?? "",
      );
      setKeyPoints(
        linesFromList(initialBrief?.keyPoints ?? initialBrief?.sellingPoints),
      );
      setTargetAudience(initialBrief?.targetAudience ?? "");
      setTone(initialBrief?.tone ?? "");
      setMustMention(linesFromList(initialBrief?.mustMention));
      setAvoidMention(linesFromList(initialBrief?.avoidMention));
      setSupplementalNotes(initialBrief?.supplementalNotes ?? "");
    }, [initialBrief]);

    const labels = useMemo(
      () => briefFieldLabels(contentCategory),
      [contentCategory],
    );

    const categoryDescription = useMemo(
      () =>
        CONTENT_CATEGORY_OPTIONS.find((item) => item.value === contentCategory)
          ?.description,
      [contentCategory],
    );

    const buildBrief = (): UserBriefRequest => {
      const points = splitLines(keyPoints);
      const brief: UserBriefRequest = {
        contentCategory,
        sellingPoints: points,
        mustMention: splitLines(mustMention),
        avoidMention: splitLines(avoidMention),
      };
      if (topic.trim()) brief.topic = topic.trim();
      if (creativeGoal.trim()) brief.creativeGoal = creativeGoal.trim();
      if (subjectName.trim()) {
        brief.subjectName = subjectName.trim();
        brief.productName = subjectName.trim();
      }
      if (points.length) brief.keyPoints = points;
      if (targetAudience.trim()) brief.targetAudience = targetAudience.trim();
      if (tone.trim()) brief.tone = tone.trim();
      if (supplementalNotes.trim()) {
        brief.supplementalNotes = supplementalNotes.trim();
      }
      const durationTarget = getDurationTarget?.();
      if (durationTarget) {
        brief.durationTarget = durationTarget;
      }
      return brief;
    };

    useImperativeHandle(ref, () => ({ getBrief: buildBrief }), [
      contentCategory,
      topic,
      creativeGoal,
      subjectName,
      keyPoints,
      targetAudience,
      tone,
      mustMention,
      avoidMention,
      supplementalNotes,
      getDurationTarget,
    ]);

    const handleSave = async () => {
      const brief = buildBrief();
      setStatus(null);
      try {
        await saveBrief(projectId, brief);
        setStatus("Brief 已保存");
        onSaved?.(brief);
      } catch (err) {
        setStatus(getErrorMessage(err));
      }
    };

    const form = (
      <div className="grid gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2 lg:col-span-2">
            <Label htmlFor="brief-category">内容类型</Label>
            <select
              id="brief-category"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:max-w-md"
              value={contentCategory}
              onChange={(event) =>
                setContentCategory(event.target.value as ContentCategory)
              }
            >
              {CONTENT_CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {categoryDescription ? (
              <p className="text-xs text-muted-foreground">{categoryDescription}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="brief-topic">主题</Label>
            <Input
              id="brief-topic"
              value={topic}
              placeholder={labels.topicPlaceholder}
              onChange={(e) => setTopic(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="brief-goal">创作目标</Label>
            <Input
              id="brief-goal"
              value={creativeGoal}
              placeholder={labels.creativeGoalPlaceholder}
              onChange={(e) => setCreativeGoal(e.target.value)}
            />
          </div>
          <div className="space-y-2 lg:col-span-2">
            <Label htmlFor="brief-key-points">{labels.keyPoints}</Label>
            <Textarea
              id="brief-key-points"
              value={keyPoints}
              rows={4}
              onChange={(e) => setKeyPoints(e.target.value)}
            />
          </div>
        </div>

        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            受众与语气（可选）
          </summary>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="brief-subject">{labels.subjectName}</Label>
              <Input
                id="brief-subject"
                value={subjectName}
                onChange={(e) => setSubjectName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="brief-audience">目标受众</Label>
              <Input
                id="brief-audience"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="brief-tone">语气</Label>
              <Input
                id="brief-tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="brief-notes">补充说明</Label>
              <Textarea
                id="brief-notes"
                value={supplementalNotes}
                maxLength={500}
                placeholder="可选：补充背景、素材使用说明、禁忌场景等"
                onChange={(e) => setSupplementalNotes(e.target.value)}
              />
            </div>
          </div>
        </details>

        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            高级约束（必须 / 禁止提及）
          </summary>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="brief-must">必须提及（每行一条）</Label>
              <Textarea
                id="brief-must"
                value={mustMention}
                onChange={(e) => setMustMention(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="brief-avoid">禁止提及（每行一条）</Label>
              <Textarea
                id="brief-avoid"
                value={avoidMention}
                onChange={(e) => setAvoidMention(e.target.value)}
              />
            </div>
          </div>
        </details>

        {showSaveButton ? (
          <div className="flex items-center gap-3">
            <Button type="button" onClick={() => void handleSave()}>
              保存 Brief
            </Button>
            {status && (
              <p className="text-sm text-muted-foreground" role="status">
                {status}
              </p>
            )}
          </div>
        ) : null}
      </div>
    );

    if (embedded) {
      return form;
    }

    return (
      <div className={cn("space-y-4 rounded-2xl border bg-card p-6 shadow-sm")}>
        <div>
          <h3 className="font-serif text-lg font-semibold">创作 Brief</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            描述创作意图与约束；上传素材后，系统会结合样例结构统一理解
          </p>
        </div>
        {form}
      </div>
    );
  },
);
