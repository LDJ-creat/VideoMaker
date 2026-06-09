"use client";

import { useEffect, useRef, useState } from "react";

import { ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";

import { TemplateSelectionDock, type TemplateSelectionDockProps } from "./TemplateSelectionDock";

type TemplateSelectionSheetProps = Omit<TemplateSelectionDockProps, "className">;

export function TemplateSelectionSheet(props: TemplateSelectionSheetProps) {
  const { primaryEntryId, referenceEntryIds, projectName, creating } = props;
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const selectedCount = (primaryEntryId ? 1 : 0) + referenceEntryIds.length;
  const canCreate = Boolean(primaryEntryId && projectName.trim() && !creating);

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
    const handleClose = () => setOpen(false);
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, []);

  return (
    <>
      <div
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 p-4 shadow-lg backdrop-blur lg:hidden"
        data-testid="template-selection-sheet-bar"
      >
        <div className="mx-auto flex max-w-lg items-center gap-3">
          <button
            type="button"
            className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left"
            onClick={() => setOpen(true)}
          >
            <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-sm">
              已选 {selectedCount} 条
              {primaryEntryId ? "" : " · 请选择主样例"}
            </span>
          </button>
          <Button
            type="button"
            size="sm"
            disabled={!canCreate}
            onClick={() => (canCreate ? props.onCreate() : setOpen(true))}
            data-testid="template-create-project-bar-button"
          >
            {creating ? "创建中…" : "创建项目"}
          </Button>
        </div>
      </div>

      <dialog
        ref={dialogRef}
        className="fixed inset-x-0 bottom-0 z-50 m-0 max-h-[85vh] w-full max-w-none rounded-t-2xl border border-border bg-background p-0 shadow-xl backdrop:bg-black/40 open:flex open:flex-col lg:hidden"
        aria-label="模板选用与创建"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="font-serif text-base font-semibold">选用与创建</p>
          <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
            关闭
          </Button>
        </div>
        <div className="overflow-y-auto p-4 pb-8">
          <TemplateSelectionDock {...props} className="border-0 p-0 shadow-none lg:static" testId="template-selection-dock-mobile" />
        </div>
      </dialog>
    </>
  );
}
