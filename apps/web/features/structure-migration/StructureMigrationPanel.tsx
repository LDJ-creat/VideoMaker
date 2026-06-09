"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

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
import type { SlotMigrationRow } from "@/features/structure-migration/buildSlotMigrationRows";
import { migrationSummaryFromRows } from "@/features/structure-migration/buildSlotMigrationRows";
import { cn } from "@/lib/utils";

const STATUS_LABELS: Record<SlotMigrationRow["status"], string> = {
  pending: "等待映射",
  mapping: "匹配中",
  planned: "已规划补全",
  completing: "补全中",
  resolved: "已落地",
};

const STATUS_VARIANT: Record<
  SlotMigrationRow["status"],
  "outline" | "secondary" | "ai" | "success" | "warning"
> = {
  pending: "outline",
  mapping: "secondary",
  planned: "warning",
  completing: "ai",
  resolved: "success",
};

type StructureMigrationPanelProps = {
  rows: SlotMigrationRow[];
  title?: string;
  description?: string;
  defaultExpanded?: boolean;
  collapsible?: boolean;
  compact?: boolean;
  "data-testid"?: string;
};

export function StructureMigrationPanel({
  rows,
  title = "结构迁移说明",
  description,
  defaultExpanded = true,
  collapsible = true,
  compact = false,
  "data-testid": testId = "structure-migration-panel",
}: StructureMigrationPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const summary = description ?? migrationSummaryFromRows(rows);

  return (
    <Card data-testid={testId}>
      <CardHeader className={cn(compact && "space-y-2 pb-3")}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className={cn(compact && "text-base")}>{title}</CardTitle>
            <CardDescription>{summary}</CardDescription>
          </div>
          {collapsible ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 px-2"
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? (
                <ChevronDown className="mr-1 h-4 w-4" />
              ) : (
                <ChevronRight className="mr-1 h-4 w-4" />
              )}
              {expanded ? "收起" : "展开"}
            </Button>
          ) : null}
        </div>
      </CardHeader>

      {(!collapsible || expanded) && (
        <CardContent className={cn("space-y-3", compact && "pt-0")}>
          {rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无结构槽位数据。</p>
          ) : (
            rows.map((row, index) => (
              <SlotMigrationRowCard key={row.slotId} row={row} index={index} />
            ))
          )}
        </CardContent>
      )}
    </Card>
  );
}

function SlotMigrationRowCard({
  row,
  index,
}: {
  row: SlotMigrationRow;
  index: number;
}) {
  return (
    <article
      className="rounded-lg border border-border/80 bg-card/40 p-4"
      data-testid={`slot-migration-row-${row.slotId}`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">#{index + 1}</Badge>
          <Badge variant="outline">{row.roleLabel}</Badge>
          <span className="font-mono text-xs text-muted-foreground">{row.slotId}</span>
        </div>
        <Badge variant={STATUS_VARIANT[row.status]}>{STATUS_LABELS[row.status]}</Badge>
      </div>

      <dl className="grid gap-3 text-sm">
        <MigrationStep label="结构意图" value={row.visualIntent} hint={row.scriptIntent} />
        <MigrationStep
          label="用户素材"
          value={
            row.userAssetId
              ? `复用 ${row.userAssetId}`
              : row.userAssetSummary
                ? row.userAssetSummary
                : "未匹配到可用素材"
          }
          hint={
            row.userAssetId && row.userAssetSummary ? row.userAssetSummary : undefined
          }
        />
        {(row.gapSummary || row.completionProvider) && (
          <MigrationStep
            label="视觉补全"
            value={row.completionReason ?? row.gapSummary ?? "按结构要求自动补全"}
            accessory={
              row.completionProvider &&
              row.completionProvider !== "tts" ? (
                <GeneratedAssetBadge provider={row.completionProvider} />
              ) : null
            }
          />
        )}
        {(row.resolvedVisual || row.script) && (
          <MigrationStep
            label="成片落地"
            value={row.resolvedVisual ?? "—"}
            hint={row.script ?? undefined}
            meta={row.timeRange ?? undefined}
          />
        )}
      </dl>
    </article>
  );
}

function MigrationStep({
  label,
  value,
  hint,
  meta,
  accessory,
}: {
  label: string;
  value: string;
  hint?: string;
  meta?: string;
  accessory?: React.ReactNode;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[88px_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-foreground">{value}</p>
          {accessory}
          {meta ? (
            <span className="font-mono text-xs text-muted-foreground">{meta}</span>
          ) : null}
        </div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </dd>
    </div>
  );
}
