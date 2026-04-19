/**
 * Typed fetch wrapper for the SKLD backend.
 *
 * One place for: base URL resolution, default headers, error shaping,
 * response parsing. Every API hook in `src/api/hooks/` runs through this.
 * No component should ever call `fetch` directly — see docs/clean-code.md §8.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly url: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestInitExt = Omit<RequestInit, "body"> & {
  body?: unknown;
};

async function request<T>(path: string, init: RequestInitExt = {}): Promise<T> {
  const { body, headers, ...rest } = init;
  const isJson = body !== undefined && !(body instanceof FormData);
  const response = await fetch(path, {
    ...rest,
    headers: {
      ...(isJson ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    // Try to surface the FastAPI `detail` field when present.
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload?.detail;
    } catch {
      // Body wasn't JSON — fall through to generic message.
    }
    throw new ApiError(
      response.status,
      path,
      detail ?? `${response.status} ${response.statusText}`,
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  // Callers that want bytes / text must use `requestText` / `requestBlob`.
  return (await response.text()) as unknown as T;
}

async function requestText(path: string, init: RequestInitExt = {}): Promise<string> {
  const response = await fetch(path, init as RequestInit);
  if (!response.ok) {
    throw new ApiError(response.status, path, `${response.status} ${response.statusText}`);
  }
  return response.text();
}

async function requestBlob(path: string, init: RequestInitExt = {}): Promise<Blob> {
  const response = await fetch(path, init as RequestInit);
  if (!response.ok) {
    throw new ApiError(response.status, path, `${response.status} ${response.statusText}`);
  }
  return response.blob();
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  getText: (path: string) => requestText(path, { method: "GET" }),
  getBlob: (path: string) => requestBlob(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
