import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CategoryTemplatePage from "@/app/templates/[categorySlug]/page";
import * as apiClient from "@/lib/apiClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useParams: () => ({ categorySlug: "beauty-skincare" }),
}));

const entryA: apiClient.KnowledgeCategoryEntryCard = {
  entryId: "entry-a",
  title: "样例 A",
  summary: "summary a",
  style: "种草",
  slotPattern: "hook → demo → cta",
  importable: true,
  previewUrl: "/preview-a.mp4",
};

const entryB: apiClient.KnowledgeCategoryEntryCard = {
  entryId: "entry-b",
  title: "样例 B",
  summary: "summary b",
  style: "测评",
  slotPattern: "hook → proof → cta",
  importable: true,
};

const entryC: apiClient.KnowledgeCategoryEntryCard = {
  entryId: "entry-c",
  title: "样例 C",
  summary: "summary c",
  style: "剧情",
  slotPattern: "story → reveal → cta",
  importable: true,
};

describe("CategoryTemplatePage", () => {
  beforeEach(() => {
    push.mockReset();
    vi.spyOn(apiClient, "getKnowledgeCategory").mockResolvedValue({
      data: {
        category: "美妆护肤",
        categorySlug: "beauty-skincare",
        entries: [entryA, entryB, entryC],
      },
      meta: { dataSource: "api" },
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders category hero and entry cards", async () => {
    render(<CategoryTemplatePage />);

    await waitFor(() =>
      expect(screen.getByTestId("category-template-page")).toBeInTheDocument(),
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("美妆护肤");
    expect(screen.getAllByTestId("template-entry-card")).toHaveLength(3);
  });

  it("enforces at most two reference entries", async () => {
    const user = userEvent.setup();
    render(<CategoryTemplatePage />);

    await waitFor(() =>
      expect(screen.getAllByTestId("template-entry-card")).toHaveLength(3),
    );

    const cards = screen.getAllByTestId("template-entry-card");

    await user.click(within(cards[0]!).getByRole("button", { name: "设为主样例" }));
    await user.click(within(cards[1]!).getByRole("button", { name: "加为参考" }));
    await user.click(within(cards[2]!).getByRole("button", { name: "加为参考" }));

    expect(within(cards[1]!).getByText("参考 1")).toBeInTheDocument();
    expect(within(cards[2]!).getByText("参考 2")).toBeInTheDocument();

    const addButtons = screen.getAllByRole("button", { name: "加为参考" });
    for (const button of addButtons) {
      expect(button).toBeDisabled();
    }
  });

  it("creates project and redirects to workbench", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "createProjectFromKnowledgeTemplate").mockResolvedValue({
      data: {
        project: {
          id: "proj-template",
          name: "美妆护肤 · 06-09",
          createdAt: "2026-06-09T10:00:00.000Z",
        },
        importedSamples: [{ sampleId: "sample-a", entryId: "entry-a" }],
        sampleSelection: {
          projectId: "proj-template",
          primarySampleId: "sample-a",
          referenceSampleIds: [],
          mode: "user_override",
          updatedAt: "2026-06-09T10:00:00.000Z",
        },
        knowledgeSelection: {
          projectId: "proj-template",
          primaryEntryId: "entry-a",
          referenceEntryIds: [],
          appliedAsStructure: false,
          mode: "user_override",
          updatedAt: "2026-06-09T10:00:00.000Z",
        },
      },
      meta: { dataSource: "api" },
    });

    render(<CategoryTemplatePage />);

    await waitFor(() =>
      expect(screen.getAllByTestId("template-entry-card")).toHaveLength(3),
    );

    const cards = screen.getAllByTestId("template-entry-card");
    await user.click(within(cards[0]!).getByRole("button", { name: "设为主样例" }));

    const dock = screen.getByTestId("template-selection-dock-desktop");
    await user.click(within(dock).getByTestId("template-create-project-button"));

    await waitFor(() =>
      expect(apiClient.createProjectFromKnowledgeTemplate).toHaveBeenCalledWith({
        name: expect.stringContaining("美妆护肤"),
        categorySlug: "beauty-skincare",
        primaryEntryId: "entry-a",
        referenceEntryIds: [],
      }),
    );
    expect(push).toHaveBeenCalledWith("/projects/proj-template");
  });
});
