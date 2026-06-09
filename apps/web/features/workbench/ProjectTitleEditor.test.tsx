import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTitleEditor } from "@/features/workbench/ProjectTitleEditor";
import * as apiClient from "@/lib/apiClient";

function ControlledTitleEditor() {
  const [name, setName] = useState("旧名称");
  return (
    <ProjectTitleEditor
      projectId="proj-1"
      name={name}
      onNameChange={setName}
    />
  );
}

describe("ProjectTitleEditor", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("saves a renamed project title", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiClient, "updateProject").mockResolvedValue({
      data: {
        id: "proj-1",
        name: "新项目名称",
        createdAt: "2026-06-07T11:52:06.877595Z",
      },
      meta: { dataSource: "api" },
    });

    render(<ControlledTitleEditor />);

    await user.click(screen.getByRole("button", { name: "编辑项目名称" }));
    const input = screen.getByRole("textbox", { name: "项目名称" });
    await user.clear(input);
    await user.type(input, "新项目名称");
    await user.click(screen.getByRole("button", { name: "保存项目名称" }));

    await waitFor(() => {
      expect(apiClient.updateProject).toHaveBeenCalledWith("proj-1", {
        name: "新项目名称",
      });
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        "新项目名称",
      );
    });
  });
});
