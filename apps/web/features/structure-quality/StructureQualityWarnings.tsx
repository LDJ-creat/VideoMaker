"use client";

import { useState } from "react";

import type { AnalysisQuality } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatStructureQualityWarnings,
  hasCriticalStructureQualityWarnings,
  structureQualitySeverityLabel,
  summarizeStructureQuality,
} from "@/lib/structureQualityWarningLabels";
import { cn } from "@/lib/utils";

type StructureQualityWarningsProps = {
  analysisQuality?: AnalysisQuality;
};

function WarningList({
  warnings,
}: {
  warnings: ReturnType<typeof formatStructureQualityWarnings>;
}) {
  return (
    <ul className="space-y-2 text-sm">
      {warnings.map((warning) => (
        <li key={warning.raw} className="flex items-start gap-2">
          <Badge
            variant={
              warning.severity === "critical"
                ? "destructive"
                : warning.severity === "info"
                  ? "outline"
                  : "secondary"
            }
            className="mt-0.5 shrink-0"
          >
            {structureQualitySeverityLabel(warning.severity)}
          </Badge>
          <div className="min-w-0 space-y-0.5 text-muted-foreground">
            <p className="text-foreground">{warning.message}</p>
            {warning.hint ? <p className="text-xs">{warning.hint}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function StructureQualityWarnings({
  analysisQuality,
}: StructureQualityWarningsProps) {
  const [expanded, setExpanded] = useState(false);
  const rawWarnings = analysisQuality?.warnings ?? [];
  const warnings = formatStructureQualityWarnings(rawWarnings);
  const criticalWarnings = warnings.filter((item) => item.severity === "critical");
  const advisoryWarnings = warnings.filter((item) => item.severity !== "critical");
  const promoteReady = analysisQuality?.promoteReady === true;
  const hasCritical = hasCriticalStructureQualityWarnings(rawWarnings);
  const summary = summarizeStructureQuality(analysisQuality);

  if (warnings.length === 0 && analysisQuality?.promoteReady == null) {
    return null;
  }

  return (
    <div
      className={cn(
        "space-y-2 rounded-lg border p-3",
        hasCritical
          ? "border-amber-500/30 bg-amber-500/5"
          : promoteReady
            ? "border-emerald-500/30 bg-emerald-500/5"
            : "border-amber-500/30 bg-amber-500/5",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-foreground">结构与入库</p>
        {analysisQuality?.promoteReady != null ? (
          <Badge
            variant={promoteReady ? "default" : "secondary"}
            data-testid="structure-promote-ready-badge"
          >
            {promoteReady ? "可入库" : "暂不可入库"}
          </Badge>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">{summary}</p>

      {criticalWarnings.length > 0 ? (
        <WarningList warnings={criticalWarnings} />
      ) : null}

      {advisoryWarnings.length > 0 ? (
        <div className="space-y-2">
          {!expanded ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setExpanded(true)}
              data-testid="structure-quality-expand"
            >
              查看 {advisoryWarnings.length} 条优化建议
            </Button>
          ) : (
            <>
              <WarningList warnings={advisoryWarnings} />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-auto px-0 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => setExpanded(false)}
              >
                收起详情
              </Button>
            </>
          )}
        </div>
      ) : null}

      {hasCritical ? (
        <p className="text-xs text-destructive/90">
          请先处理「严重」提示后再加入知识库，或尝试重新分析。
        </p>
      ) : null}
    </div>
  );
}
