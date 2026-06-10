"use client";

import { CheckCircle2 } from "lucide-react";
import { useEffect } from "react";

type WorkbenchToastProps = {
  message: string | null;
  onDismiss: () => void;
  durationMs?: number;
};

export function WorkbenchToast({
  message,
  onDismiss,
  durationMs = 2600,
}: WorkbenchToastProps) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [message, durationMs, onDismiss]);

  if (!message) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-700 shadow-lg backdrop-blur-sm dark:text-emerald-300"
    >
      <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}
