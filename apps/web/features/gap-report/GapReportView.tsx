"use client";

import type { CompletionAction, GapReport } from "@videomaker/contracts";
import { Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GeneratedAssetBadge } from "@/features/aigc-preview/GeneratedAssetBadge";

type GapReportViewProps = {
  report: GapReport;
  completionActions?: CompletionAction[];
  onUploadAsset?: (slotId: string) => void;
  onGenerate?: (slotId: string) => void;
};

export function GapReportView({
  report,
  completionActions = [],
  onUploadAsset,
  onGenerate,
}: GapReportViewProps) {
  const actionsBySlot = new Map(
    completionActions.map((action) => [action.slotId, action]),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>缺口报告</CardTitle>
        <CardDescription>{report.summary}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <section>
          <h3 className="mb-2 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
            已匹配
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {report.slotMatches.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无匹配槽位</p>
            )}
            {report.slotMatches.map((match) => (
              <GapCard
                key={match.slotId}
                slotId={match.slotId}
                tone="matched"
                title={`槽位 ${match.slotId}`}
                body={match.matchReason}
                meta={`得分 ${(match.matchScore * 100).toFixed(0)}%`}
              />
            ))}
          </div>
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold text-amber-600 dark:text-amber-400">
            弱匹配
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {report.weakSlots.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无弱匹配槽位</p>
            )}
            {report.weakSlots.map((slot) => (
              <GapCard
                key={slot.slotId}
                slotId={slot.slotId}
                tone="weak"
                title={`槽位 ${slot.slotId}`}
                body={slot.reason}
                meta={`影响 ${slot.impact}`}
                suggestedProviders={slot.suggestedFixes}
                completionAction={actionsBySlot.get(slot.slotId)}
                onUploadAsset={onUploadAsset}
                onGenerate={onGenerate}
              />
            ))}
          </div>
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold text-red-600 dark:text-red-400">
            缺失
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {report.missingSlots.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无缺失槽位</p>
            )}
            {report.missingSlots.map((slot) => (
              <GapCard
                key={slot.slotId}
                slotId={slot.slotId}
                tone="missing"
                title={`槽位 ${slot.slotId}`}
                body={slot.reason}
                meta={slot.suggestedFixes.join(", ")}
                suggestedProviders={slot.suggestedFixes}
                completionAction={actionsBySlot.get(slot.slotId)}
                onUploadAsset={onUploadAsset}
                onGenerate={onGenerate}
                showActions
              />
            ))}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}

function GapCard({
  slotId,
  tone,
  title,
  body,
  meta,
  suggestedProviders,
  completionAction,
  showActions,
  onUploadAsset,
  onGenerate,
}: {
  slotId: string;
  tone: "matched" | "weak" | "missing";
  title: string;
  body: string;
  meta: string;
  suggestedProviders?: string[];
  completionAction?: CompletionAction;
  showActions?: boolean;
  onUploadAsset?: (slotId: string) => void;
  onGenerate?: (slotId: string) => void;
}) {
  const border =
    tone === "matched"
      ? "border-emerald-500/30"
      : tone === "weak"
        ? "border-amber-500/30"
        : "border-red-500/30";

  return (
    <div className={`rounded-lg border p-4 ${border}`}>
      <div className="mb-2 flex items-center justify-between">
        <p className="font-medium">{title}</p>
        <Badge
          variant={
            tone === "matched"
              ? "success"
              : tone === "weak"
                ? "warning"
                : "destructive"
          }
        >
          {tone === "matched"
            ? "Matched"
            : tone === "weak"
              ? "Weak"
              : "Missing"}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">{body}</p>
      <p className="mt-2 font-mono text-xs text-muted-foreground">{meta}</p>
      {(completionAction?.provider || (suggestedProviders?.length ?? 0) > 0) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {completionAction?.provider && (
            <GeneratedAssetBadge
              provider={completionAction.provider}
              generatedBy={{
                provider: completionAction.provider,
                template: completionAction.strategy,
              }}
            />
          )}
          {suggestedProviders
            ?.filter((provider) => provider !== completionAction?.provider)
            .map((provider) => (
              <GeneratedAssetBadge key={provider} provider={provider} />
            ))}
        </div>
      )}
      {(showActions || tone !== "matched") && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => onUploadAsset?.(slotId)}
          >
            <Upload className="h-3 w-3" />
            上传素材
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => onGenerate?.(slotId)}
          >
            生成补全
          </Button>
        </div>
      )}
    </div>
  );
}
