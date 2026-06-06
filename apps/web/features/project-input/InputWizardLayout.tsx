"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type InputWizardSectionProps = {
  step: number;
  title: string;
  description?: string;
  actionSlot?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function InputWizardSection({
  step,
  title,
  description,
  actionSlot,
  children,
  className,
}: InputWizardSectionProps) {
  return (
    <section
      className={cn(
        "flex flex-col rounded-2xl border border-border bg-card p-5 shadow-sm sm:p-6",
        className,
      )}
      data-testid={`input-wizard-step-${step}`}
    >
      <header className="mb-3 flex shrink-0 flex-wrap items-start justify-between gap-3 sm:mb-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Step {step}
          </p>
          <h2 className="font-serif text-lg font-semibold tracking-tight">{title}</h2>
          {description ? (
            <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actionSlot}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

type InputWizardAdvancedProps = {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
  testId?: string;
};

export function InputWizardAdvanced({
  title,
  defaultOpen = false,
  children,
  testId,
}: InputWizardAdvancedProps) {
  return (
    <details
      className="rounded-2xl border border-border bg-muted/20 p-4"
      open={defaultOpen}
      data-testid={testId}
    >
      <summary className="cursor-pointer font-serif text-base font-semibold tracking-tight">
        {title}
      </summary>
      <div className="mt-4 space-y-4">{children}</div>
    </details>
  );
}

type InputWizardLayoutProps = {
  children: ReactNode;
};

/** 录入页主容器：宽屏下扩展至 6xl，避免两侧大面积留白 */
export function InputWizardLayout({ children }: InputWizardLayoutProps) {
  return (
    <div
      className="mx-auto w-full max-w-6xl space-y-8 px-1 sm:px-0"
      data-testid="input-wizard-layout"
    >
      {children}
    </div>
  );
}

/** Step 1 + Step 2 并排，首屏同时可见上传与 Brief */
export function InputWizardPrimaryGrid({ children }: { children: ReactNode }) {
  return (
    <div
      className="grid gap-6 lg:grid-cols-2 lg:items-stretch xl:gap-8"
      data-testid="input-wizard-primary-grid"
    >
      {children}
    </div>
  );
}

/** Advanced 区块并排（样例选择 / 知识推荐） */
export function InputWizardSecondaryGrid({ children }: { children: ReactNode }) {
  return (
    <div
      className="grid gap-8 xl:grid-cols-2 xl:items-start"
      data-testid="input-wizard-secondary-grid"
    >
      {children}
    </div>
  );
}
