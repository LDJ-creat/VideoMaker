import {
  fixtureAgentRuns,
  fixtureEditIntent,
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
  fixtureModelGatewayStatus,
  fixtureMultiVariantGenerations,
  fixtureProject,
  fixtureReviseGenerationResponse,
  fixtureTaskEvent,
  fixtureVideoStructure,
} from "@/fixtures";

type FixtureResult = {
  status: number;
  body: unknown;
};

function parseGenerationPlanVariants(requestBody?: string): string[] {
  if (!requestBody) {
    return fixtureMultiVariantGenerations.map((entry) => entry.variant);
  }
  try {
    const parsed = JSON.parse(requestBody) as { variants?: string[] };
    if (parsed.variants?.length) {
      return parsed.variants;
    }
  } catch {
    /* ignore */
  }
  return fixtureMultiVariantGenerations.map((entry) => entry.variant);
}

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
    method === "GET" &&
    segments[0] === "settings" &&
    segments[1] === "model-gateway"
  ) {
    return {
      status: 200,
      body: fixtureModelGatewayStatus,
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
    const requestedVariants = parseGenerationPlanVariants(requestBody);
    const generations = fixtureMultiVariantGenerations.filter((entry) =>
      requestedVariants.includes(entry.variant),
    );
    return {
      status: 201,
      body: { generations },
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
      body: {
        generations: fixtureMultiVariantGenerations.map((entry) => ({
          generationId: entry.generationId,
          variant: entry.variant,
          plan: {
            ...(entry.variant === "high_click"
              ? fixtureGenerationPlanHighClick
              : fixtureGenerationPlan),
            id: entry.generationId,
            variant: entry.variant,
            gapReport: fixtureGapReport,
          },
        })),
      },
    };
  }

  if (method === "GET" && segments[0] === "generations" && segments.length === 2) {
    const generationId = segments[1];
    const plan =
      generationId === fixtureGenerationPlanHighClick.id
        ? fixtureGenerationPlanHighClick
        : { ...fixtureGenerationPlan, id: generationId };
    return {
      status: 200,
      body: { ...plan, gapReport: fixtureGapReport },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "generations" &&
    segments[2] === "revise"
  ) {
    return {
      status: 202,
      body: {
        ...fixtureReviseGenerationResponse,
        sourceGenerationId: segments[1],
        intents: fixtureEditIntent.intents,
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "generations" &&
    segments[2] === "agent-runs"
  ) {
    return {
      status: 200,
      body: {
        runs: fixtureAgentRuns.map((run) => ({
          ...run,
          generationId: segments[1],
        })),
      },
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
