"use client";

import type { AnalysisQuality } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";

type StructureQualityWarningsProps = {
  analysisQuality?: AnalysisQuality;
};

export function StructureQualityWarnings({
  analysisQuality,
}: StructureQualityWarningsProps) {
  const warnings = analysisQuality?.warnings ?? [];
  if (warnings.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
      <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
        结构质量提示
      </p>
      <ul className="space-y-1 text-sm text-muted-foreground">
        {warnings.map((warning) => {
          const critical = warning.startsWith("critical:");
          return (
            <li key={warning} className="flex items-start gap-2">
              <Badge variant={critical ? "destructive" : "secondary"}>
                {critical ? "critical" : "warn"}
              </Badge>
              <span>{warning.replace(/^critical:\s*/, "")}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
