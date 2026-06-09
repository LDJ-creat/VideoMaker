import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MasterNarrationPanel } from "@/features/master-narration/MasterNarrationPanel";
import {
  fixtureGenerationPlan,
  fixtureGapReport,
  fixtureVideoStructure,
} from "@/fixtures";

describe("MasterNarrationPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders full breakdown with master narration and scene segments", () => {
    render(
      <MasterNarrationPanel
        plan={fixtureGenerationPlan}
        structure={fixtureVideoStructure}
        gapReport={fixtureGapReport}
      />,
    );

    expect(screen.getByText("全片拆解")).toBeInTheDocument();
    expect(screen.getByText("全片口播稿")).toBeInTheDocument();
    expect(screen.getByTestId("master-narration-text")).toHaveTextContent(
      fixtureGenerationPlan.masterNarration,
    );
    expect(screen.getByTestId("narration-scene-scene-1")).toHaveTextContent(
      "夏天出门还在被晒黑？",
    );
    expect(screen.getByText("槽位拆解")).toBeInTheDocument();
    expect(screen.getAllByText("结构意图").length).toBeGreaterThan(0);
  });

  it("derives master text from storyboard when field is empty", () => {
    const plan = {
      ...fixtureGenerationPlan,
      masterNarration: "",
    };
    render(<MasterNarrationPanel plan={plan} />);

    expect(screen.getByTestId("master-narration-text")).toHaveTextContent(
      "夏天出门还在被晒黑？轻薄 SPF50+，一喷成膜不黏腻限时第二件半价，评论区领券",
    );
    expect(
      screen.getByText(/未单独保存 masterNarration/i),
    ).toBeInTheDocument();
  });
});
