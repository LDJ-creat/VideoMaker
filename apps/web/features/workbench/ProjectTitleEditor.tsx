"use client";

import { Check, Pencil, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateProject } from "@/lib/apiClient";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

type ProjectTitleEditorProps = {
  projectId: string;
  name: string | null;
  onNameChange: (name: string) => void;
  onError?: (message: string) => void;
  className?: string;
};

export function ProjectTitleEditor({
  projectId,
  name,
  onNameChange,
  onError,
  className,
}: ProjectTitleEditorProps) {
  const displayName = name?.trim() || "项目工作台";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(displayName);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) {
      setDraft(displayName);
    }
  }, [displayName, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const cancelEdit = useCallback(() => {
    setDraft(displayName);
    setEditing(false);
  }, [displayName]);

  const saveName = useCallback(async () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      onError?.("项目名称不能为空。");
      return;
    }
    if (trimmed === displayName) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      const { data } = await updateProject(projectId, { name: trimmed });
      onNameChange(data.name);
      setEditing(false);
    } catch (error) {
      onError?.(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }, [draft, displayName, onError, onNameChange, projectId]);

  if (editing) {
    return (
      <div
        className={cn(
          "flex max-w-xl items-center gap-2",
          className,
        )}
      >
        <Input
          ref={inputRef}
          value={draft}
          maxLength={128}
          disabled={saving}
          aria-label="项目名称"
          className="h-9 min-w-0 flex-1 font-serif text-xl font-semibold"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void saveName();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              cancelEdit();
            }
          }}
        />
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-8 w-8"
            disabled={saving}
            aria-label="保存项目名称"
            onClick={() => void saveName()}
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            disabled={saving}
            aria-label="取消编辑项目名称"
            onClick={cancelEdit}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <h1 className="font-serif text-2xl font-semibold tracking-tight">
        {displayName}
      </h1>
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="h-8 w-8 shrink-0 text-muted-foreground"
        aria-label="编辑项目名称"
        onClick={() => setEditing(true)}
      >
        <Pencil className="h-4 w-4" />
      </Button>
    </div>
  );
}
