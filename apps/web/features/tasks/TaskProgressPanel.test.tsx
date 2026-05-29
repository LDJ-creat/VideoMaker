import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TaskProgressPanel } from "@/features/tasks/TaskProgressPanel";
import { fixtureTaskEvent } from "@/fixtures";

describe("TaskProgressPanel", () => {
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

  it("keeps raw stage in dev footer only", () => {
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

    expect(screen.getByText(/stage=transcribing/)).toBeInTheDocument();
    expect(screen.getByText("语音转写")).toBeInTheDocument();
  });
});
