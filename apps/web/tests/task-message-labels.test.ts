import { describe, expect, it } from "vitest";

import { formatTaskMessage } from "@/lib/taskMessageLabels";

describe("taskMessageLabels", () => {
  it("maps common backend messages to Chinese", () => {
    expect(formatTaskMessage("Queued sample analysis")).toBe("排队等待开始分析");
    expect(formatTaskMessage("Sample analysis and structure extraction completed")).toBe(
      "样例分析与结构提取已完成",
    );
  });
});
