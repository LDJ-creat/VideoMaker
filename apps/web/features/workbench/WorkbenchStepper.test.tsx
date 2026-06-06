import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkbenchStepper } from "@/features/workbench/WorkbenchStepper";
import { PANEL_LABELS } from "@/features/workbench/workbenchTypes";

describe("WorkbenchStepper", () => {
  afterEach(() => {
    cleanup();
  });

  it("groups panel tabs by phase and highlights active panel", async () => {
    const user = userEvent.setup();
    const onSelectPanel = vi.fn();

    render(
      <WorkbenchStepper
        phaseState={{ activePhase: "prepare", completedPhases: ["prepare"] }}
        panel="input"
        panelLabels={PANEL_LABELS}
        onSelectPanel={onSelectPanel}
      />,
    );

    expect(screen.getByTestId("workbench-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-nav")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-phase-prepare")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "样例分析" }));
    expect(onSelectPanel).toHaveBeenCalledWith("analysis");
  });
});
