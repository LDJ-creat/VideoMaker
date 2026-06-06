"use client";

import { useEffect, useRef } from "react";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { sampleDisplayName } from "@/features/project-input/SampleVideoCard";
import type { ActiveSampleSummary } from "@/lib/apiClient";

type SamplePreviewDialogProps = {
  sample: ActiveSampleSummary | null;
  open: boolean;
  onClose: () => void;
};

export function SamplePreviewDialog({
  sample,
  open,
  onClose,
}: SamplePreviewDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => onClose();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, [onClose]);

  if (!sample) return null;

  const title = sampleDisplayName(sample);

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto max-h-[90vh] w-full max-w-lg rounded-2xl border border-border bg-background p-0 shadow-xl backdrop:bg-black/60 open:flex open:flex-col"
      aria-label={`预览 ${title}`}
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <p className="truncate text-sm font-medium">{title}</p>
        <Button type="button" size="icon" variant="ghost" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="p-4">
        {sample.previewUrl ? (
          <video
            src={sample.previewUrl}
            controls
            playsInline
            className="mx-auto max-h-[70vh] w-full rounded-lg bg-black"
          />
        ) : (
          <p className="py-12 text-center text-sm text-muted-foreground">
            暂无可预览视频
          </p>
        )}
      </div>
    </dialog>
  );
}
