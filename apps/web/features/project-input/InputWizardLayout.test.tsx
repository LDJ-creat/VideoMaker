import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { InputWizardLayout, InputWizardPrimaryGrid, InputWizardSection } from "@/features/project-input/InputWizardLayout";

describe("InputWizardLayout", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders ordered wizard sections", () => {
    render(
      <InputWizardLayout>
        <InputWizardPrimaryGrid>
          <InputWizardSection step={1} title="样例视频">
            <p>step one</p>
          </InputWizardSection>
          <InputWizardSection step={2} title="创作 Brief">
            <p>step two</p>
          </InputWizardSection>
        </InputWizardPrimaryGrid>
      </InputWizardLayout>,
    );

    expect(screen.getByTestId("input-wizard-layout")).toBeInTheDocument();
    expect(screen.getByTestId("input-wizard-primary-grid")).toBeInTheDocument();
    expect(screen.getByTestId("input-wizard-step-1")).toBeInTheDocument();
    expect(screen.getByTestId("input-wizard-step-2")).toBeInTheDocument();
    expect(screen.getByText("样例视频")).toBeInTheDocument();
    expect(screen.getByText("创作 Brief")).toBeInTheDocument();
  });
});
