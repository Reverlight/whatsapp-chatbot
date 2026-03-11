"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, type Table } from "../api";
import s from "./tables.module.css";

// ── API calls ────────────────────────────────────────────────────────────────

const fetchTables = () => apiFetch<Table[]>("/api/tables");

const apiCreateTable = (name: string, capacity: number) =>
  apiFetch<Table>("/api/tables", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, capacity }),
  });

const apiUpdateTable = (
  id: number,
  patch: { name?: string; capacity?: number; is_active?: boolean },
) =>
  apiFetch<Table>(`/api/tables/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

const apiDeleteTable = (id: number) =>
  apiFetch<void>(`/api/tables/${id}`, { method: "DELETE" });

// ── Component ────────────────────────────────────────────────────────────────

export default function TablesPage() {
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [seats, setSeats] = useState("");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editSeats, setEditSeats] = useState("");
  const [busy, setBusy] = useState(false);

  // ── Load on mount ────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    try {
      setTables(await fetchTables());
    } catch {
      setError("Could not load tables. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Add ──────────────────────────────────────────────────────────────────

  const addTable = async () => {
    const trimmed = name.trim();
    const seatsNum = parseInt(seats);
    if (!trimmed) return setError("Table name is required.");
    if (!seatsNum || seatsNum < 1) return setError("Enter a valid number of seats.");

    setError("");
    setBusy(true);
    try {
      const created = await apiCreateTable(trimmed, seatsNum);
      setTables((prev) => [...prev, created]);
      setName("");
      setSeats("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Delete ───────────────────────────────────────────────────────────────

  const deleteTable = async (id: number) => {
    setBusy(true);
    setError("");
    try {
      await apiDeleteTable(id);
      setTables((prev) => prev.filter((t) => t.id !== id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Toggle active ────────────────────────────────────────────────────────

  const toggleActive = async (t: Table) => {
    setBusy(true);
    setError("");
    try {
      const updated = await apiUpdateTable(t.id, { is_active: !t.is_active });
      setTables((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Inline edit ──────────────────────────────────────────────────────────

  const startEdit = (t: Table) => {
    setEditingId(t.id);
    setEditName(t.name);
    setEditSeats(String(t.capacity));
    setError("");
  };

  const cancelEdit = () => setEditingId(null);

  const saveEdit = async () => {
    if (editingId === null) return;
    const trimmed = editName.trim();
    const seatsNum = parseInt(editSeats);
    if (!trimmed) return setError("Table name is required.");
    if (!seatsNum || seatsNum < 1) return setError("Enter a valid number of seats.");

    setError("");
    setBusy(true);
    try {
      const updated = await apiUpdateTable(editingId, { name: trimmed, capacity: seatsNum });
      setTables((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      setEditingId(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className={s.tablesPage}>
      <div className={s.pageInner}>
        <h1 className={s.pageTitle}>Table <em>Management</em></h1>
        <p className={s.subtitle}>Admin panel · La Maison</p>

        {/* ── Navigation ──────────────────────────────────────── */}
        <div style={{ display: "flex", gap: 16, marginBottom: 32 }}>
          <span
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase" as const,
              padding: "6px 14px",
              border: "1px solid var(--gold)",
              borderRadius: 2,
              background: "var(--gold)",
              color: "white",
              cursor: "default",
            }}
          >
            Tables
          </span>
          <Link
            href="/reservations"
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase" as const,
              color: "var(--muted)",
              textDecoration: "none",
              padding: "6px 14px",
              border: "1px solid var(--border)",
              borderRadius: 2,
              transition: "all 0.2s",
            }}
          >
            Reservations
          </Link>
          <Link
            href="/menu"
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: "0.68rem",
              letterSpacing: "0.1em",
              textTransform: "uppercase" as const,
              color: "var(--muted)",
              textDecoration: "none",
              padding: "6px 14px",
              border: "1px solid var(--border)",
              borderRadius: 2,
              transition: "all 0.2s",
            }}
          >
            Menu
          </Link>
        </div>

        {/* ── Add form ──────────────────────────────────────────────── */}
        <div className={s.card}>
          <h2 className={s.cardTitle}>Add a table</h2>
          <div className={s.fields}>
            <div>
              <label className={s.fieldLabel} htmlFor="name">Table name</label>
              <input
                id="name"
                className={s.fieldInput}
                type="text"
                placeholder="e.g. T1, Bar-3, Terrace A"
                maxLength={20}
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTable()}
              />
            </div>
            <div>
              <label className={s.fieldLabel} htmlFor="seats">Seats</label>
              <input
                id="seats"
                className={s.fieldInput}
                type="number"
                placeholder="4"
                min={1}
                max={30}
                value={seats}
                onChange={(e) => setSeats(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTable()}
              />
            </div>
            <div>
              <button className={s.btnAdd} onClick={addTable} disabled={busy}>
                + Add
              </button>
            </div>
          </div>
          {error && <p className={s.errorMsg}>{error}</p>}
        </div>

        {/* ── Table list ────────────────────────────────────────────── */}
        <div className={s.card}>
          {loading ? (
            <p className={s.loading}>Loading tables…</p>
          ) : (
            <>
              <div className={s.count}>
                {tables.length} table{tables.length !== 1 ? "s" : ""}
              </div>

              {tables.length === 0 ? (
                <p className={s.empty}>No tables yet. Add your first one above.</p>
              ) : (
                <table className={s.tbl}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Seats</th>
                      <th>Status</th>
                      <th>Added</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {tables.map((t) => (
                      <tr key={t.id}>
                        {editingId === t.id ? (
                          <>
                            <td>
                              <input
                                className={s.fieldInputSm}
                                value={editName}
                                maxLength={20}
                                onChange={(e) => setEditName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveEdit();
                                  if (e.key === "Escape") cancelEdit();
                                }}
                                autoFocus
                              />
                            </td>
                            <td>
                              <input
                                className={s.fieldInputSm}
                                type="number"
                                value={editSeats}
                                min={1}
                                max={30}
                                style={{ width: 70 }}
                                onChange={(e) => setEditSeats(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") saveEdit();
                                  if (e.key === "Escape") cancelEdit();
                                }}
                              />
                            </td>
                            <td>
                              <span
                                className={`${s.statusBadge} ${t.is_active ? s.statusActive : s.statusInactive}`}
                                onClick={() => toggleActive(t)}
                              >
                                {t.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td className={s.dateCell}>
                              {t.created_at.slice(0, 10)}
                            </td>
                            <td>
                              <div className={s.actionsCell}>
                                <button
                                  className={`${s.btnAction} ${s.btnSave}`}
                                  onClick={saveEdit}
                                  disabled={busy}
                                >
                                  Save
                                </button>
                                <button className={s.btnAction} onClick={cancelEdit}>
                                  Cancel
                                </button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td>{t.name}</td>
                            <td>
                              <span className={s.seatsBadge}>{t.capacity} seats</span>
                            </td>
                            <td>
                              <span
                                className={`${s.statusBadge} ${t.is_active ? s.statusActive : s.statusInactive}`}
                                onClick={() => toggleActive(t)}
                              >
                                {t.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td className={s.dateCell}>
                              {t.created_at.slice(0, 10)}
                            </td>
                            <td>
                              <div className={s.actionsCell}>
                                <button
                                  className={s.btnAction}
                                  onClick={() => startEdit(t)}
                                  disabled={busy}
                                >
                                  Edit
                                </button>
                                <button
                                  className={`${s.btnAction} ${s.btnDel}`}
                                  onClick={() => deleteTable(t.id)}
                                  disabled={busy}
                                >
                                  Remove
                                </button>
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}