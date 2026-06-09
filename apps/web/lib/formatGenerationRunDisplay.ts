import { format, formatDistanceToNow, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";

import {
  generationRunStatusLabel,
  generationStatusLabel,
} from "@/lib/generationRunLabels";
import { getVariantLabel } from "@/lib/variantRegistry";

export function parseApiTimestamp(value: string): Date | null {
  const parsed = parseISO(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** e.g. 2026年6月7日 19:52 */
export function formatGenerationRunDateTime(createdAt: string): string {
  const date = parseApiTimestamp(createdAt);
  if (!date) return "未知时间";
  return format(date, "yyyy年M月d日 HH:mm", { locale: zhCN });
}

/** e.g. 3 天前 */
export function formatGenerationRunRelative(createdAt: string): string {
  const date = parseApiTimestamp(createdAt);
  if (!date) return "";
  return formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
}

export function formatShortRunId(runId: string): string {
  const tail = runId.split("-").pop() ?? runId;
  if (tail.length <= 8) return `…${tail}`;
  return `…${tail.slice(-8)}`;
}

/** Newest run in list gets batch number = total. */
export function formatGenerationRunBatchNumber(
  index: number,
  total: number,
): number {
  return Math.max(1, total - index);
}

export function formatGenerationRunTitle(
  createdAt: string,
  index: number,
  total: number,
): string {
  const batch = formatGenerationRunBatchNumber(index, total);
  const when = formatGenerationRunDateTime(createdAt);
  if (index === 0 && total > 1) {
    return `最近生成（批次 ${batch}）· ${when}`;
  }
  return `批次 ${batch} · ${when}`;
}

export type RunVariantSummaryEntry = {
  variant?: string;
  status?: string;
};

export function summarizeRunVariants(
  entries: RunVariantSummaryEntry[],
): string {
  if (entries.length === 0) return "";

  return entries
    .map((entry) => {
      const variantId = entry.variant ?? "default";
      const variantLabel = getVariantLabel(variantId);
      const statusLabel = entry.status
        ? generationStatusLabel(entry.status)
        : "未知";
      return `${variantLabel}${statusLabel.replace(/^生成/, "")}`;
    })
    .join("、");
}

export function formatGenerationRunMetaLine(
  createdAt: string,
  runStatus: string,
  variantEntries: RunVariantSummaryEntry[],
): string {
  const parts: string[] = [];
  const relative = formatGenerationRunRelative(createdAt);
  if (relative) parts.push(relative);
  parts.push(generationRunStatusLabel(runStatus));
  const variantSummary = summarizeRunVariants(variantEntries);
  if (variantSummary) parts.push(variantSummary);
  return parts.join(" · ");
}
