import {
  DATA_SOURCE_HEADER,
  getBackendApiUrl,
  shouldUseFixtureFallback,
} from "@/lib/server/config";
import { resolveFixture } from "@/lib/server/fixture-resolver";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

export function isEventStreamPath(apiPath: string): boolean {
  return apiPath.endsWith("/events");
}

function buildBackendUrl(apiPath: string, search: string): string {
  const base = getBackendApiUrl().replace(/\/$/, "");
  const path = apiPath.startsWith("/") ? apiPath : `/${apiPath}`;
  return `${base}/api${path}${search}`;
}

function forwardHeaders(request: Request): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(lower)) {
      headers.set(key, value);
    }
  });
  return headers;
}

function fixtureJsonResponse(
  status: number,
  body: unknown,
): Response {
  return Response.json(body, {
    status,
    headers: {
      [DATA_SOURCE_HEADER]: "fixture",
      "Content-Type": "application/json",
    },
  });
}

function upstreamErrorResponse(message: string, status = 502): Response {
  return Response.json(
    { code: "UPSTREAM_ERROR", message },
    { status, headers: { "Content-Type": "application/json" } },
  );
}

async function tryFixtureFallback(
  method: string,
  apiPath: string,
  bodyText?: string,
): Promise<Response | null> {
  if (!shouldUseFixtureFallback()) {
    return null;
  }
  const fixture = resolveFixture(method, apiPath, bodyText);
  if (!fixture) {
    return null;
  }
  return fixtureJsonResponse(fixture.status, fixture.body);
}

export async function proxyRequest(
  request: Request,
  apiPath: string,
): Promise<Response> {
  const search = new URL(request.url).search;
  const url = buildBackendUrl(apiPath, search);
  const method = request.method;
  const hasBody = method !== "GET" && method !== "HEAD";
  const bodyText =
    hasBody && request.headers.get("content-type")?.includes("application/json")
      ? await request.text()
      : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method,
      headers: forwardHeaders(request),
      body:
        hasBody && !bodyText
          ? request.body
          : bodyText
            ? bodyText
            : undefined,
      duplex: hasBody && !bodyText ? "half" : undefined,
    } as RequestInit);
  } catch (error) {
    const fallback = await tryFixtureFallback(method, apiPath, bodyText);
    if (fallback) return fallback;
    const message =
      error instanceof Error ? error.message : "Backend unreachable";
    return upstreamErrorResponse(message);
  }

  if (!upstream.ok) {
    const fallback = await tryFixtureFallback(method, apiPath, bodyText);
    if (fallback) return fallback;
    const text = await upstream.text();
    return new Response(text || upstream.statusText, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  const headers = new Headers(upstream.headers);
  headers.set(DATA_SOURCE_HEADER, "api");
  headers.delete("content-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

export async function proxyEventStream(
  request: Request,
  apiPath: string,
): Promise<Response> {
  const search = new URL(request.url).search;
  const url = buildBackendUrl(apiPath, search);

  try {
    const upstream = await fetch(url, {
      method: "GET",
      headers: forwardHeaders(request),
    });

    if (!upstream.ok || !upstream.body) {
      if (shouldUseFixtureFallback()) {
        const fixture = resolveFixture("GET", apiPath.replace(/\/events$/, ""));
        const event = fixture?.body ?? {
          taskId: apiPath.split("/")[1] ?? "unknown",
          status: "running",
          stage: "extracting_structure",
          progress: 50,
          message: "演示 SSE 不可用，请使用轮询",
          updatedAt: new Date().toISOString(),
        };
        const payload = `event: task\ndata: ${JSON.stringify(event)}\n\n`;
        return new Response(payload, {
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            [DATA_SOURCE_HEADER]: "fixture",
          },
        });
      }
      return upstreamErrorResponse("SSE upstream failed", upstream.status);
    }

    const headers = new Headers(upstream.headers);
    headers.set("Content-Type", "text/event-stream");
    headers.set("Cache-Control", "no-cache");
    headers.set(DATA_SOURCE_HEADER, "api");

    return new Response(upstream.body, {
      status: upstream.status,
      headers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "SSE proxy failed";
    return upstreamErrorResponse(message);
  }
}
