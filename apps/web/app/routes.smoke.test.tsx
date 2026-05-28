import { describe, expect, it } from "vitest";

import ProjectsPage from "@/app/projects/page";
import { ProjectWorkbench } from "@/features/workbench/ProjectWorkbench";

describe("app route components", () => {
  it("imports projects list page", () => {
    expect(ProjectsPage).toBeDefined();
  });

  it("imports project workbench", () => {
    expect(ProjectWorkbench).toBeDefined();
  });
});
