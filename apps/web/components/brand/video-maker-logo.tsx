import { cn } from "@/lib/utils";

type VideoMakerLogoProps = {
  size?: "sm" | "md";
  showWordmark?: boolean;
  className?: string;
};

const sizeMap = {
  sm: { icon: 28, text: "text-sm" },
  md: { icon: 36, text: "text-base" },
} as const;

export function VideoMakerLogo({
  size = "md",
  showWordmark = false,
  className,
}: VideoMakerLogoProps) {
  const { icon, text } = sizeMap[size];

  return (
    <span className={cn("inline-flex items-center gap-2.5 text-primary", className)}>
      <svg
        width={icon}
        height={icon}
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect
          x="2"
          y="8"
          width="32"
          height="20"
          rx="3"
          stroke="currentColor"
          strokeWidth="1.75"
          fill="hsl(var(--secondary))"
        />
        <rect x="5" y="11" width="8" height="6" rx="1" fill="currentColor" opacity="0.25" />
        <rect x="23" y="11" width="8" height="6" rx="1" fill="currentColor" opacity="0.25" />
        <circle cx="12" cy="24" r="2" fill="currentColor" opacity="0.5" />
        <circle cx="18" cy="20" r="2.5" fill="currentColor" />
        <circle cx="24" cy="24" r="2" fill="currentColor" opacity="0.5" />
        <line
          x1="14"
          y1="24"
          x2="16"
          y2="20.5"
          stroke="currentColor"
          strokeWidth="1.25"
          opacity="0.7"
        />
        <line
          x1="20"
          y1="20.5"
          x2="22"
          y2="24"
          stroke="currentColor"
          strokeWidth="1.25"
          opacity="0.7"
        />
      </svg>
      {showWordmark ? (
        <span className={cn("font-serif font-semibold tracking-tight text-foreground", text)}>
          VideoMaker
        </span>
      ) : null}
    </span>
  );
}
