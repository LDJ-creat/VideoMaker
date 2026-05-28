import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DATA_SOURCE_HEADER } from "@/lib/api-types";
import {
  importSampleFromUrl,
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
});
