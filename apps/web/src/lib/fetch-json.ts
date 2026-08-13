export async function fetchJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
  fallback = "The requested data is unavailable.",
): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {}
    throw new Error(detail || fallback);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new Error(fallback);
  }
}
