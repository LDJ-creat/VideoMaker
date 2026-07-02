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

  it("shows material review note for fork material_regen plans", () => {
    render(
      <RevisePlanCard
        plan={{
          ...fixtureRevisePlan,
          executionMode: "fork",
          materialReviewGateExpected: true,
          intents: [
            {
              ...fixtureRevisePlan.intents[0],
              executionTool: "material_regen",
            },
          ],
        }}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/执行后将暂停于素材预览审核/),
    ).toBeInTheDocument();
  });

  it("hides material review note when gate is not expected", () => {
    render(
      <RevisePlanCard
        plan={{
          ...fixtureRevisePlan,
          executionMode: "fork",
          materialReviewGateExpected: false,
          intents: [
            {
              ...fixtureRevisePlan.intents[0],
              executionTool: "material_regen",
            },
          ],
        }}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      screen.queryByText(/执行后将暂停于素材预览审核/),
    ).not.toBeInTheDocument();
  });

  it("shows material regen intent label for scene structured plans", () => {
    render(
      <RevisePlanCard
        plan={{
          ...fixtureRevisePlan,
          planSource: "scene_structured",
          executionMode: "fork",
          summary: "重新生成 slot-2",
          intents: [
            {
              target: "generation_plan.storyboard",
              operation: "change_packaging_style",
              executionTool: "material_regen",
              scope: "scene",
              sceneIds: ["scene-slot-2"],
              slotIds: ["slot-2"],
              params: {
                sceneId: "scene-slot-2",
                slotId: "slot-2",
                materialEditMode: "full",
                editInstruction: "重新生成该分镜",
                requiresMaterialRegen: true,
              },
              rationale: "重新生成该分镜",
            },
          ],
          executionSteps: [{ tool: "material_regen", description: "重生成 slot-2" }],
        }}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("单镜完全重生成")).toBeInTheDocument();
    expect(screen.queryByText("更换包装风格")).not.toBeInTheDocument();
  });
});
