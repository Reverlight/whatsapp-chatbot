"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  apiFetch,
  type Reservation,
  type ReservationCreatePayload,
  type ReservationStatus,
  type ReservationUpdatePayload,
  type Table,
} from "../api";
import s from "./reservations.module.css";

// ── API calls ────────────────────────────────────────────────────────────────

const fetchReservations = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<Reservation[]>(`/api/reservations${qs}`);
};

const fetchTables = () => apiFetch<Table[]>("/api/tables?active_only=true");

const apiCreateReservation = (payload: ReservationCreatePayload) =>
  apiFetch<Reservation>("/api/reservations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

const apiUpdateReservation = (id: number, payload: ReservationUpdatePayload) =>
  apiFetch<Reservation>(`/api/reservations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

const apiCancelReservation = (id: number) =>
  apiFetch<Reservation>(`/api/reservations/${id}/cancel`, { method: "POST" });

const apiDeleteReservation = (id: number) =>
  apiFetch<void>(`/api/reservations/${id}`, { method: "DELETE" });

// ── Status helpers ───────────────────────────────────────────────────────────

const STATUS_LABELS: Record<ReservationStatus, string> = {
  confirmed: "Confirmed",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No Show",
};

const STATUS_CSS: Record<ReservationStatus, string> = {
  confirmed: "statusConfirmed",
  completed: "statusCompleted",
  cancelled: "statusCancelled",
  no_show: "statusNoShow",
};

function formatTime(t: string) {
  return t.slice(0, 5);
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPhone, setFilterPhone] = useState("");

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<ReservationCreatePayload>({
    guest_name: "",
    phone: "",
    reservation_date: "",
    start_time: "",
    end_time: "",
    guests: 2,
    table_id: null,
  });

  // Edit modal
  const [editingRes, setEditingRes] = useState<Reservation | null>(null);
  const [editForm, setEditForm] = useState<ReservationUpdatePayload>({});

  // UI state
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  // ── Load data ──────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (filterDate) params.date = filterDate;
      if (filterStatus) params.status = filterStatus;
      if (filterPhone) params.phone = filterPhone;
      const [res, tbl] = await Promise.all([
        fetchReservations(Object.keys(params).length ? params : undefined),
        fetchTables(),
      ]);
      setReservations(res);
      setTables(tbl);
    } catch {
      setError("Could not load data. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, [filterDate, filterStatus, filterPhone]);

  useEffect(() => {
    load();
  }, [load]);

  // ── Create ─────────────────────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!createForm.guest_name.trim()) return setError("Guest name is required.");
    if (!createForm.phone.trim()) return setError("Phone is required.");
    if (!createForm.reservation_date) return setError("Date is required.");
    if (!createForm.start_time) return setError("Start time is required.");
    if (!createForm.end_time) return setError("End time is required.");
    if (createForm.guests < 1) return setError("At least 1 guest is required.");

    setError("");
    setBusy(true);
    try {
      const created = await apiCreateReservation(createForm);
      setReservations((prev) => [created, ...prev]);
      setShowCreate(false);
      setCreateForm({
        guest_name: "",
        phone: "",
        reservation_date: "",
        start_time: "",
        end_time: "",
        guests: 2,
        table_id: null,
      });
      setSuccess("Reservation created successfully.");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Edit ───────────────────────────────────────────────────────────────────

  const openEdit = (r: Reservation) => {
    setEditingRes(r);
    setEditForm({
      guest_name: r.guest_name,
      phone: r.phone,
      reservation_date: r.reservation_date,
      start_time: formatTime(r.start_time),
      end_time: formatTime(r.end_time),
      guests: r.guests,
      table_id: r.table_id,
      status: r.status,
    });
    setError("");
  };

  const handleEdit = async () => {
    if (!editingRes) return;
    setError("");
    setBusy(true);
    try {
      const updated = await apiUpdateReservation(editingRes.id, editForm);
      setReservations((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r))
      );
      setEditingRes(null);
      setSuccess("Reservation updated.");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Cancel ─────────────────────────────────────────────────────────────────

  const handleCancel = async (id: number) => {
    if (!confirm("Cancel this reservation?")) return;
    setBusy(true);
    setError("");
    try {
      const updated = await apiCancelReservation(id);
      setReservations((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r))
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Delete ─────────────────────────────────────────────────────────────────

  const handleDelete = async (id: number) => {
    if (!confirm("Permanently delete this reservation?")) return;
    setBusy(true);
    setError("");
    try {
      await apiDeleteReservation(id);
      setReservations((prev) => prev.filter((r) => r.id !== id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className={s.reservationsPage}>
      <div className={s.pageInner}>
        <h1 className={s.pageTitle}>
          Reservation <em>Management</em>
        </h1>
        <p className={s.subtitle}>Admin panel · La Maison</p>

        {/* ── Navigation ──────────────────────────────────────── */}
        <div className={s.navRow}>
          <Link href="/tables" className={s.navLink}>
            Tables
          </Link>
          <span className={`${s.navLink} ${s.navLinkActive}`}>
            Reservations
          </span>
          <Link href="/menu" className={s.navLink}>
            Menu
          </Link>
        </div>

        {success && <p className={s.successMsg}>{success}</p>}
        {error && !showCreate && !editingRes && (
          <p className={s.errorMsg}>{error}</p>
        )}

        {/* ── Create form toggle ──────────────────────────────── */}
        <div style={{ marginBottom: 24 }}>
          <button
            className={s.btnPrimary}
            onClick={() => {
              setShowCreate(!showCreate);
              setError("");
            }}
          >
            {showCreate ? "− Close" : "+ New Reservation"}
          </button>
        </div>

        {/* ── Create form ─────────────────────────────────────── */}
        {showCreate && (
          <div className={s.card}>
            <h2 className={s.cardTitle}>New reservation</h2>
            <div className={s.formGrid}>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Guest name</label>
                <input
                  className={s.fieldInput}
                  type="text"
                  placeholder="John Doe"
                  maxLength={100}
                  value={createForm.guest_name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, guest_name: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Phone</label>
                <input
                  className={s.fieldInput}
                  type="tel"
                  placeholder="+380671234567"
                  maxLength={32}
                  value={createForm.phone}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, phone: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Date</label>
                <input
                  className={s.fieldInput}
                  type="date"
                  value={createForm.reservation_date}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      reservation_date: e.target.value,
                    })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Guests</label>
                <input
                  className={s.fieldInput}
                  type="number"
                  min={1}
                  max={30}
                  value={createForm.guests}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      guests: parseInt(e.target.value) || 1,
                    })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Start time</label>
                <input
                  className={s.fieldInput}
                  type="time"
                  value={createForm.start_time}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      start_time: e.target.value,
                    })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>End time</label>
                <input
                  className={s.fieldInput}
                  type="time"
                  value={createForm.end_time}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, end_time: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>
                  Table (optional — auto-assigned)
                </label>
                <select
                  className={s.fieldSelect}
                  value={createForm.table_id ?? ""}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      table_id: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">Auto-assign</option>
                  {tables.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.capacity} seats)
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className={s.formActions}>
              <button
                className={s.btnPrimary}
                onClick={handleCreate}
                disabled={busy}
              >
                Create
              </button>
              <button
                className={s.btnSecondary}
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </button>
            </div>
            {error && showCreate && <p className={s.errorMsg}>{error}</p>}
          </div>
        )}

        {/* ── Filters + List ──────────────────────────────────── */}
        <div className={s.card}>
          <div className={s.filterBar}>
            <div className={s.filterField}>
              <label className={s.fieldLabel}>Date</label>
              <input
                className={s.filterInput}
                type="date"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
              />
            </div>
            <div className={s.filterField}>
              <label className={s.fieldLabel}>Status</label>
              <select
                className={s.filterSelect}
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="">All</option>
                <option value="confirmed">Confirmed</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
                <option value="no_show">No Show</option>
              </select>
            </div>
            <div className={s.filterField}>
              <label className={s.fieldLabel}>Phone</label>
              <input
                className={s.filterInput}
                type="text"
                placeholder="Search…"
                value={filterPhone}
                onChange={(e) => setFilterPhone(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <p className={s.loading}>Loading reservations…</p>
          ) : (
            <>
              <div className={s.count}>
                {reservations.length} reservation
                {reservations.length !== 1 ? "s" : ""}
              </div>

              {reservations.length === 0 ? (
                <p className={s.empty}>
                  No reservations found. Create one above or adjust filters.
                </p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table className={s.tbl}>
                    <thead>
                      <tr>
                        <th>Guest</th>
                        <th>Phone</th>
                        <th>Date</th>
                        <th>Time</th>
                        <th>Guests</th>
                        <th>Table</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {reservations.map((r) => (
                        <tr key={r.id}>
                          <td className={s.guestCell}>{r.guest_name}</td>
                          <td className={s.phoneCell}>{r.phone}</td>
                          <td className={s.dateCell}>{r.reservation_date}</td>
                          <td className={s.timeCell}>
                            {formatTime(r.start_time)}–
                            {formatTime(r.end_time)}
                          </td>
                          <td>
                            <span className={s.guestsBadge}>{r.guests}</span>
                          </td>
                          <td>
                            {r.table ? (
                              <span className={s.tableBadge}>
                                {r.table.name}
                              </span>
                            ) : (
                              <span className={s.phoneCell}>—</span>
                            )}
                          </td>
                          <td>
                            <span
                              className={`${s.statusBadge} ${
                                s[STATUS_CSS[r.status]]
                              }`}
                            >
                              {STATUS_LABELS[r.status]}
                            </span>
                          </td>
                          <td>
                            <div className={s.actionsCell}>
                              <button
                                className={s.btnAction}
                                onClick={() => openEdit(r)}
                                disabled={busy}
                              >
                                Edit
                              </button>
                              {r.status === "confirmed" && (
                                <button
                                  className={`${s.btnAction} ${s.btnCancel}`}
                                  onClick={() => handleCancel(r.id)}
                                  disabled={busy}
                                >
                                  Cancel
                                </button>
                              )}
                              <button
                                className={`${s.btnAction} ${s.btnDel}`}
                                onClick={() => handleDelete(r.id)}
                                disabled={busy}
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Edit modal ──────────────────────────────────────────── */}
      {editingRes && (
        <div className={s.modalOverlay} onClick={() => setEditingRes(null)}>
          <div
            className={s.modalContent}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className={s.cardTitle}>
              Edit reservation #{editingRes.id}
            </h2>
            <div className={s.formGrid}>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Guest name</label>
                <input
                  className={s.fieldInput}
                  type="text"
                  value={editForm.guest_name ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, guest_name: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Phone</label>
                <input
                  className={s.fieldInput}
                  type="tel"
                  value={editForm.phone ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, phone: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Date</label>
                <input
                  className={s.fieldInput}
                  type="date"
                  value={editForm.reservation_date ?? ""}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      reservation_date: e.target.value,
                    })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Guests</label>
                <input
                  className={s.fieldInput}
                  type="number"
                  min={1}
                  max={30}
                  value={editForm.guests ?? 1}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      guests: parseInt(e.target.value) || 1,
                    })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Start time</label>
                <input
                  className={s.fieldInput}
                  type="time"
                  value={editForm.start_time ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, start_time: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>End time</label>
                <input
                  className={s.fieldInput}
                  type="time"
                  value={editForm.end_time ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, end_time: e.target.value })
                  }
                />
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Table</label>
                <select
                  className={s.fieldSelect}
                  value={editForm.table_id ?? ""}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      table_id: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">None</option>
                  {tables.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.capacity} seats)
                    </option>
                  ))}
                </select>
              </div>
              <div className={s.formField}>
                <label className={s.fieldLabel}>Status</label>
                <select
                  className={s.fieldSelect}
                  value={editForm.status ?? ""}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      status: e.target.value as ReservationStatus,
                    })
                  }
                >
                  <option value="confirmed">Confirmed</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="no_show">No Show</option>
                </select>
              </div>
            </div>
            <div className={s.formActions}>
              <button
                className={s.btnPrimary}
                onClick={handleEdit}
                disabled={busy}
              >
                Save changes
              </button>
              <button
                className={s.btnSecondary}
                onClick={() => setEditingRes(null)}
              >
                Discard
              </button>
            </div>
            {error && editingRes && <p className={s.errorMsg}>{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}