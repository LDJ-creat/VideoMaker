import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProjectCoverPlaceholder } from "@/components/home/project-cover-placeholder";
import { TemplateCoverPlaceholder } from "@/components/home/template-cover-placeholder";
import { TemplateCategoryCard } from "@/components/home/template-category-card";
import { ProjectCard } from "@/components/home/project-card";
import { placeholderDisplayName } from "@/lib/coverPlaceholders";

describe("cover placeholders", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders template placeholder with truncated category name and slot ghost", () => {
    render(
      <TemplateCoverPlaceholder
        category="美妆护肤"
        slotPattern="hook → problem → cta"
      />,
    );

    expect(screen.getByTestId("template-cover-placeholder")).toBeInTheDocument();
    expect(screen.getByText("美妆护肤")).toBeInTheDocument();
    expect(screen.getByText("hook → problem → cta")).toBeInTheDocument();
    expect(screen.getByText("待收录样例封面")).toBeInTheDocument();
  });

  it("caps template placeholder name at five characters", () => {
    render(
      <TemplateCoverPlaceholder
        category="夏季防晒喷雾"
        slotPattern="hook → cta"
      />,
    );

    expect(screen.getByText("夏季防晒喷")).toBeInTheDocument();
    expect(screen.queryByText("夏季防晒喷雾")).not.toBeInTheDocument();
  });

  it("renders project placeholder with truncated project name", () => {
    render(
      <ProjectCoverPlaceholder
        projectName="为人处世"
        gradient="from-amber-100 to-yellow-100"
      />,
    );

    expect(screen.getByTestId("project-cover-placeholder")).toBeInTheDocument();
    expect(screen.getByText("为人处世")).toBeInTheDocument();
    expect(screen.getByText("等待样例或成片")).toBeInTheDocument();
  });

  it("placeholderDisplayName respects max length", () => {
    expect(placeholderDisplayName("夏季防晒喷雾")).toBe("夏季防晒喷");
    expect(placeholderDisplayName("教育")).toBe("教育");
  });

  it("uses template placeholder when category has no coverUrl", () => {
    render(
      <TemplateCategoryCard
        category={{
          category: "教育",
          categorySlug: "education",
          entryCount: 1,
          summary: "测试摘要",
          slotPatterns: ["hook → cta"],
          updatedAt: "2026-06-09T00:00:00Z",
          coverUrl: null,
        }}
      />,
    );

    const placeholder = screen.getByTestId("template-cover-placeholder");
    expect(placeholder).toHaveTextContent("教育");
    expect(screen.queryByTestId("project-cover-placeholder")).not.toBeInTheDocument();
  });

  it("uses project placeholder when project has no coverUrl", () => {
    render(
      <ProjectCard
        project={{
          id: "proj-1",
          name: "好物推荐",
          createdAt: "2026-06-01T10:00:00.000Z",
        }}
        onDelete={() => undefined}
      />,
    );

    const placeholder = screen.getByTestId("project-cover-placeholder");
    expect(placeholder).toHaveTextContent("好物推荐");
    expect(screen.queryByTestId("template-cover-placeholder")).not.toBeInTheDocument();
  });
});
