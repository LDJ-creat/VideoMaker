"use client";

import { Badge } from "@/components/ui/badge";
import { isDuplicateText } from "@/lib/keyframePreview";
import { narrativeRoleLabel } from "@/lib/narrativeRoleLabels";
import { cn } from "@/lib/utils";

import type { SegmentEvidenceView } from "./StructureEvidencePanel";

type EvidenceCardProps = {
  view: SegmentEvidenceView;
  mode?: "compact" | "detail";
  highlighted?: boolean;
  onSelect?: () => void;
};

function isTimeRangeSummary(text: string): boolean {
  const trimmed = text.trim();
  return /^\d+(\.\d+)?\s*[-–]\s*\d+(\.\d+)?(\s*sec)?$/i.test(trimmed);
}

export function EvidenceCard({
  view,
  mode = "detail",
  highlighted,
  onSelect,
}: EvidenceCardProps) {
  const {
    segment,
    transcriptExcerpt: evidenceTranscript,
    ocrExcerpts,
    audioSummary,
    shotRanges,
  } = view;
  const roleLabel = narrativeRoleLabel(segment.role);
  const showIntent =
    segment.intent.trim().length > 0 &&
    !isDuplicateText(segment.role, segment.intent) &&
    !isDuplicateText(roleLabel, segment.intent);
  const showScriptSummary =
    segment.scriptSummary.trim().length > 0 &&
    !isDuplicateText(segment.visualSummary, segment.scriptSummary);
  const transcriptExcerpt = segment.transcriptExcerpt?.trim() ?? "";
  const showTranscriptExcerpt =
    transcriptExcerpt.length > 0 &&
    !isDuplicateText(segment.scriptSummary, transcriptExcerpt) &&
    !isDuplicateText(segment.visualSummary, transcriptExcerpt);
  const asrText = evidenceTranscript?.trim() ?? "";
  const showAsrEvidence =
    asrText.length > 0 &&
    !isDuplicateText(segment.scriptSummary, asrText) &&
    (transcriptExcerpt.length === 0 ||
      !isDuplicateText(transcriptExcerpt, asrText)) &&
    !isTimeRangeSummary(asrText);

  const hasEvidenceDetails =
    showAsrEvidence ||
    (ocrExcerpts?.length ?? 0) > 0 ||
    Boolean(audioSummary) ||
    shotRanges.length > 0;

  const Wrapper = mode === "compact" ? "button" : "div";
  const interactive = mode === "compact";

  return (
    <Wrapper
      type={interactive ? "button" : undefined}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      className={cn(
        "w-full rounded-lg border border-border bg-muted/20 p-4 text-left transition-colors",
        interactive && "cursor-pointer hover:bg-muted/40",
        highlighted && "border-ai/50 bg-ai/5",
      )}
      onClick={interactive ? onSelect : undefined}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect?.();
              }
            }
          : undefined
      }
      data-testid={`evidence-card-${segment.id}`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{roleLabel}</Badge>
          <span className="font-mono text-xs text-muted-foreground">
            {segment.startSec}–{segment.endSec}s
          </span>
        </div>
        {showIntent ? (
          <span className="text-xs text-muted-foreground">{segment.intent}</span>
        ) : null}
      </div>

      {mode === "compact" ? (
        <p className="line-clamp-2 text-xs text-muted-foreground">{segment.intent}</p>
      ) : null}

      {mode === "detail" ? (
        <div className="space-y-3 text-sm">
          {showScriptSummary ? (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">口播手法：</span>
              {segment.scriptSummary}
            </p>
          ) : null}
          {segment.visualSummary.trim() ? (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">画面概要：</span>
              {segment.visualSummary}
            </p>
          ) : null}
          {showTranscriptExcerpt ? (
            <p className="rounded-md border border-border/50 bg-background/40 px-3 py-2 text-muted-foreground">
              <span className="font-medium text-foreground">口播摘录：</span>
              {transcriptExcerpt}
            </p>
          ) : null}
          {segment.retentionRole ? (
            <p className="text-xs text-muted-foreground">
              留存作用：{segment.retentionRole}
            </p>
          ) : null}
          {segment.rhetoricalDevices?.length ? (
            <p className="text-xs text-muted-foreground">
              修辞：{segment.rhetoricalDevices.join("、")}
            </p>
          ) : null}
          {segment.voStyle ? (
            <p className="text-xs text-muted-foreground">
              口播风格：{segment.voStyle.persona} / {segment.voStyle.pace} /{" "}
              {segment.voStyle.energy}
            </p>
          ) : null}
          {segment.visualSpec ? (
            <p className="text-xs text-muted-foreground">
              镜头规格：{segment.visualSpec.framing} · {segment.visualSpec.cameraMove}
              {segment.visualSpec.onScreenText?.length
                ? ` · 花字：${segment.visualSpec.onScreenText.join("、")}`
                : ""}
            </p>
          ) : null}

          {hasEvidenceDetails ? (
            <details
              className="rounded-md border border-border/60 bg-background/40 px-3 py-2"
              onClick={(event) => event.stopPropagation()}
              onKeyDown={(event) => event.stopPropagation()}
            >
              <summary className="cursor-pointer text-xs font-medium text-foreground">
                核对依据
              </summary>
              <div className="mt-2 space-y-2 text-xs text-muted-foreground">
                {showAsrEvidence ? (
                  <p>
                    <span className="font-medium text-foreground">ASR 转写：</span>
                    {asrText}
                  </p>
                ) : null}
                {ocrExcerpts && ocrExcerpts.length > 0 ? (
                  <p>
                    <span className="font-medium text-foreground">屏上文字：</span>
                    {ocrExcerpts.join(" · ")}
                  </p>
                ) : null}
                {audioSummary ? (
                  <p>
                    <span className="font-medium text-foreground">音频区间：</span>
                    {audioSummary}
                  </p>
                ) : null}
                {shotRanges.length > 0 ? (
                  <p className="font-mono">
                    镜头切点：{" "}
                    {shotRanges
                      .map((shot) => `${shot.startSec}–${shot.endSec}s`)
                      .join(" · ")}
                  </p>
                ) : null}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}
    </Wrapper>
  );
}
