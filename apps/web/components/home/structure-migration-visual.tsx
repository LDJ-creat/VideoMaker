import { Film, Play } from "lucide-react";

export function StructureMigrationVisual() {
  return (
    <div
      className="relative mx-auto w-full max-w-md lg:max-w-none"
      aria-hidden="true"
    >
      <div className="rounded-3xl border border-border/60 bg-card/80 p-6 shadow-sm backdrop-blur-sm dark:bg-card/60">
        <svg
          viewBox="0 0 400 220"
          className="h-auto w-full text-primary"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            x="20"
            y="40"
            width="90"
            height="140"
            rx="12"
            stroke="currentColor"
            strokeWidth="2"
            className="fill-secondary/80"
          />
          <rect
            x="155"
            y="70"
            width="90"
            height="80"
            rx="12"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="6 4"
            className="fill-muted/50"
          />
          <rect
            x="290"
            y="40"
            width="90"
            height="140"
            rx="12"
            stroke="currentColor"
            strokeWidth="2"
            className="fill-secondary/60"
          />
          <circle cx="185" cy="95" r="8" fill="currentColor" opacity="0.9" />
          <circle cx="200" cy="110" r="10" fill="currentColor" />
          <circle cx="215" cy="125" r="8" fill="currentColor" opacity="0.9" />
          <line
            x1="193"
            y1="103"
            x2="198"
            y2="108"
            stroke="currentColor"
            strokeWidth="1.5"
            opacity="0.6"
          />
          <line
            x1="208"
            y1="118"
            x2="213"
            y2="123"
            stroke="currentColor"
            strokeWidth="1.5"
            opacity="0.6"
          />
          <path
            d="M110 110 L145 110"
            stroke="currentColor"
            strokeWidth="2"
            markerEnd="url(#arrowhead)"
            opacity="0.5"
          />
          <path
            d="M245 110 L280 110"
            stroke="currentColor"
            strokeWidth="2"
            markerEnd="url(#arrowhead)"
            opacity="0.5"
          />
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="8"
              refX="6"
              refY="4"
              orient="auto"
            >
              <polygon points="0 0, 8 4, 0 8" fill="currentColor" opacity="0.5" />
            </marker>
          </defs>
        </svg>
        <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs text-muted-foreground">
          <span className="flex flex-col items-center gap-1">
            <Film className="h-4 w-4 text-primary/70" />
            样例视频
          </span>
          <span className="flex flex-col items-center gap-1">
            <span className="flex h-4 w-4 items-center justify-center rounded-full border border-primary/40 text-[10px] font-medium text-primary">
              3
            </span>
            结构槽位
          </span>
          <span className="flex flex-col items-center gap-1">
            <Play className="h-4 w-4 text-primary/70" />
            新视频
          </span>
        </div>
      </div>
    </div>
  );
}
