"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API_BASE } from "../api";
import s from "./menu.module.css";

// ── Types ────────────────────────────────────────────────────────────────────

interface MenuFile {
  filename: string;
}

interface UploadResult {
  filename: string;
  chunks: number;
}

// ── API calls ────────────────────────────────────────────────────────────────

async function fetchMenuFiles(): Promise<MenuFile[]> {
  const res = await fetch(`${API_BASE}/api/menu`);
  if (!res.ok) throw new Error("Failed to load menu files");
  return res.json();
}

async function uploadMenuFiles(files: FileList): Promise<UploadResult[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const res = await fetch(`${API_BASE}/api/menu/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `Upload failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

async function deleteMenuFile(filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/menu/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    let detail = `Delete failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
}

// ── Component ────────────────────────────────────────────────────────────────

export default function MenuPage() {
  const [files, setFiles] = useState<MenuFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setFiles(await fetchMenuFiles());
    } catch {
      setError("Could not load menu files. Is the API running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Upload ──────────────────────────────────────────────────────────────

  const handleUpload = async () => {
    const input = fileRef.current;
    if (!input?.files?.length) return setError("Select at least one PDF file.");

    setError("");
    setSuccess("");
    setBusy(true);
    try {
      const results = await uploadMenuFiles(input.files);
      const summary = results.map((r) => `${r.filename} (${r.chunks} chunks)`).join(", ");
      setSuccess(`Uploaded: ${summary}`);
      input.value = "";
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Delete ──────────────────────────────────────────────────────────────

  const handleDelete = async (filename: string) => {
    if (!confirm(`Remove "${filename}" from the menu index?`)) return;

    setError("");
    setSuccess("");
    setBusy(true);
    try {
      await deleteMenuFile(filename);
      setFiles((prev) => prev.filter((f) => f.filename !== filename));
      setSuccess(`Removed: ${filename}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className={s.menuPage}>
      <div className={s.pageInner}>
        <h1 className={s.pageTitle}>Menu <em>Management</em></h1>
        <p className={s.subtitle}>Admin panel · La Maison</p>

        {/* ── Navigation ──────────────────────────────────────── */}
        <div style={{ display: "flex", gap: 16, marginBottom: 32 }}>
          <Link href="/tables" className={s.navLink}>Tables</Link>
          <Link href="/reservations" className={s.navLink}>Reservations</Link>
          <span className={`${s.navLink} ${s.navLinkActive}`}>Menu</span>
        </div>

        {/* ── Upload form ─────────────────────────────────────── */}
        <div className={s.card}>
          <h2 className={s.cardTitle}>Upload menu PDFs</h2>
          <div className={s.uploadRow}>
            <input
              ref={fileRef}
              className={s.fileInput}
              type="file"
              accept=".pdf"
              multiple
            />
            <button
              className={s.btnUpload}
              onClick={handleUpload}
              disabled={busy}
            >
              Upload
            </button>
          </div>
          {error && <p className={s.errorMsg}>{error}</p>}
          {success && <p className={s.successMsg}>{success}</p>}
        </div>

        {/* ── File list ───────────────────────────────────────── */}
        <div className={s.card}>
          {loading ? (
            <p className={s.loading}>Loading menu files…</p>
          ) : (
            <>
              <div className={s.count}>
                {files.length} file{files.length !== 1 ? "s" : ""} indexed
              </div>

              {files.length === 0 ? (
                <p className={s.empty}>
                  No menu PDFs uploaded yet. Upload one above so the AI assistant
                  can answer questions about your menu.
                </p>
              ) : (
                <table className={s.tbl}>
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {files.map((f) => (
                      <tr key={f.filename}>
                        <td>
                          <span className={s.fileBadge}>{f.filename}</span>
                        </td>
                        <td>
                          <button
                            className={`${s.btnAction} ${s.btnDel}`}
                            onClick={() => handleDelete(f.filename)}
                            disabled={busy}
                          >
                            Remove
                          </button>
                        </td>
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
