import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScriptReviewPanel } from "@/features/script-review/ScriptReviewPanel";
import * as apiClient from "@/lib/apiClient";

describe("ScriptReviewPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads draft and calls approve-master", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "getScriptDraft").mockResolvedValue({
      data: {
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "总脚本草稿",
          masterNarrationStatus: "draft",
          storyboard: [],
          storyboardStatus: "draft",
        },
        taskStage: "awaiting_master_review",
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "updateScriptDraft").mockResolvedValue({
      data: {
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "总脚本草稿",
          masterNarrationStatus: "draft",
          storyboard: [],
          storyboardStatus: "draft",
        },
      },
      meta: { dataSource: "api" },
    });
    const approveMaster = vi.spyOn(apiClient, "approveMasterScript").mockResolvedValue({
      data: {
        generationId: "gen-1",
        taskId: "task-1",
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "总脚本草稿",
          masterNarrationStatus: "approved",
          storyboard: [],
          storyboardStatus: "draft",
        },
      },
      meta: { dataSource: "api" },
    });

    render(
      <ScriptReviewPanel
        projectId="project-1"
        variants={[
          {
            generationId: "gen-1",
            variant: "high_click",
            label: "高点击版",
            taskEvent: {
              taskId: "task-1",
              status: "awaiting_review",
              stage: "awaiting_master_review",
              progress: 40,
              message: "等待总脚本审核",
              updatedAt: new Date().toISOString(),
            },
          },
        ]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("总脚本草稿")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "批准总脚本并生成分镜" }));
    expect(approveMaster).toHaveBeenCalledWith("gen-1");
  });

  it("submits NL revise for master script", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "getScriptDraft").mockResolvedValue({
      data: {
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "总脚本草稿",
          masterNarrationStatus: "draft",
          storyboard: [],
          storyboardStatus: "draft",
        },
        taskStage: "awaiting_master_review",
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "updateScriptDraft").mockResolvedValue({
      data: {
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "总脚本草稿",
          masterNarrationStatus: "draft",
          storyboard: [],
          storyboardStatus: "draft",
        },
      },
      meta: { dataSource: "api" },
    });
    const nlRevise = vi.spyOn(apiClient, "nlReviseScriptDraft").mockResolvedValue({
      data: {
        draft: {
          generationId: "gen-1",
          projectId: "project-1",
          variant: "high_click",
          masterNarration: "更抓人的总脚本",
          masterNarrationStatus: "draft",
          storyboard: [],
          storyboardStatus: "draft",
        },
        revisionId: "rev-1",
        summary: "强化了开场钩子",
      },
      meta: { dataSource: "api" },
    });

    render(
      <ScriptReviewPanel
        projectId="project-1"
        variants={[
          {
            generationId: "gen-1",
            variant: "high_click",
            label: "高点击版",
            taskEvent: {
              taskId: "task-1",
              status: "awaiting_review",
              stage: "awaiting_master_review",
              progress: 40,
              message: "等待总脚本审核",
              updatedAt: new Date().toISOString(),
            },
          },
        ]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue("总脚本草稿")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("脚本修改指令"), "开头更抓人");
    await user.click(screen.getByRole("button", { name: "应用修改" }));

    await waitFor(() => {
      expect(nlRevise).toHaveBeenCalledWith("gen-1", {
        scope: "master",
        instruction: "开头更抓人",
      });
    });
    expect(screen.getByDisplayValue("更抓人的总脚本")).toBeInTheDocument();
    expect(screen.getByTestId("nl-revise-summary")).toHaveTextContent("强化了开场钩子");
  });
});
