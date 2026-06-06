import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssetInputPanel } from "@/features/project-input/AssetInputPanel";
import { BriefEditor } from "@/features/project-input/BriefEditor";
import { SampleInputPanel } from "@/features/project-input/SampleInputPanel";
import * as apiClient from "@/lib/apiClient";

describe("project input panels", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("uploads local sample with multipart file field", async () => {
    const upload = vi.spyOn(apiClient, "uploadSampleBatch").mockResolvedValue({
      data: {
        batchId: "batch-1",
        samples: [{ id: "sample-1", taskId: "task-1" }],
      },
      meta: { dataSource: "api" },
    });
    const user = userEvent.setup();
    const file = new File(["video"], "demo.mp4", { type: "video/mp4" });

    render(
      <SampleInputPanel
        projectId="proj-1"
        onTaskStarted={vi.fn()}
        onSampleReady={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/上传样例视频/i);
    await user.upload(input, file);

    await waitFor(() =>
      expect(upload).toHaveBeenCalledWith(
        "proj-1",
        expect.arrayContaining([
          expect.objectContaining({ name: "demo.mp4" }),
        ]),
      ),
    );
  });

  it("imports sample from URL via API (not yt-dlp)", async () => {
    const importUrl = vi
      .spyOn(apiClient, "importSampleFromUrl")
      .mockResolvedValue({
        data: { id: "sample-url", taskId: "task-url" },
        meta: { dataSource: "api" },
      });
    const user = userEvent.setup();

    render(
      <SampleInputPanel
        projectId="proj-1"
        onTaskStarted={vi.fn()}
        onSampleReady={vi.fn()}
      />,
    );

    await user.click(screen.getAllByRole("tab", { name: /URL 导入/i })[0]!);
    await user.type(
      screen.getAllByLabelText(/视频页面 URL/i)[0]!,
      "https://example.com/watch?v=1",
    );
    await user.click(screen.getByRole("button", { name: /开始 URL 导入/i }));

    await waitFor(() =>
      expect(importUrl).toHaveBeenCalledWith("proj-1", {
        url: "https://example.com/watch?v=1",
      }),
    );
  });

  it("rejects invalid URLs before API call", async () => {
    const importUrl = vi.spyOn(apiClient, "importSampleFromUrl");
    const user = userEvent.setup();

    render(
      <SampleInputPanel
        projectId="proj-1"
        onTaskStarted={vi.fn()}
        onSampleReady={vi.fn()}
      />,
    );

    await user.click(screen.getAllByRole("tab", { name: /URL 导入/i })[0]!);
    const urlInput = screen.getAllByLabelText(/视频页面 URL/i)[0]!;
    await user.clear(urlInput);
    await user.type(urlInput, "not-a-url");
    await user.click(screen.getByRole("button", { name: /开始 URL 导入/i }));

    expect(importUrl).not.toHaveBeenCalled();
    expect(screen.getAllByRole("status")[0]).toHaveTextContent(/链接/);
  });

  it("uploads assets with image/video/text accept types", () => {
    render(<AssetInputPanel projectId="proj-1" assets={[]} />);
    const input = screen.getByLabelText(/上传用户素材/i);
    expect(input.getAttribute("accept")).toContain("image/*");
    expect(input.getAttribute("accept")).toContain("video/*");
    expect(input.getAttribute("accept")).toContain(".txt");
    expect(input).toHaveAttribute("multiple");
  });

  it("submits structured brief matching UserBriefRequest v2", async () => {
    const save = vi.spyOn(apiClient, "saveBrief").mockResolvedValue({
      data: { ok: true },
      meta: { dataSource: "api" },
    });
    const user = userEvent.setup();

    render(<BriefEditor projectId="proj-1" />);

    await user.selectOptions(screen.getByLabelText(/^内容类型$/i), "product_commerce");
    await user.type(screen.getByLabelText(/^主题$/i), "夏季防晒");
    await user.type(screen.getByLabelText(/^产品名$/i), "清爽喷雾");
    await user.type(screen.getByLabelText(/^创作目标$/i), "促进转化");
    await user.type(screen.getByLabelText(/^卖点/i), "轻薄不黏\n12小时防护");
    await user.click(screen.getByRole("button", { name: /保存 Brief/i }));

    await waitFor(() =>
      expect(save).toHaveBeenCalledWith("proj-1", {
        contentCategory: "product_commerce",
        topic: "夏季防晒",
        creativeGoal: "促进转化",
        subjectName: "清爽喷雾",
        productName: "清爽喷雾",
        keyPoints: ["轻薄不黏", "12小时防护"],
        sellingPoints: ["轻薄不黏", "12小时防护"],
        mustMention: [],
        avoidMention: [],
      }),
    );
  });
});
