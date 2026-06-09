import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RevisePlanCard } from "@/features/nl-revise/RevisePlanCard";
import { fixtureRevisePlan } from "@/fixtures";

describe("RevisePlanCard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders plan summary and actions", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <RevisePlanCard
        plan={fixtureRevisePlan}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByTestId("revise-plan-card")).toBeInTheDocument();
    expect(screen.getByText(fixtureRevisePlan.summary)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认执行" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
