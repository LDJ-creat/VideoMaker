import {
  isEventStreamPath,
  proxyEventStream,
  proxyRequest,
} from "@/lib/server/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

async function handle(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { path } = await context.params;
  const apiPath = path.join("/");

  if (isEventStreamPath(apiPath)) {
    return proxyEventStream(request, apiPath);
  }

  return proxyRequest(request, apiPath);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
