import { Film } from "lucide-react";

import { placeholderDisplayName } from "@/lib/coverPlaceholders";
import { cn } from "@/lib/utils";

type TemplateCoverPlaceholderProps = {
  category: string;
  slotPattern?: string;
  className?: string;
};

export function TemplateCoverPlaceholder({
  category,
  slotPattern,
  className,
}: TemplateCoverPlaceholderProps) {
  const displayName = placeholderDisplayName(category);

  return (
    <div
      className={cn(
        "relative flex h-full w-full flex-col overflow-hidden",
        "bg-gradient-to-br from-studio-cream via-background to-studio-wheat bg-studio-texture",
        "dark:from-stone-900/95 dark:via-card dark:to-amber-950/25",
        className,
      )}
      data-testid="template-cover-placeholder"
      aria-hidden
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent dark:via-primary/30"
        aria-hidden
      />

      {slotPattern ? (
        <p className="pointer-events-none absolute inset-x-4 top-3 truncate text-center font-mono text-[10px] text-primary/25 dark:text-primary/35">
          {slotPattern}
        </p>
      ) : null}

      <div className="absolute inset-3 rounded-lg border border-primary/10 bg-background/30 dark:border-primary/20 dark:bg-background/10">
        <div className="relative flex h-full items-center justify-center">
          <span className="select-none px-2 text-center font-serif text-2xl font-semibold leading-tight tracking-tight text-primary/20 dark:text-primary/30 sm:text-3xl">
            {displayName}
          </span>
          <Film
            className="absolute bottom-2 right-2 h-5 w-5 text-primary/30 dark:text-primary/40"
            aria-hidden
          />
        </div>
      </div>

      <p className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-[10px] text-muted-foreground/60">
        待收录样例封面
      </p>
    </div>
  );
}
