import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { TaskArtifactPreview } from "@/features/tasks/TaskArtifactPreview";
import { fixtureMaterialTaskEvent } from "@/fixtures";

describe("TaskArtifactPreview", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders deduped artifacts and auto-expands for material stages", () => {
    render(
      <TaskArtifactPreview
        projectId="proj-demo-001"
        artifactRefs={fixtureMaterialTaskEvent.artifactRefs}
        stage="generating_image"
      />,
    );

    expect(screen.getByTestId("task-artifact-preview")).toBeInTheDocument();
    expect(screen.getByText("阶段产物")).toBeInTheDocument();
    expect(screen.getByText("art-image-1")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute(
      "src",
      "/api/projects/proj-demo-001/media/file/generations/gen-demo-001/material/hook.png",
    );
  });

  it("toggles expanded state", async () => {
    const user = userEvent.setup();
    render(
      <TaskArtifactPreview
        projectId="proj-demo-001"
        artifactRefs={fixtureMaterialTaskEvent.artifactRefs}
        stage="generating_image"
      />,
    );

    const panel = screen.getByTestId("task-artifact-preview");
    expect(within(panel).getByRole("img")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: /阶段产物/i }));
    expect(within(panel).queryByRole("img")).not.toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: /阶段产物/i }));
    expect(within(panel).getByRole("img")).toBeInTheDocument();
  });
});
