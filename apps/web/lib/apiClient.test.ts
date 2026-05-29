import { afterEach, describe, expect, it, vi } from "vitest";

import { DATA_SOURCE_HEADER } from "@/lib/api-types";
import {
  createGenerationPlan,
  getGenerationAgentRuns,
  getModelGatewayStatus,
  importSampleFromUrl,
  reviseGeneration,
  uploadAsset,
  uploadSampleVideo,
} from "@/lib/apiClient";
import { ApiClientError } from "@/lib/errors";

describe("apiClient request shapes", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POSTs multipart file for sample upload via same-origin BFF", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "s1", taskId: "t1" }), {
        status: 200,
        headers: { [DATA_SOURCE_HEADER]: "api" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "sample.mp4", { type: "video/mp4" });
    const result = await uploadSampleVideo("proj-1", file);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/proj-1/samples/upload",
      expect.objectContaining({ method: "POST" }),
    );
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.body as FormData).get("file")).toBe(file);
    expect(result.data.id).toBe("s1");
    expect(result.meta.dataSource).toBe("api");
  });

  it("POSTs JSON body for URL import", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "s2", taskId: "t2" }), {
        status: 200,
        headers: { [DATA_SOURCE_HEADER]: "api" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await importSampleFromUrl("proj-1", {
      url: "https://youtu.be/demo",
    });

    expect(fetchMock.mock.calls[0]![0]).toBe(
      "/api/projects/proj-1/samples/from-url",
    );
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
    });
    expect(JSON.parse(init.body as string)).toEqual({
      url: "https://youtu.be/demo",
    });
  });

  it("throws ApiClientError on failed responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ message: "bad" }), { status: 502 }),
      ),
    );

    await expect(
      uploadAsset("proj-1", new File(["x"], "a.jpg", { type: "image/jpeg" })),
    ).rejects.toBeInstanceOf(ApiClientError);
  });

  it("POSTs multi-variant generation plan body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          generations: [
            {
              generationId: "gen-1",
              variant: "high_click",
              taskId: "task-1",
            },
          ],
        }),
        {
          status: 201,
          headers: { [DATA_SOURCE_HEADER]: "fixture" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createGenerationPlan("proj-1", {
      variants: ["high_click"],
      brief: { sellingPoints: [], mustMention: [], avoidMention: [] },
    });

    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(JSON.parse(init.body as string)).toMatchObject({
      variants: ["high_click"],
    });
    expect(result.data.generations[0]?.variant).toBe("high_click");
  });

  it("GETs model gateway status", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          fixtureMode: true,
          providers: {
            text: { configured: true },
            vision: { configured: true },
            tts: { configured: false },
            image: { configured: true },
            video: { configured: false },
          },
        }),
        { status: 200, headers: { [DATA_SOURCE_HEADER]: "fixture" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getModelGatewayStatus();
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/settings/model-gateway");
    expect(result.data.fixtureMode).toBe(true);
  });

  it("POSTs revise generation instruction", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          sourceGenerationId: "gen-src",
          generationId: "gen-new",
          taskId: "task-new",
          intents: [],
        }),
        { status: 202, headers: { [DATA_SOURCE_HEADER]: "fixture" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await reviseGeneration("gen-src", "字幕少一点");
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      instruction: "字幕少一点",
    });
  });

  it("GETs generation agent runs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ runs: [] }), {
        status: 200,
        headers: { [DATA_SOURCE_HEADER]: "api" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getGenerationAgentRuns("gen-1");
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "/api/generations/gen-1/agent-runs",
    );
  });
});
