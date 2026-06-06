"use client";

import type { WorkbenchPanel } from "@/features/workbench/workbenchTypes";
import {
  PHASE_LABELS,
  PHASE_ORDER,
  PHASE_PANELS,
  getPhaseForPanel,
  type WorkbenchPhase,
  type WorkbenchPhaseState,
} from "@/features/workbench/workbenchPhases";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type WorkbenchStepperProps = {
  phaseState: WorkbenchPhaseState;
  panel: WorkbenchPanel;
  panelLabels: Record<WorkbenchPanel, string>;
  onSelectPanel: (panel: WorkbenchPanel) => void;
  taskBadge?: React.ReactNode;
};

function PhaseIndicator({
  phase,
  isActive,
  isCompleted,
}: {
  phase: WorkbenchPhase;
  isActive: boolean;
  isCompleted: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 text-xs font-medium",
        isActive ? "text-primary" : isCompleted ? "text-foreground" : "text-muted-foreground",
      )}
      data-testid={`workbench-phase-${phase}`}
    >
      <span
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded-full border text-[10px]",
          isActive && "border-primary bg-primary text-primary-foreground",
          !isActive && isCompleted && "border-primary/50 bg-primary/10 text-primary",
          !isActive && !isCompleted && "border-border bg-muted/30",
        )}
      >
        {PHASE_ORDER.indexOf(phase) + 1}
      </span>
      <span className="hidden sm:inline">{PHASE_LABELS[phase]}</span>
    </div>
  );
}

export function WorkbenchStepper({
  phaseState,
  panel,
  panelLabels,
  onSelectPanel,
  taskBadge,
}: WorkbenchStepperProps) {
  const currentPhase = phaseState.activePhase;

  return (
    <div className="space-y-3" data-testid="workbench-stepper">
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card/60 px-4 py-3">
        {PHASE_ORDER.map((phase, index) => (
          <div key={phase} className="flex items-center gap-4">
            <PhaseIndicator
              phase={phase}
              isActive={currentPhase === phase}
              isCompleted={phaseState.completedPhases.includes(phase)}
            />
            {index < PHASE_ORDER.length - 1 ? (
              <span className="hidden h-px w-8 bg-border sm:block" aria-hidden />
            ) : null}
          </div>
        ))}
      </div>

      <nav
        className="flex flex-wrap gap-2"
        aria-label="工作台视图"
        data-testid="workbench-nav"
      >
        {PHASE_ORDER.map((phase) => (
          <div key={phase} className="flex flex-wrap gap-1.5">
            {PHASE_PANELS[phase].map((key) => {
              const isCurrentPhase = getPhaseForPanel(key) === currentPhase;
              return (
                <Button
                  key={key}
                  type="button"
                  size="sm"
                  variant={panel === key ? "default" : isCurrentPhase ? "outline" : "ghost"}
                  className={cn(!isCurrentPhase && panel !== key && "opacity-70")}
                  onClick={() => onSelectPanel(key)}
                >
                  {panelLabels[key]}
                </Button>
              );
            })}
            {phase !== "output" ? (
              <span className="mx-1 hidden self-center text-border sm:inline">|</span>
            ) : null}
          </div>
        ))}
        {taskBadge}
      </nav>
    </div>
  );
}
