import { describe, expect, it } from "vitest";

import {
  batchProgressHeadline,
  buildRecentSampleAnalysisTasks,
  countBatchProgress,
  summarizeBatchProgress,
} from "@/lib/batchAnalysisProgress";
import { fixtureTaskEvent } from "@/fixtures";

describe("batchAnalysisProgress", () => {
  it("builds recent analysis tasks from in-flight sample summaries only", () => {
    const tasks = buildRecentSampleAnalysisTasks([
      { id: "a", taskId: "task-a", status: "analyzing", sourceKind: "local" },
      { id: "b", taskId: "task-b", status: "analyzed", sourceKind: "local" },
      { id: "c", taskId: null, status: "uploaded", sourceKind: "local" },
    ]);
    expect(tasks).toEqual([{ sampleId: "a", taskId: "task-a" }]);
  });

  it("counts queued and running tasks separately", () => {
    const counts = countBatchProgress(
      [{ taskId: "a" }, { taskId: "b" }, { taskId: "c" }],
      {
        a: { ...fixtureTaskEvent, taskId: "a", status: "running" },
        b: { ...fixtureTaskEvent, taskId: "b", status: "queued" },
        c: { ...fixtureTaskEvent, taskId: "c", status: "succeeded", progress: 100 },
      },
    );

    expect(counts.running).toBe(1);
    expect(counts.queued).toBe(1);
    expect(counts.succeeded).toBe(1);
    expect(summarizeBatchProgress(counts)).toContain("排队");
    expect(batchProgressHeadline(counts)).toBe("批量样例分析进行中");
  });
});
