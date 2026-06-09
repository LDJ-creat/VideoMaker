"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { KnowledgeCategoryDetail, KnowledgeCategoryEntryCard } from "@/lib/apiClient";
import { cn } from "@/lib/utils";

import { SelectedEntryChip } from "./TemplateEntryCard";

export type TemplateSelectionDockProps = {
  detail: KnowledgeCategoryDetail;
  entriesById: Map<string, KnowledgeCategoryEntryCard>;
  primaryEntryId: string | null;
  referenceEntryIds: string[];
  projectName: string;
  creating: boolean;
  createError: string | null;
  onProjectNameChange: (value: string) => void;
  onRemovePrimary: () => void;
  onRemoveReference: (entryId: string) => void;
  onCreate: () => void;
  className?: string;
  testId?: string;
};

function SelectionSlot({
  label,
  entry,
  onRemove,
}: {
  label: string;
  entry: KnowledgeCategoryEntryCard | null;
  onRemove?: () => void;
}) {
  if (!entry) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/30 px-3 py-4 text-center text-xs text-muted-foreground">
        {label} · 未选择
      </div>
    );
  }

  return <SelectedEntryChip entry={entry} label={label} onRemove={onRemove} />;
}

export function TemplateSelectionDock({
  detail,
  entriesById,
  primaryEntryId,
  referenceEntryIds,
  projectName,
  creating,
  createError,
  onProjectNameChange,
  onRemovePrimary,
  onRemoveReference,
  onCreate,
  className,
  testId = "template-selection-dock",
}: TemplateSelectionDockProps) {
  const primaryEntry = primaryEntryId ? entriesById.get(primaryEntryId) ?? null : null;
  const referenceEntries = referenceEntryIds
    .map((entryId) => entriesById.get(entryId))
    .filter((entry): entry is KnowledgeCategoryEntryCard => Boolean(entry));

  const canCreate = Boolean(primaryEntryId && projectName.trim() && !creating);

  return (
    <aside
      className={cn(
        "space-y-5 rounded-2xl border border-border bg-card p-5 shadow-sm lg:sticky lg:top-28",
        className,
      )}
      data-testid={testId}
    >
      <div className="space-y-1">
        <h2 className="font-serif text-lg font-semibold">当前选用</h2>
        <p className="text-xs leading-relaxed text-muted-foreground">
          选择 1 个主样例作为结构基准，最多再添加 2 个参考样例用于多源合成。
        </p>
      </div>

      <div className="space-y-3" aria-live="polite">
        <SelectionSlot
          label="主样例"
          entry={primaryEntry}
          onRemove={primaryEntry ? onRemovePrimary : undefined}
        />
        {[0, 1].map((index) => (
          <SelectionSlot
            key={`reference-${index}`}
            label={`参考 ${index + 1}`}
            entry={referenceEntries[index] ?? null}
            onRemove={
              referenceEntries[index]
                ? () => onRemoveReference(referenceEntries[index]!.entryId)
                : undefined
            }
          />
        ))}
      </div>

      <div className="space-y-2">
        <Label htmlFor="template-project-name">项目名称</Label>
        <Input
          id="template-project-name"
          value={projectName}
          onChange={(event) => onProjectNameChange(event.target.value)}
          placeholder={`${detail.category} · 新项目`}
        />
      </div>

      <div className="space-y-2">
        <Button
          type="button"
          className="w-full"
          disabled={!canCreate}
          onClick={onCreate}
          data-testid="template-create-project-button"
        >
          {creating ? "创建中…" : "用所选模板创建项目"}
        </Button>
        <p className="text-xs text-muted-foreground">
          创建后将进入工作台，可在那里上传素材并填写 Brief。
        </p>
        {createError ? (
          <p className="text-sm text-destructive" role="alert">
            {createError}
          </p>
        ) : null}
      </div>
    </aside>
  );
}
