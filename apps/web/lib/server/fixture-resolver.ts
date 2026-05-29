import {
  fixtureGenerationPlan,
  fixtureGapReport,
  fixtureProject,
  fixtureTaskEvent,
  fixtureVideoStructure,
} from "@/fixtures";

type FixtureResult = {
  status: number;
  body: unknown;
};

export function resolveFixture(
  method: string,
  apiPath: string,
  requestBody?: string,
): FixtureResult | null {
  const segments = apiPath.split("/").filter(Boolean);

  if (method === "POST" && apiPath === "projects") {
    let name = fixtureProject.name;
    if (requestBody) {
      try {
        const parsed = JSON.parse(requestBody) as { name?: string };
        if (parsed.name) name = parsed.name;
      } catch {
        /* ignore */
      }
    }
    return {
      status: 201,
      body: { ...fixtureProject, name, id: `proj-fixture-${Date.now()}` },
    };
  }

  if (method === "GET" && apiPath === "projects") {
    return {
      status: 200,
      body: { projects: [fixtureProject] },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments.length === 3
  ) {
    return {
      status: 200,
      body: {
        samples: [
          {
            id: "sample-fixture-local",
            status: "uploaded",
            sourceKind: "local",
            hasStructure: false,
            previewUrl: null,
            fileName: "demo.mp4",
          },
        ],
      },
    };
  }

  if (method === "GET" && segments[0] === "projects" && segments.length === 2) {
    return {
      status: 200,
      body: { ...fixtureProject, id: segments[1] },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "active"
  ) {
    return {
      status: 200,
      body: {
        id: "sample-fixture-local",
        status: "uploaded",
        sourceKind: "local",
        hasStructure: false,
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "upload"
  ) {
    return {
      status: 201,
      body: { id: "sample-fixture-local", taskId: fixtureTaskEvent.taskId },
    };
  }

  if (method === "GET" && segments[0] === "settings" && segments[1] === "cookies") {
    return {
      status: 200,
      body: { configured: false, updatedAt: null, domains: [] },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "settings" &&
    segments[1] === "cookies" &&
    segments[2] === "upload"
  ) {
    return {
      status: 201,
      body: { ok: true, configured: true, domains: [".example.com"], mode: "merge" },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "from-url"
  ) {
    return {
      status: 201,
      body: { id: "sample-fixture-url", taskId: fixtureTaskEvent.taskId },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "assets" &&
    segments[3] === "upload"
  ) {
    return { status: 201, body: { id: `asset-fixture-${Date.now()}` } };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "brief"
  ) {
    return { status: 200, body: { ok: true } };
  }

  if (
    method === "POST" &&
    segments[0] === "samples" &&
    segments[2] === "analyze"
  ) {
    return { status: 200, body: { taskId: fixtureTaskEvent.taskId } };
  }

  if (method === "GET" && segments[0] === "tasks" && segments.length === 2) {
    return {
      status: 200,
      body: { ...fixtureTaskEvent, taskId: segments[1] },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "generation-plan"
  ) {
    return {
      status: 201,
      body: {
        generationId: fixtureGenerationPlan.id,
        taskId: fixtureTaskEvent.taskId,
        gapReport: fixtureGapReport,
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "generations" &&
    segments[3] === "latest"
  ) {
    return {
      status: 200,
      body: { ...fixtureGenerationPlan, gapReport: fixtureGapReport },
    };
  }

  if (method === "GET" && segments[0] === "generations" && segments.length === 2) {
    return {
      status: 200,
      body: { ...fixtureGenerationPlan, id: segments[1], gapReport: fixtureGapReport },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "samples" &&
    segments[2] === "structure"
  ) {
    return {
      status: 200,
      body: { ...fixtureVideoStructure, sourceVideoId: segments[1] },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "samples" &&
    segments[2] === "analysis"
  ) {
    return {
      status: 200,
      body: { ...fixtureVideoStructure, sourceVideoId: segments[1] },
    };
  }

  return null;
}
