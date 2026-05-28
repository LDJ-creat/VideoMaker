import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";

vi.mock("@/features/tasks/useTaskProgress", () => ({
  useTaskProgress: () => ({
    event: null,
    mode: "idle" as const,
    sseFailureCount: 0,
    error: null,
  }),
}));

describe("ProjectWorkbench", () => {
  it("switches between input, progress, structure, gap, timeline, and result panels", async () => {
    const user = userEvent.setup();
    render(<ProjectWorkbench projectId="proj-test" />);

    expect(screen.getByText(/样例视频/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "进度" }));
    expect(screen.getByText(/任务进度/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "样例分析" }));
    expect(
      screen.getByRole("heading", { name: "样例分析" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结构槽" }));
    expect(screen.getByText(/结构槽位/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "缺口" }));
    expect(screen.getByText(/缺口报告/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "时间线" }));
    expect(screen.getByText(/时间线预览/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结果" }));
    expect(screen.getByText(/生成结果/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "录入" }));
    expect(screen.getByText(/创作 Brief/i)).toBeInTheDocument();
  });
});
