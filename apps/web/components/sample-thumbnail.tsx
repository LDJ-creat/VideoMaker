"use client";

import { Play } from "lucide-react";

import { cn } from "@/lib/utils";

export type SampleThumbnailSize = "xs" | "sm" | "md";

const SIZE_CLASS: Record<SampleThumbnailSize, string> = {
  xs: "h-10 w-7",
  sm: "h-14 w-9",
  md: "h-[85px] w-12",
};

type SampleThumbnailProps = {
  /** Full video stream URL for preview dialog */
  previewUrl?: string | null;
  /** Sharp keyframe JPEG from analysis (preferred for list thumbnails) */
  posterUrl?: string | null;
  alt: string;
  size?: SampleThumbnailSize;
  className?: string;
  /** Click to open preview; uses div + stopPropagation (safe inside list row buttons) */
  onPreviewClick?: () => void;
};

export function SampleThumbnail({
  previewUrl,
  posterUrl,
  alt,
  size = "sm",
  className,
  onPreviewClick,
}: SampleThumbnailProps) {
  const canPreview = Boolean(onPreviewClick && previewUrl);
  const imageSrc = posterUrl ?? null;
  const videoSrc =
    !imageSrc && previewUrl
      ? previewUrl.includes("#")
        ? previewUrl
        : `${previewUrl}#t=0.5`
      : null;

  const media = imageSrc ? (
    // eslint-disable-next-line @next/next/no-img-element -- keyframe URLs are API media paths
    <img
      src={imageSrc}
      alt={alt}
      loading="lazy"
      decoding="async"
      className="h-full w-full object-cover"
    />
  ) : videoSrc ? (
    <video
      src={videoSrc}
      muted
      playsInline
      preload="metadata"
      aria-hidden
      className="h-full w-full object-cover"
    />
  ) : (
    <div className="flex h-full items-center justify-center text-[9px] text-muted-foreground">
      无预览
    </div>
  );

  return (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-md bg-black",
        SIZE_CLASS[size],
        canPreview && "group cursor-pointer",
        className,
      )}
      role={canPreview ? "button" : undefined}
      tabIndex={canPreview ? 0 : undefined}
      aria-label={canPreview ? `播放 ${alt}` : undefined}
      onClick={
        canPreview
          ? (event) => {
              event.stopPropagation();
              onPreviewClick?.();
            }
          : undefined
      }
      onKeyDown={
        canPreview
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                onPreviewClick?.();
              }
            }
          : undefined
      }
    >
      {media}
      {canPreview ? (
        <span
          className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/35 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
          aria-hidden
        >
          <Play className="h-4 w-4 fill-white text-white" />
        </span>
      ) : null}
    </div>
  );
}
