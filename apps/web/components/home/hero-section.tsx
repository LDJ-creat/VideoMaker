import { AlertCircle, ArrowRight, Sparkles } from "lucide-react";
import type { RefObject } from "react";

import { StructureMigrationVisual } from "@/components/home/structure-migration-visual";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type HeroSectionProps = {
  name: string;
  creating: boolean;
  error: string | null;
  onNameChange: (value: string) => void;
  onCreate: () => void;
  onLoadDemo: () => void;
  inputRef?: RefObject<HTMLInputElement | null>;
};

export function HeroSection({
  name,
  creating,
  error,
  onNameChange,
  onCreate,
  onLoadDemo,
  inputRef,
}: HeroSectionProps) {
  return (
    <section
      id="hero"
      className={cn(
        "relative overflow-hidden rounded-3xl border border-border/50",
        "bg-gradient-to-br from-studio-cream via-background to-studio-wheat",
        "bg-studio-texture px-6 py-12 sm:px-10 sm:py-16 lg:px-12 lg:py-20",
      )}
    >
      <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/5 blur-3xl" />
      <div className="absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-secondary blur-3xl" />

      <div className="relative z-10 grid items-center gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
        <div className="space-y-6 text-left">
          <Badge
            variant="outline"
            className="motion-safe-animate-in border-primary/40 bg-background/60 text-primary"
          >
            VideoMaker Beta
          </Badge>

          <h1
            className={cn(
              "motion-safe-animate-in font-serif text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl",
              "[animation-delay:80ms]",
            )}
          >
            让爆款视频的结构
            <br className="hidden sm:block" />
            为您所用
          </h1>

          <p
            className={cn(
              "motion-safe-animate-in max-w-lg text-lg leading-relaxed text-muted-foreground",
              "[animation-delay:160ms]",
            )}
          >
            上传高转化样例视频，一键提取镜头结构与爆款脚本，结合您的素材，自动化生成专属视频创意。
          </p>

          <div
            className={cn(
              "motion-safe-animate-in flex max-w-lg flex-col gap-3 rounded-2xl border border-border bg-card p-2 shadow-sm sm:flex-row sm:items-center",
              "[animation-delay:240ms]",
            )}
          >
            <Input
              ref={inputRef}
              placeholder="为新项目命名，如：夏季防晒喷雾"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onCreate()}
              className="h-12 flex-1 border-0 bg-transparent text-base focus-visible:ring-0 focus-visible:ring-offset-0"
            />
            <Button
              size="lg"
              disabled={creating || !name.trim()}
              onClick={onCreate}
              className="h-12 w-full shrink-0 rounded-xl px-8 sm:w-auto"
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {creating ? "创建中…" : "开始创建"}
            </Button>
          </div>

          {error ? (
            <p className="inline-flex max-w-md items-center gap-2 rounded-full border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="truncate">{error}</span>
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>还没想好怎么做？</span>
            <button
              type="button"
              onClick={onLoadDemo}
              className="inline-flex cursor-pointer items-center gap-1 font-medium text-primary transition-colors hover:underline underline-offset-4"
            >
              加载演示项目
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="motion-safe-animate-in [animation-delay:320ms]">
          <StructureMigrationVisual />
        </div>
      </div>
    </section>
  );
}
