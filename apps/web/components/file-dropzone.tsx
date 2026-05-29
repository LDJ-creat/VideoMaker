"use client";

import { Upload } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

type FileDropzoneProps = {
  accept: string;
  multiple?: boolean;
  disabled?: boolean;
  title: string;
  hint: string;
  className?: string;
  onFiles: (files: File[]) => void;
};

export function FileDropzone({
  accept,
  multiple = false,
  disabled = false,
  title,
  hint,
  className,
  onFiles,
}: FileDropzoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFiles = useCallback(
    (fileList: FileList | null | undefined) => {
      if (!fileList?.length || disabled) return;
      onFiles(Array.from(fileList));
    },
    [disabled, onFiles],
  );

  return (
    <div className={className}>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        className="sr-only"
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />
      <label
        htmlFor={inputId}
        onDragEnter={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!disabled) setDragActive(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (!disabled) setDragActive(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
            return;
          }
          setDragActive(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setDragActive(false);
          if (disabled) return;
          handleFiles(event.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition-colors",
          dragActive
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/20 hover:border-primary/50 hover:bg-muted/40",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <Upload className="h-8 w-8 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">{title}</span>
        <span className="max-w-sm text-xs text-muted-foreground">{hint}</span>
      </label>
    </div>
  );
}
