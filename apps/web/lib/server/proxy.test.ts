import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DATA_SOURCE_HEADER } from "@/lib/server/config";
import { isEventStreamPath, proxyEventStream, proxyRequest } from "@/lib/server/proxy";

describe("server proxy", () => {
  beforeEach(() => {
    vi.stubEnv("VIDEOMAKER_API_URL", "http://backend.test");
    vi.stubEnv("VIDEOMAKER_USE_FIXTURE_FALLBACK", "false");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("detects SSE paths", () => {
    expect(isEventStreamPath("tasks/abc/events")).toBe(true);
    expect(isEventStreamPath("tasks/abc")).toBe(false);
  });

  it("forwards JSON requests to backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://localhost/api/projects/p1/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: "test" }),
    });

    const response = await proxyRequest(request, "projects/p1/brief");
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/api/projects/p1/brief",
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.headers.get(DATA_SOURCE_HEADER)).toBe("api");
  });

  it("returns fixture with header when fallback enabled and upstream fails", async () => {
    vi.stubEnv("VIDEOMAKER_USE_FIXTURE_FALLBACK", "true");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

    const request = new Request("http://localhost/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Demo" }),
    });

    const response = await proxyRequest(request, "projects");
    expect(response.status).toBe(201);
    expect(response.headers.get(DATA_SOURCE_HEADER)).toBe("fixture");
    const body = (await response.json()) as { name: string };
    expect(body.name).toBe("Demo");
  });

  it("returns 502 when upstream fails and fallback disabled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));

    const request = new Request("http://localhost/api/projects");
    const response = await proxyRequest(request, "projects");
    expect(response.status).toBe(502);
  });

  it("proxies SSE streams from backend", async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode('event: task\ndata: {"taskId":"t1"}\n\n'),
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      ),
    );

    const request = new Request("http://localhost/api/tasks/t1/events");
    const response = await proxyEventStream(request, "tasks/t1/events");
    expect(response.headers.get("Content-Type")).toContain("text/event-stream");
    expect(response.headers.get(DATA_SOURCE_HEADER)).toBe("api");
  });
});
