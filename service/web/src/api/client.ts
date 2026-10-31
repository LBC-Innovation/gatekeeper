export class ApiError extends Error {
  constructor(public status: number, public detail: string, public body: any) {
    super(detail);
  }
}

async function req<T>(method: string, url: string, body?: unknown, headers: Record<string, string> = {}, keepalive = false): Promise<T> {
  const res = await fetch(url, {
    method, credentials: "same-origin", keepalive,
    headers: { Accept: "application/json", ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) window.dispatchEvent(new Event("gk:unauthorized"));
  if (!res.ok) {
    let b: any = null;
    try { b = await res.json(); } catch { /* not JSON */ }
    throw new ApiError(res.status, b?.detail ?? res.statusText, b);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(url: string) => req<T>("GET", url),
  post: <T>(url: string, body: unknown, headers?: Record<string, string>, keepalive = false) => req<T>("POST", url, body, headers, keepalive),
  put: <T>(url: string, body: unknown) => req<T>("PUT", url, body),
  patch: <T>(url: string, body: unknown) => req<T>("PATCH", url, body),
};
