import { cleanup, render, screen } from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { afterEach, describe, expect, it, vi } from "vitest";



import { SceneRevisePanel } from "@/features/nl-revise/SceneRevisePanel";



describe("SceneRevisePanel", () => {

  afterEach(() => {

    cleanup();

  });



  it("submits edit mode payload with instruction", async () => {

    const user = userEvent.setup();

    const onSubmit = vi.fn().mockResolvedValue(undefined);



    render(

      <SceneRevisePanel

        sceneId="scene-1"

        slotId="slot-1"

        index={0}

        chainKind="stock_then_hf"

        onSubmit={onSubmit}

      />,

    );



    await user.type(

      screen.getByLabelText("修改说明（必填）"),

      "字幕居中，动效更大",

    );

    await user.click(screen.getByTestId("scene-revise-submit-scene-1"));



    expect(onSubmit).toHaveBeenCalledWith({

      sceneId: "scene-1",

      slotId: "slot-1",

      mode: "edit",

      instruction: "字幕居中，动效更大",

    });

  });



  it("submits full mode payload", async () => {

    const user = userEvent.setup();

    const onSubmit = vi.fn().mockResolvedValue(undefined);



    render(

      <SceneRevisePanel

        sceneId="scene-2"

        slotId="slot-2"

        index={1}

        onSubmit={onSubmit}

      />,

    );



    await user.click(screen.getByLabelText("完全重生成"));

    await user.type(screen.getByLabelText("修改说明（必填）"), "改成赛博朋克风格");

    await user.click(screen.getByTestId("scene-revise-submit-scene-2"));



    expect(onSubmit).toHaveBeenCalledWith({

      sceneId: "scene-2",

      slotId: "slot-2",

      mode: "full",

      instruction: "改成赛博朋克风格",

    });

  });



  it("disables submit when instruction is empty", () => {

    render(

      <SceneRevisePanel

        sceneId="scene-3"

        slotId="slot-3"

        index={2}

        onSubmit={vi.fn()}

      />,

    );



    expect(screen.getByTestId("scene-revise-submit-scene-3")).toBeDisabled();

  });

});

