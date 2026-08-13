import type { APIRoute } from "astro";

const API = process.env.SOURCECUT_API_URL ?? "http://127.0.0.1:8080";
const BODYLESS_METHODS = new Set(["GET", "HEAD"]);
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "range",
  "x-request-id",
  "x-sourcecut-admin-key",
];
const FORWARDED_RESPONSE_HEADERS = [
  "accept-ranges",
  "cache-control",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
];

export const prerender = false;

const forward: APIRoute = async ({ params, request, url }) => {
  const path = params.path;
  if (!path) return new Response("Missing API path", { status: 400 });

  const upstream = new URL(`/${path}${url.search}`, API);
  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = await fetch(upstream, {
    method: request.method,
    headers,
    body: BODYLESS_METHODS.has(request.method) ? undefined : await request.arrayBuffer(),
    signal: request.signal,
  });
  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
};

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
