"use client";

import { Loader2 } from "lucide-react";

type KnowledgeRefreshStatusProps = {
  label: string;
};

export function KnowledgeRefreshStatus({ label }: KnowledgeRefreshStatusProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2.5 rounded-lg border border-primary/40 bg-primary/10 px-3.5 py-2.5 shadow-sm ring-1 ring-primary/15"
    >
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden />
      <span className="text-sm font-medium text-primary">{label}</span>
    </div>
  );
}
