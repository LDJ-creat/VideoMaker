import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  importSampleFromUrl,
  uploadAsset,
  uploadSampleVideo,
} from "@/lib/apiClient";

describe("apiClient request shapes", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_USE_FIXTURES", "false");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs multipart file for sample upload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "s1", taskId: "t1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "sample.mp4", { type: "video/mp4" });
    await uploadSampleVideo("http://api.test", "proj-1", file);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/api/projects/proj-1/samples/upload",
    );
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("POSTs JSON body for URL import", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "s2", taskId: "t2" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await importSampleFromUrl("http://api.test", "proj-1", {
      url: "https://youtu.be/demo",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://api.test/api/projects/proj-1/samples/from-url",
    );
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
    });
    expect(JSON.parse(init.body as string)).toEqual({
      url: "https://youtu.be/demo",
    });
  });

  it("POSTs multipart file for asset upload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "a1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["x"], "photo.jpg", { type: "image/jpeg" });
    await uploadAsset("http://api.test", "proj-1", file);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.body as FormData).get("file")).toBe(file);
  });
});
