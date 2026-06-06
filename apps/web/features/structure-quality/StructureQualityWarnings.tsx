"use client";

import type { AnalysisQuality } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import {
  formatStructureQualityWarnings,
  hasCriticalStructureQualityWarnings,
  structureQualitySeverityLabel,
} from "@/lib/structureQualityWarningLabels";
import { cn } from "@/lib/utils";

type StructureQualityWarningsProps = {
  analysisQuality?: AnalysisQuality;
};

export function StructureQualityWarnings({
  analysisQuality,
}: StructureQualityWarningsProps) {
  const rawWarnings = analysisQuality?.warnings ?? [];
  const warnings = formatStructureQualityWarnings(rawWarnings);
  const promoteReady = analysisQuality?.promoteReady === true;
  const hasCritical = hasCriticalStructureQualityWarnings(rawWarnings);

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
        <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
          结构质量提示
        </p>
        {analysisQuality?.promoteReady != null ? (
          <Badge
            variant={promoteReady ? "default" : "secondary"}
            data-testid="structure-promote-ready-badge"
          >
            {promoteReady ? "可入库" : "暂不可入库"}
          </Badge>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        以下为系统自动校验结果，用于判断结构是否适合迁移与入库，并非播放或渲染错误。
      </p>
      {warnings.length > 0 ? (
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
      ) : promoteReady ? (
        <p className="text-xs text-muted-foreground">
          未检测到质量警告，结构满足入库门槛。
        </p>
      ) : null}
      {hasCritical ? (
        <p className="text-xs text-destructive/90">
          存在「严重」提示时，暂无法将该样例加入知识库；可尝试重新分析或调整模型输出后再入库。
        </p>
      ) : null}
    </div>
  );
}
