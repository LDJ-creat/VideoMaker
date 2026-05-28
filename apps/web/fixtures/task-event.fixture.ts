import type { TaskEvent } from "@videomaker/contracts";

export const fixtureTaskEvent: TaskEvent = {
  taskId: "task-demo-001",
  status: "running",
  stage: "extracting_structure",
  progress: 62,
  message: "正在从样例镜头中提取结构槽位…",
  updatedAt: "2026-05-27T10:05:00.000Z",
  artifactRefs: [
    {
      id: "art-json-1",
      type: "json",
      uri: "storage/projects/proj-demo-001/analysis.json",
      createdAt: "2026-05-27T10:04:30.000Z",
    },
  ],
};
