import { createRef } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeSelectionPanel } from "@/features/knowledge/KnowledgeSelectionPanel";
import { KNOWLEDGE_RECOMMENDATION_UPDATING_LABEL } from "@/features/knowledge/knowledgeMessages";
import * as apiClient from "@/lib/apiClient";

function mockKnowledgePanelApis(delayMs = 0) {
  vi.spyOn(apiClient, "getKnowledgeSelection").mockImplementation(
    () =>
      new Promise((resolve) => {
        setTimeout(
          () =>
            resolve({
              data: { selection: null },
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
});
