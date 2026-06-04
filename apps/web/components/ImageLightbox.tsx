"use client";

import { useEffect } from "react";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ImageLightboxProps = {
  src: string;
  alt: string;
  open: boolean;
  onClose: () => void;
  caption?: string;
  className?: string;
};

export function ImageLightbox({
  src,
  alt,
  open,
  onClose,
  caption,
  className,
}: ImageLightboxProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4",
        className,
      )}
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
    >
      <Button
        type="button"
        variant="secondary"
        size="icon"
        className="absolute right-4 top-4 z-10"
        onClick={onClose}
        aria-label="关闭预览"
      >
        <X className="h-4 w-4" />
      </Button>
      <figure
        className="relative flex max-h-[90vh] max-w-[min(96vw,1200px)] flex-col items-center gap-3"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="relative max-h-[80vh] w-full">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt={alt}
            className="mx-auto max-h-[80vh] w-auto max-w-full rounded-md object-contain"
          />
        </div>
        {caption ? (
          <figcaption className="max-w-2xl text-center text-sm text-muted-foreground">
            {caption}
          </figcaption>
        ) : null}
      </figure>
    </div>
  );
}
