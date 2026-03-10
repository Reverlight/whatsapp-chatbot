// ── Types ────────────────────────────────────────────────────────────────────

export interface Table {
  id: number;
  name: string;
  capacity: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── Config ───────────────────────────────────────────────────────────────────

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Thin wrapper around fetch that throws with the API error detail on failure.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* no json body */
    }
    throw new Error(detail);
  }

  // 204 No Content (e.g. DELETE) — return undefined
  if (res.status === 204) return undefined as T;

  return res.json();
}
