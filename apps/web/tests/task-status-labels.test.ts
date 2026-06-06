import { describe, expect, it } from "vitest";

import { getTaskStatusLabel } from "@/lib/taskStatusLabels";

describe("taskStatusLabels", () => {
  it("maps task statuses to Chinese labels", () => {
    expect(getTaskStatusLabel("queued")).toBe("排队中");
    expect(getTaskStatusLabel("succeeded")).toBe("已完成");
  });
});
