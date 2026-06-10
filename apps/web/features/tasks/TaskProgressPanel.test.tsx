import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { fixtureTaskEvent } from "@/fixtures";

describe("TaskProgressPanel", () => {
  afterEach(() => {
    cleanup();
  });
  it("shows Chinese stage label instead of raw enum", () => {
    render(
      <TaskProgressPanel
        event={{
          ...fixtureTaskEvent,
          stage: "generating_image",
          message: "正在生成补全图片…",
        }}
        mode="sse"
        sseFailureCount={0}
        error={null}
      />,
    );

    expect(screen.getByText("正在生成补全图片…")).toBeInTheDocument();
    expect(screen.getByText("AI 生图")).toBeInTheDocument();
    expect(screen.queryByText("generating_image")).not.toBeInTheDocument();
  });

  it("shows retry when onRetry is provided for succeeded render-incomplete tasks", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <TaskProgressPanel
        event={{
          ...fixtureTaskEvent,
          status: "succeeded",
          stage: "completed",
          progress: 100,
          message: "Generation plan and preview ready",
        }}
        mode="idle"
        sseFailureCount={0}
        error={null}
        onRetry={onRetry}
        retryLabel="重新渲染 MP4"
      />,
    );

    expect(screen.getByText(/演示 MP4 尚未就绪/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新渲染 MP4" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("keeps raw stage in dev footer only", async () => {
    const user = userEvent.setup();
    render(
      <TaskProgressPanel
        event={{
          ...fixtureTaskEvent,
          stage: "transcribing",
        }}
        mode="polling"
        sseFailureCount={0}
        error={null}
      />,
    );

    expect(screen.getByText("语音转写")).toBeInTheDocument();
    expect(screen.queryByText(/stage=transcribing/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看技术详情" }));
    expect(screen.getByText(/stage=transcribing/)).toBeInTheDocument();
  });
});
