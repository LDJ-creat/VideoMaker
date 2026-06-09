import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GenerationRunHistoryPanel } from "@/features/generation-runs/GenerationRunHistoryPanel";
import * as apiClient from "@/lib/apiClient";

describe("GenerationRunHistoryPanel", () => {
  it("shows per-variant status and invokes onSelectRun", async () => {
    const user = userEvent.setup();
    const onSelectRun = vi.fn();

    vi.spyOn(apiClient, "listGenerationRuns").mockResolvedValue({
      data: {
        runs: [
          {
            id: "run-1",
            projectId: "proj-1",
            status: "partial_failed",
            variantIds: ["high_click", "high_conversion"],
            generationIds: ["gen-a", "gen-b"],
            createdAt: "2026-06-07T11:52:06.877595Z",
            updatedAt: "2026-06-07T11:52:06.877595Z",
          },
        ],
      },
      meta: { dataSource: "api" },
    });

    vi.spyOn(apiClient, "getGenerationRun").mockResolvedValue({
      data: {
        run: {
          id: "run-1",
          projectId: "proj-1",
          status: "partial_failed",
          variantIds: ["high_click", "high_conversion"],
          generationIds: ["gen-a", "gen-b"],
          createdAt: "2026-06-07T11:52:06.877595Z",
          updatedAt: "2026-06-07T11:52:06.877595Z",
        },
        generations: [
          {
            generationId: "gen-a",
            variant: "high_click",
            status: "failed",
            taskId: "task-a",
          },
          {
            generationId: "gen-b",
            variant: "high_conversion",
            status: "succeeded",
            taskId: "task-b",
          },
        ],
        provenance: null,
      },
      meta: { dataSource: "api" },
    });

    render(
      <GenerationRunHistoryPanel
        projectId="proj-1"
        activeRunId={null}
        onSelectRun={onSelectRun}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("高点击版 · 生成失败")).toBeInTheDocument();
      expect(screen.getByText("高转化版 · 生成成功")).toBeInTheDocument();
      expect(screen.getByTestId("run-title-run-1")).toHaveTextContent(
        /批次 1 · 2026年6月7日/,
      );
      expect(screen.queryByText("2026-06-07T11:52:06.877595Z")).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "查看结果" }));
    expect(onSelectRun).toHaveBeenCalledWith("run-1");
  });
});
