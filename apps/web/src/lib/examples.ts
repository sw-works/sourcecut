import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Build-time access to the committed captures.
 *
 * Resolution walks up from the working directory rather than from
 * `import.meta.url`: a page is bundled before it runs, so a path relative to
 * the module resolves against the emitted chunk and silently misses. It missed
 * in exactly that way on the first Cloud Run deploy — the page built and served
 * an empty form, with no error anywhere, because a missing snapshot is a
 * supported state.
 */
const PREFIXES = ["", "..", "../..", "../../.."];

export function loadJson(directory: string, file: string): any {
  for (const prefix of PREFIXES) {
    const candidate = resolve(process.cwd(), prefix, directory, file);
    try {
      return JSON.parse(readFileSync(candidate, "utf8"));
    } catch (reason) {
      const code = (reason as NodeJS.ErrnoException)?.code;
      if (code !== "ENOENT") {
        console.warn(`[sourcecut] ${file} at ${candidate} could not be read:`, reason);
        return null;
      }
    }
  }
  return null;
}

/** The curated corpus windows, default scope first so it leads every listing. */
export function loadScopes(): any[] {
  const scopes: any[] = loadJson("data/reference", "research_scopes.json") ?? [];
  return [...scopes].sort(
    (left, right) => Number(Boolean(right.default)) - Number(Boolean(left.default)),
  );
}

/** Every scope that has a committed capture, in scope order. */
export function loadCaptures(): { scope: any; captured: any }[] {
  return loadScopes()
    .map((scope) => ({ scope, captured: loadJson("data/examples", `${scope.scope_id}.json`) }))
    .filter((entry) => entry.captured != null);
}
