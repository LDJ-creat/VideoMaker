import {
  fixtureAgentRuns,
  fixtureEditIntent,
  fixtureGapReport,
  fixtureGenerationPlan,
  fixtureGenerationPlanHighClick,
  fixtureModelGatewayStatus,
  fixtureMultiVariantGenerations,
  fixtureProject,
  fixtureGenerationPlanRevised,
  fixtureReviseGenerationResponse,
  fixtureRevisePlan,
  fixtureReviseSession,
  fixtureReviseTaskEvent,
  fixtureMaterialTaskEvent,
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
    segments[0] === "settings" &&
    segments[1] === "model-gateway"
  ) {
    if (method === "GET") {
      return {
        status: 200,
        body: fixtureModelGatewayStatus,
      };
    }
    if (method === "PUT") {
      return {
        status: 200,
        body: fixtureModelGatewayStatus,
      };
    }
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
    const taskId = segments[1];
    const multiTaskIds = new Set(
      fixtureMultiVariantGenerations.map((entry) => entry.taskId),
    );
    let body: typeof fixtureTaskEvent = { ...fixtureTaskEvent, taskId };
    if (taskId === fixtureReviseTaskEvent.taskId) {
      body = fixtureReviseTaskEvent;
    } else if (multiTaskIds.has(taskId)) {
      body = { ...fixtureMaterialTaskEvent, taskId };
    }
    return {
      status: 200,
      body,
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "upload-batch"
  ) {
    return {
      status: 201,
      body: {
        batchId: "batch-fixture-001",
        samples: [
          { id: "sample-fixture-local", taskId: null },
          { id: "sample-fixture-local-2", taskId: null },
        ],
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "analyze-batch"
  ) {
    return {
      status: 200,
      body: {
        tasks: [
          { sampleId: "sample-fixture-local", taskId: fixtureTaskEvent.taskId },
        ],
        maxConcurrent: 2,
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "upload-batches"
  ) {
    return {
      status: 200,
      body: {
        batches: [
          {
            id: "batch-fixture-001",
            projectId: segments[1],
            status: "uploading",
            sampleIds: ["sample-fixture-local"],
            createdAt: "2026-06-04T00:00:00Z",
            updatedAt: "2026-06-04T00:00:00Z",
            samples: [
              {
                id: "sample-fixture-local",
                status: "queued",
                hasStructure: false,
                uploadBatchId: "batch-fixture-001",
              },
            ],
          },
        ],
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "selection"
  ) {
    return {
      status: 200,
      body: {
        selection: {
          projectId: segments[1],
          primarySampleId: "sample-fixture-local",
          referenceSampleIds: [],
          activeUploadBatchId: "batch-fixture-001",
          mode: "auto",
          updatedAt: "2026-06-04T00:00:00Z",
        },
      },
    };
  }

  if (
    method === "PUT" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "selection"
  ) {
    let primarySampleId = "sample-fixture-local";
    let referenceSampleIds: string[] = [];
    if (requestBody) {
      try {
        const parsed = JSON.parse(requestBody) as {
          primarySampleId?: string;
          referenceSampleIds?: string[];
        };
        if (parsed.primarySampleId) primarySampleId = parsed.primarySampleId;
        if (parsed.referenceSampleIds) referenceSampleIds = parsed.referenceSampleIds;
      } catch {
        /* ignore */
      }
    }
    return {
      status: 200,
      body: {
        selection: {
          projectId: segments[1],
          primarySampleId,
          referenceSampleIds,
          activeUploadBatchId: "batch-fixture-001",
          mode: "user_override",
          updatedAt: "2026-06-04T00:00:00Z",
        },
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "selection" &&
    segments[4] === "reset"
  ) {
    return {
      status: 200,
      body: {
        selection: {
          projectId: segments[1],
          primarySampleId: "sample-fixture-local",
          referenceSampleIds: [],
          activeUploadBatchId: "batch-fixture-001",
          mode: "auto",
          updatedAt: "2026-06-04T00:00:00Z",
        },
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "projects" &&
    segments[2] === "samples" &&
    segments[3] === "recommend"
  ) {
    return {
      status: 200,
      body: {
        recommendation: {
          projectId: segments[1],
          suggestedPrimaryId: "sample-fixture-local",
          suggestedReferenceIds: [],
          candidates: [
            {
              sampleId: "sample-fixture-local",
              score: 1,
              reasons: ["fixture"],
              hasStructure: true,
              status: "analyzed",
            },
          ],
          computedAt: "2026-06-04T00:00:00Z",
        },
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "generation-runs" &&
    segments.length === 3
  ) {
    return {
      status: 200,
      body: {
        runs: [
          {
            id: "run-fixture-001",
            projectId: segments[1],
            status: "completed",
            variantIds: ["high_click", "high_conversion"],
            generationIds: fixtureMultiVariantGenerations.map(
              (entry) => entry.generationId,
            ),
            synthesizedStructureId: "synthesized-run-fixture-001",
            provenanceId: null,
            createdAt: "2026-06-04T00:00:00Z",
            updatedAt: "2026-06-04T00:00:00Z",
          },
        ],
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "projects" &&
    segments[2] === "generation-runs" &&
    segments.length === 4
  ) {
    return {
      status: 200,
      body: {
        run: {
          id: segments[3],
          projectId: segments[1],
          status: "completed",
          variantIds: ["high_click", "high_conversion"],
          generationIds: fixtureMultiVariantGenerations.map(
            (entry) => entry.generationId,
          ),
          synthesizedStructureId: `synthesized-${segments[3]}`,
          provenanceId: null,
          createdAt: "2026-06-04T00:00:00Z",
          updatedAt: "2026-06-04T00:00:00Z",
        },
        generations: fixtureMultiVariantGenerations.map((entry) => ({
          generationId: entry.generationId,
          variant: entry.variant,
          status: "succeeded",
          plan: {
            ...(entry.variant === "high_click"
              ? fixtureGenerationPlanHighClick
              : fixtureGenerationPlan),
            id: entry.generationId,
            variant: entry.variant,
            gapReport: fixtureGapReport,
          },
        })),
        provenance: null,
      },
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
      body: {
        generationRunId: `run-fixture-${Date.now()}`,
        generations,
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
      generationId === fixtureGenerationPlanRevised.id
        ? fixtureGenerationPlanRevised
        : generationId === fixtureGenerationPlanHighClick.id
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
    segments[2] === "revise" &&
    segments[3] === "plan"
  ) {
    return {
      status: 200,
      body: {
        plan: { ...fixtureRevisePlan, sourceGenerationId: segments[1] },
        sessionId: fixtureReviseSession.sessionId,
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "generations" &&
    segments[2] === "revise" &&
    segments[3] === "execute"
  ) {
    return {
      status: 202,
      body: {
        sourceGenerationId: segments[1],
        generationId: segments[1],
        taskId: "task-fixture-revise-patch",
        executionMode: "in_place",
        plan: { ...fixtureRevisePlan, status: "executed" },
      },
    };
  }

  if (
    method === "GET" &&
    segments[0] === "generations" &&
    segments[2] === "revise" &&
    segments[3] === "session"
  ) {
    return {
      status: 200,
      body: {
        session: { ...fixtureReviseSession, sourceGenerationId: segments[1] },
        plans: [{ ...fixtureRevisePlan, sourceGenerationId: segments[1] }],
      },
    };
  }

  if (
    method === "POST" &&
    segments[0] === "generations" &&
    segments[2] === "revise" &&
    segments.length === 3
  ) {
    return {
      status: 202,
      body: {
        ...fixtureReviseGenerationResponse,
        sourceGenerationId: segments[1],
        intents: fixtureEditIntent.intents,
        plan: { ...fixtureRevisePlan, sourceGenerationId: segments[1] },
        executionMode: "fork",
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
