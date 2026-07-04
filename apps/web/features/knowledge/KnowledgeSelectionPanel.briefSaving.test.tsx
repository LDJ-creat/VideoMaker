import { createRef } from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeSelectionPanel } from "@/features/knowledge/KnowledgeSelectionPanel";
import { KNOWLEDGE_RECOMMENDATION_UPDATING_LABEL } from "@/features/knowledge/knowledgeMessages";
import * as apiClient from "@/lib/apiClient";

const primaryEntry = {
  id: "entry-primary",
  status: "published" as const,
  title: "主知识条目",
  category: "测试",
  categorySlug: "test",
  style: "快节奏",
  summary: "主知识摘要",
  skillMdUri: "knowledge/test/entry-primary/structure-skill.md",
  structureJsonUri: "knowledge/test/entry-primary/video-structure.json",
  version: "1",
  entryKind: "structure" as const,
  createdAt: "2026-06-10T00:00:00Z",
  updatedAt: "2026-06-10T00:00:00Z",
};

function mockKnowledgePanelApis(delayMs = 0) {
  vi.spyOn(apiClient, "getKnowledgeSelection").mockImplementation(
    () =>
      new Promise((resolve) => {
        setTimeout(
          () =>
            resolve({
              data: {
                selection: {
                  projectId: "proj-1",
                  primaryEntryId: "entry-primary",
                  referenceEntryIds: [],
                  mode: "user_override",
                  appliedAsStructure: false,
                  updatedAt: "2026-06-10T00:00:00Z",
                  recommendationSnapshot: {
                    projectId: "proj-1",
                    suggestedPrimaryId: "entry-primary",
                    computedAt: "2026-06-10T00:00:00Z",
                    candidates: [
                      {
                        entryId: "entry-primary",
                        score: 0.8,
                        reasons: ["主题关键词匹配: 测试"],
                        entry: primaryEntry,
                      },
                    ],
                  },
                },
              },
              meta: { dataSource: "api" },
            }),
          delayMs,
        );
      }),
  );
  vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
    data: { samples: [] },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "getBrief").mockResolvedValue({
    data: {
      brief: {
        topic: "测试主题",
        sellingPoints: [],
        mustMention: [],
        avoidMention: [],
      },
    },
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "getKnowledgeEntry").mockResolvedValue({
    data: primaryEntry,
    meta: { dataSource: "api" },
  });
  vi.spyOn(apiClient, "recommendKnowledge").mockResolvedValue({
    data: {
      recommendation: {
        projectId: "proj-1",
        candidates: [],
        suggestedPrimaryId: "",
        computedAt: "2026-06-10T00:00:00Z",
      },
      selection: null,
    },
    meta: { dataSource: "api" },
  });
}

describe("KnowledgeSelectionPanel async refresh", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows updating label on refresh after initial load", async () => {
    mockKnowledgePanelApis(0);
    const panelRef = createRef<{ refresh: () => Promise<void> }>();
    render(<KnowledgeSelectionPanel ref={panelRef} projectId="proj-1" />);

    await waitFor(() => expect(panelRef.current).not.toBeNull());
    await act(async () => {
      await panelRef.current?.refresh();
    });

    mockKnowledgePanelApis(80);
    await act(async () => {
      void panelRef.current?.refresh();
    });

    await waitFor(() =>
      expect(screen.getByText(KNOWLEDGE_RECOMMENDATION_UPDATING_LABEL)).toBeInTheDocument(),
    );
  });

  it("does not call recommendKnowledge on initial load when selection is persisted", async () => {
    mockKnowledgePanelApis(0);
    render(<KnowledgeSelectionPanel projectId="proj-1" />);

    await waitFor(() => expect(screen.getByText("主知识条目")).toBeInTheDocument());

    expect(apiClient.recommendKnowledge).not.toHaveBeenCalled();
  });

  it("uses persisted snapshot when expanding without calling recommendKnowledge", async () => {
    mockKnowledgePanelApis(0);
    const user = userEvent.setup();
    render(<KnowledgeSelectionPanel projectId="proj-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "查看其他推荐（1）" })).toBeInTheDocument(),
    );
    expect(apiClient.recommendKnowledge).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "查看其他推荐（1）" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "当前主知识" })).toBeInTheDocument(),
    );
    expect(apiClient.recommendKnowledge).not.toHaveBeenCalled();
  });

  it("calls recommendKnowledge when expanding without persisted snapshot", async () => {
    vi.spyOn(apiClient, "getKnowledgeSelection").mockResolvedValue({
      data: {
        selection: {
          projectId: "proj-1",
          primaryEntryId: "entry-primary",
          referenceEntryIds: [],
          mode: "user_override",
          appliedAsStructure: false,
          updatedAt: "2026-06-10T00:00:00Z",
        },
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "listProjectSamples").mockResolvedValue({
      data: { samples: [] },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getBrief").mockResolvedValue({
      data: {
        brief: {
          topic: "测试主题",
          sellingPoints: [],
          mustMention: [],
          avoidMention: [],
        },
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "getKnowledgeEntry").mockResolvedValue({
      data: primaryEntry,
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "recommendKnowledge").mockResolvedValue({
      data: {
        recommendation: {
          projectId: "proj-1",
          candidates: [
            {
              entryId: "entry-primary",
              score: 0.8,
              reasons: ["主题关键词匹配: 测试"],
              entry: primaryEntry,
            },
          ],
          suggestedPrimaryId: "entry-primary",
          computedAt: "2026-06-10T00:00:00Z",
        },
        selection: null,
      },
      meta: { dataSource: "api" },
    });

    const user = userEvent.setup();
    render(<KnowledgeSelectionPanel projectId="proj-1" />);

    await waitFor(() => expect(screen.getByText("主知识条目")).toBeInTheDocument());
    expect(apiClient.recommendKnowledge).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "查看其他推荐" }));

    await waitFor(() => expect(apiClient.recommendKnowledge).toHaveBeenCalledTimes(1));
  });

  it("clears primary knowledge without triggering recommendKnowledge", async () => {
    mockKnowledgePanelApis(0);
    const updateSpy = vi.spyOn(apiClient, "updateKnowledgeSelection").mockResolvedValue({
      data: {
        selection: {
          projectId: "proj-1",
          primaryEntryId: null,
          referenceEntryIds: [],
          mode: "none",
          appliedAsStructure: false,
          updatedAt: "2026-06-10T00:00:00Z",
        },
      },
      meta: { dataSource: "api" },
    });
    const user = userEvent.setup();
    render(<KnowledgeSelectionPanel projectId="proj-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "取消主知识" })).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "取消主知识" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("proj-1", {
        primaryEntryId: null,
        referenceEntryIds: [],
        applyStructure: false,
      }),
    );
    expect(apiClient.recommendKnowledge).not.toHaveBeenCalled();
  });
});
