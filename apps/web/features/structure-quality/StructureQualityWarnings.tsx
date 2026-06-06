"use client";

import type { AnalysisQuality } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  formatStructureQualityWarnings,
  hasCriticalStructureQualityWarnings,
  structureQualitySeverityLabel,
} from "@/lib/structureQualityWarningLabels";

type StructureQualityWarningsProps = {
  analysisQuality?: AnalysisQuality;
};

export function StructureQualityWarnings({
  analysisQuality,
}: StructureQualityWarningsProps) {
  const rawWarnings = analysisQuality?.warnings ?? [];
  const warnings = formatStructureQualityWarnings(rawWarnings);
  if (warnings.length === 0) {
    return null;
  }

  const hasCritical = hasCriticalStructureQualityWarnings(rawWarnings);

  return (
    <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
      <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
        结构质量提示
      </p>
      <p className="text-xs text-muted-foreground">
        以下为系统自动校验结果，用于判断结构是否适合迁移与入库，并非播放或渲染错误。
      </p>
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
              {warning.hint ? (
                <p className="text-xs">{warning.hint}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {hasCritical ? (
        <p className="text-xs text-destructive/90">
          存在「严重」提示时，暂无法将该样例加入知识库；可尝试重新分析或调整模型输出后再入库。
        </p>
      ) : null}
    </div>
  );
}
