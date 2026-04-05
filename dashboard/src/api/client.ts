export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const AUTH_TOKEN = import.meta.env.VITE_AUTH_TOKEN || '';

function buildHeaders(extra?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (AUTH_TOKEN) {
    headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
  }
  if (extra) {
    const entries = extra instanceof Headers
      ? Array.from(extra.entries())
      : Array.isArray(extra)
        ? extra
        : Object.entries(extra);
    for (const [k, v] of entries) {
      headers[k] = v;
    }
  }
  return headers;
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: buildHeaders(options?.headers),
  });
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(error.error || resp.statusText);
  }
  return resp.json();
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}
