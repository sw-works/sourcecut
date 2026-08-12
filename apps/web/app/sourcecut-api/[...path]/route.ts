const API = process.env.SOURCECUT_API_URL ?? "http://127.0.0.1:8080";

type ProxyContext = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: ProxyContext) {
  const { path } = await context.params;
  const inbound = new URL(request.url);
  const upstream = new URL(`/${path.join("/")}${inbound.search}`, API);
  const headers = new Headers();
  for (const name of ["accept", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = await fetch(upstream, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    signal: request.signal,
  });
  const responseHeaders = new Headers();
  for (const name of ["cache-control", "content-disposition", "content-length", "content-type"]) {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers: responseHeaders });
}

export const dynamic = "force-dynamic";
export const GET = forward;
export const POST = forward;
export const DELETE = forward;
