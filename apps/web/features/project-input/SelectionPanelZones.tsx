"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SelectionCurrentZoneProps = {
  title?: string;
  description?: string;
  className?: string;
  children: ReactNode;
};

/** 已确认选用区：实心边框 + 主色浅底，与候选区形成对比 */
export function SelectionCurrentZone({
  title = "当前选用",
  description,
  className,
  children,
}: SelectionCurrentZoneProps) {
  return (
    <section
      className={cn(
        "rounded-xl border border-primary/30 bg-primary/[0.06] p-4 shadow-sm ring-1 ring-primary/10",
        className,
      )}
      data-testid="selection-current-zone"
    >
      <header className="mb-3 flex items-start gap-2 border-b border-primary/15 pb-2.5">
        <span
          className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary"
          aria-hidden
        />
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-foreground">{title}</h4>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

type SelectionCandidateZoneProps = {
  title: string;
  count: number;
  onCollapse: () => void;
  collapseLabel?: string;
  className?: string;
  children: ReactNode;
};

/** 候选切换区：虚线边框 + 中性底，与上方选用区明显分层 */
export function SelectionCandidateZone({
  title,
  count,
  onCollapse,
  collapseLabel = "收起候选",
  className,
  children,
}: SelectionCandidateZoneProps) {
  return (
    <section
      className={cn(
        "rounded-xl border border-dashed border-muted-foreground/35 bg-muted/20 p-4",
        className,
      )}
      data-testid="selection-candidate-zone"
    >
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border/70 pb-2.5">
        <div className="min-w-0">
          <h4 className="text-sm font-medium text-foreground">
            {title}
            <span className="ml-1.5 font-normal text-muted-foreground">({count})</span>
          </h4>
          <p className="mt-0.5 text-xs text-muted-foreground">
            在下方切换主条目与参考条目
          </p>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={onCollapse}>
          {collapseLabel}
        </Button>
      </header>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

/** 知识推荐匹配分：0 分不展示，避免误导性的「0%」 */
export function formatKnowledgeMatchScore(score: number): string | null {
  if (!Number.isFinite(score) || score <= 0) {
    return null;
  }
  const percent = Math.round(score * 100);
  if (percent <= 0) {
    return null;
  }
  return `${percent}%`;
}
