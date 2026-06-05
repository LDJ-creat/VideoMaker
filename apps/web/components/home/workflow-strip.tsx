import { ArrowRight, Film, Layers, Play, Puzzle } from "lucide-react";

const STEPS = [
  { icon: Film, label: "样例视频", step: "01" },
  { icon: Layers, label: "结构提取", step: "02" },
  { icon: Puzzle, label: "素材匹配", step: "03" },
  { icon: Play, label: "生成预览", step: "04" },
] as const;

export function WorkflowStrip() {
  return (
    <section
      className="border-t border-border/60 pt-10"
      aria-label="创作流程"
    >
      <div className="overflow-x-auto pb-2">
        <ol className="flex min-w-max items-center justify-center gap-2 sm:gap-4 md:min-w-0 md:gap-6">
          {STEPS.map(({ icon: Icon, label, step }, index) => (
            <li key={step} className="flex items-center gap-2 sm:gap-4 md:gap-6">
              <div className="flex flex-col items-center gap-2 text-center sm:flex-row sm:text-left">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border bg-card shadow-sm">
                  <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {step}
                  </p>
                  <p className="whitespace-nowrap text-sm font-medium text-foreground">
                    {label}
                  </p>
                </div>
              </div>
              {index < STEPS.length - 1 ? (
                <ArrowRight
                  className="hidden h-4 w-4 shrink-0 text-muted-foreground/50 sm:block"
                  aria-hidden="true"
                />
              ) : null}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
