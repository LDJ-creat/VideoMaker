import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EditIntentList } from "@/features/nl-revise/EditIntentList";
import { ReviseInputBar } from "@/features/nl-revise/ReviseInputBar";
import {
  TimelineDiffSummary,
  buildTimelineDiffItems,
} from "@/features/nl-revise/TimelineDiffSummary";
import {
  fixtureEditIntent,
  fixtureGenerationPlan,
  fixtureGenerationPlanRevised,
} from "@/fixtures";

describe("ReviseInputBar", () => {
  afterEach(() => {
    cleanup();
  });

  it("submits trimmed instruction and clears input", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<ReviseInputBar onSubmit={onSubmit} />);

    const input = screen.getByLabelText("改片指令");
    await user.type(input, "  开头更抓人  ");
    await user.click(screen.getByRole("button", { name: "提交改片" }));

    expect(onSubmit).toHaveBeenCalledWith("开头更抓人");
    expect(input).toHaveValue("");
  });

  it("disables submit when instruction is empty", () => {
    render(<ReviseInputBar onSubmit={() => undefined} />);

    expect(screen.getByRole("button", { name: "提交改片" })).toBeDisabled();
  });
});

describe("EditIntentList", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders parsed intents with Chinese labels", () => {
    render(<EditIntentList intents={fixtureEditIntent.intents} />);

    expect(screen.getByTestId("edit-intent-list")).toBeInTheDocument();
    expect(screen.getByText("强化开头 hook")).toBeInTheDocument();
    expect(screen.getByText("减少字幕")).toBeInTheDocument();
    expect(screen.getByText("用户希望开头更抓人")).toBeInTheDocument();
  });
});

describe("TimelineDiffSummary", () => {
  afterEach(() => {
    cleanup();
  });

  it("highlights changed fields between plans", () => {
    const items = buildTimelineDiffItems(
      fixtureGenerationPlan,
      fixtureGenerationPlanRevised,
    );

    expect(items.find((item) => item.label === "总时长")?.changed).toBe(true);
    expect(items.find((item) => item.label === "包装风格")?.changed).toBe(true);

    render(
      <TimelineDiffSummary
        before={fixtureGenerationPlan}
        after={fixtureGenerationPlanRevised}
      />,
    );

    expect(screen.getByTestId("timeline-diff-summary")).toBeInTheDocument();
    expect(screen.getAllByText("已变更").length).toBeGreaterThan(0);
  });
});
