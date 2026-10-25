import "server-only";

/**
 * The ONLY place this app talks to the INVEST API. Never write a raw `fetch` elsewhere.
 *
 * Same convention as the TCSS 460 project's `fetchGroupOneApi`: one helper, one error type,
 * so a non-2xx response is a typed thing a Server Action can convert rather than an
 * unhandled rejection somewhere in a component tree.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type FetchOptions = {
  query?: Record<string, string | number | undefined>;
  /** Seconds to cache. Omit for always-fresh. */
  revalidate?: number;
};

export async function fetchInvestApi<T>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const url = new URL(path, BASE_URL);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    next:
      options.revalidate === undefined
        ? { revalidate: 0 }
        : { revalidate: options.revalidate },
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      detail = (await res.json())?.detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(
      `INVEST API ${res.status} on ${path}`,
      res.status,
      detail,
    );
  }

  return (await res.json()) as T;
}
