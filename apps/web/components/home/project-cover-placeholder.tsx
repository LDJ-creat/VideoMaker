import { Clapperboard } from "lucide-react";

import { placeholderDisplayName } from "@/lib/coverPlaceholders";
import { cn } from "@/lib/utils";

type ProjectCoverPlaceholderProps = {
  projectName: string;
  gradient: string;
  className?: string;
};

export function ProjectCoverPlaceholder({
  projectName,
  gradient,
  className,
}: ProjectCoverPlaceholderProps) {
  const displayName = placeholderDisplayName(projectName);

  return (
    <div
      className={cn(
        "relative h-full w-full overflow-hidden bg-gradient-to-br bg-film-grain",
        gradient,
        className,
      )}
      data-testid="project-cover-placeholder"
      aria-hidden
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(135deg,transparent_0,transparent_12px,rgba(255,255,255,0.02)_12px,rgba(255,255,255,0.02)_13px)] dark:bg-[repeating-linear-gradient(135deg,transparent_0,transparent_12px,rgba(255,255,255,0.015)_12px,rgba(255,255,255,0.015)_13px)]"
        aria-hidden
      />

      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5">
        <div className="flex min-h-14 min-w-[4.5rem] max-w-[85%] items-center justify-center rounded-2xl border border-foreground/10 bg-background/25 px-3 py-2 font-serif text-base font-semibold leading-tight text-foreground/30 shadow-sm backdrop-blur-sm transition-transform duration-300 group-hover:scale-105 dark:bg-background/15 dark:text-foreground/25 sm:text-lg">
          {displayName}
        </div>
        <Clapperboard
          className="h-6 w-6 text-foreground/20 dark:text-foreground/25"
          aria-hidden
        />
        <p className="text-[10px] text-muted-foreground/65">等待样例或成片</p>
      </div>
    </div>
  );
}
