import type { TaskEvent } from "@videomaker/contracts";

import { fixtureTaskEvent } from "./task-event.fixture";

export const fixtureMaterialTaskEvent: TaskEvent = {
  ...fixtureTaskEvent,
  taskId: "task-demo-material",
  stage: "generating_image",
  progress: 72,
  message: "正在生成补全图片素材…",
  artifactRefs: [
    {
      id: "art-image-1",
      type: "image",
      uri: "/api/projects/proj-demo-001/media/file/generations/gen-demo-001/material/hook.png",
      createdAt: "2026-05-29T12:10:00.000Z",
    },
    {
      id: "art-json-2",
      type: "json",
      uri: "/api/projects/proj-demo-001/media/file/generations/gen-demo-001/material/manifest.json",
      createdAt: "2026-05-29T12:10:30.000Z",
    },
  ],
};
