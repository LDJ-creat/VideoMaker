import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import { VariantPicker } from "@/features/generation-variants/VariantPicker";
import { VariantTabs } from "@/features/generation-variants/VariantTabs";
import {
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
} from "@/fixtures";

describe("VariantPicker", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders enabled variants checked by default selection", () => {
    render(
      <VariantPicker
        selectedVariantIds={["high_click", "high_conversion"]}
        onChange={() => undefined}
      />,
    );

    expect(screen.getByLabelText("高点击版")).toBeChecked();
    expect(screen.getByLabelText("高转化版")).toBeChecked();
    expect(screen.getByText("生成变体")).toBeInTheDocument();
  });

  it("calls onChange when toggling a variant", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <VariantPicker
        selectedVariantIds={["high_click", "high_conversion"]}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByLabelText("高点击版"));
    expect(onChange).toHaveBeenCalledWith(["high_conversion"]);
  });
});

describe("VariantTabs", () => {
  afterEach(() => {
    cleanup();
  });

  function VariantTabsHarness({
    initialActiveId,
  }: {
    initialActiveId: string;
  }) {
    const [activeGenerationId, setActiveGenerationId] = useState(initialActiveId);
    return (
      <VariantTabs
        tabs={[
          {
            generationId: fixtureGenerationPlanHighClick.id,
            variant: "high_click",
            label: "高点击版",
            plan: fixtureGenerationPlanHighClick,
          },
          {
            generationId: fixtureGenerationPlan.id,
            variant: "high_conversion",
            label: "高转化版",
            plan: fixtureGenerationPlan,
          },
        ]}
        activeGenerationId={activeGenerationId}
        onActiveChange={setActiveGenerationId}
      />
    );
  }

  it("renders a tab per generation with plan content", async () => {
    const user = userEvent.setup();

    render(
      <VariantTabsHarness initialActiveId={fixtureGenerationPlanHighClick.id} />,
    );

    expect(screen.getByRole("tab", { name: "高点击版" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "高转化版" })).toBeInTheDocument();
    expect(screen.getByText(/变体 high_click · 3 个分镜场景/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "高转化版" }));
    expect(screen.getByRole("tab", { name: "高转化版" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText(/变体 high_conversion · 3 个分镜场景/)).toBeInTheDocument();
  });
});
