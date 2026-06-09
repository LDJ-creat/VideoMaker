import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProjectsPage from "@/app/projects/page";
import * as apiClient from "@/lib/apiClient";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("ProjectsPage home redesign", () => {
  beforeEach(() => {
    push.mockReset();
    vi.spyOn(apiClient, "listProjects").mockResolvedValue({
      data: { projects: [] },
      meta: { dataSource: "fixture" },
    });
    vi.spyOn(apiClient, "listKnowledgeCategories").mockResolvedValue({
      data: { categories: [] },
      meta: { dataSource: "api" },
    });
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders hero copy and project name input", async () => {
    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByText("暂无视频项目")).toBeInTheDocument(),
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /让爆款视频的结构/,
    );
    expect(
      screen.getByPlaceholderText("为新项目命名，如：夏季防晒喷雾"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始创建/ })).toBeInTheDocument();
  });

  it("renders workflow strip steps", async () => {
    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByText("暂无视频项目")).toBeInTheDocument(),
    );

    const workflow = screen.getByLabelText("创作流程");
    expect(within(workflow).getByText("样例视频")).toBeInTheDocument();
    expect(within(workflow).getByText("结构提取")).toBeInTheDocument();
    expect(within(workflow).getByText("素材匹配")).toBeInTheDocument();
    expect(within(workflow).getByText("生成预览")).toBeInTheDocument();
  });

  it("links project cards to workbench", async () => {
    vi.spyOn(apiClient, "listProjects").mockResolvedValue({
      data: {
        projects: [
          {
            id: "proj-001",
            name: "夏季防晒喷雾",
            createdAt: "2026-06-01T10:00:00.000Z",
          },
        ],
      },
      meta: { dataSource: "api" },
    });

    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByText("夏季防晒喷雾")).toBeInTheDocument(),
    );

    const link = screen.getByRole("link", { name: /夏季防晒喷雾/ });
    expect(link).toHaveAttribute("href", "/projects/proj-001");
    expect(screen.getByText("新建项目")).toBeInTheDocument();
  });

  it("redirects to workbench after creating a project", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "createProject").mockResolvedValue({
      data: {
        id: "proj-new",
        name: "夏季防晒喷雾",
        createdAt: "2026-06-05T10:00:00.000Z",
      },
      meta: { dataSource: "api" },
    });

    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByText("暂无视频项目")).toBeInTheDocument(),
    );

    await user.type(
      screen.getByPlaceholderText("为新项目命名，如：夏季防晒喷雾"),
      "夏季防晒喷雾",
    );
    await user.click(screen.getByRole("button", { name: /开始创建/ }));

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/projects/proj-new"),
    );
  });

  it("renders template category section when categories exist", async () => {
    vi.spyOn(apiClient, "listKnowledgeCategories").mockResolvedValue({
      data: {
        categories: [
          {
            category: "美妆护肤",
            categorySlug: "beauty-skincare",
            entryCount: 2,
            summary: "种草结构参考",
            slotPatterns: ["hook → demo → cta"],
            updatedAt: "2026-06-09T10:00:00.000Z",
            coverUrl: "/cover.jpg",
          },
        ],
      },
      meta: { dataSource: "api" },
    });

    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByTestId("template-category-section")).toBeInTheDocument(),
    );

    expect(screen.getByText("结构模板库")).toBeInTheDocument();
    expect(screen.getByTestId("template-category-card")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /美妆护肤/ })).toHaveAttribute(
      "href",
      "/templates/beauty-skincare",
    );
  });

  it("opens delete confirmation for project cards", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "listProjects").mockResolvedValue({
      data: {
        projects: [
          {
            id: "proj-001",
            name: "夏季防晒喷雾",
            createdAt: "2026-06-01T10:00:00.000Z",
          },
        ],
      },
      meta: { dataSource: "api" },
    });
    vi.spyOn(apiClient, "deleteProject").mockResolvedValue({
      data: undefined,
      meta: { dataSource: "api" },
    });

    render(<ProjectsPage />);

    await waitFor(() =>
      expect(screen.getByText("夏季防晒喷雾")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "删除项目 夏季防晒喷雾" }));

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText(/将永久删除「夏季防晒喷雾」/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "删除项目" }));

    await waitFor(() =>
      expect(apiClient.deleteProject).toHaveBeenCalledWith("proj-001"),
    );
    expect(screen.queryByText("夏季防晒喷雾")).not.toBeInTheDocument();
  });
});