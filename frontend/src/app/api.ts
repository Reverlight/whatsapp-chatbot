// ── Types ────────────────────────────────────────────────────────────────────

export interface Table {
  id: number;
  name: string;
  capacity: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TableNested {
  id: number;
  name: string;
  capacity: number;
}

export type ReservationStatus = "confirmed" | "completed" | "cancelled" | "no_show";

export interface Reservation {
  id: number;
  guest_name: string;
  phone: string;
  table_id: number | null;
  table: TableNested | null;
  reservation_date: string;
  start_time: string;
  end_time: string;
  guests: number;
  status: ReservationStatus;
  created_at: string;
  updated_at: string;
}

export interface ReservationCreatePayload {
  guest_name: string;
  phone: string;
  reservation_date: string;
  start_time: string;
  end_time: string;
  guests: number;
  table_id?: number | null;
}

export interface ReservationUpdatePayload {
  guest_name?: string;
  phone?: string;
  reservation_date?: string;
  start_time?: string;
  end_time?: string;
  guests?: number;
  table_id?: number | null;
  status?: ReservationStatus;
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