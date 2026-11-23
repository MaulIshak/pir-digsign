"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Upload,
  FileText,
  Download,
  ExternalLink,
  Ban,
  RefreshCw,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import NativeModal from "@/components/NativeModal";
import { api, ApiError } from "@/lib/api";
import type { DocumentSummary, User } from "@/lib/types";

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  draft: { label: "Draft", cls: "bg-slate-100 text-slate-700" },
  pending: { label: "Menunggu", cls: "bg-amber-100 text-amber-800" },
  completed: { label: "Selesai", cls: "bg-emerald-100 text-emerald-800" },
  revoked: { label: "Dicabut", cls: "bg-red-100 text-red-800" },
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [revokeTarget, setRevokeTarget] = useState<DocumentSummary | null>(null);
  const [revokeReason, setRevokeReason] = useState("Dicabut oleh pemilik dokumen");
  const [revoking, setRevoking] = useState(false);

  const loadData = useCallback(async (statusFilter: string) => {
    setError(null);
    try {
      const me = await api.me();
      setUser(me.user);
      const list = await api.listDocuments(
        statusFilter === "all" ? undefined : statusFilter
      );
      setDocs(list);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Gagal memuat dashboard.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    loadData(filter);
  }, [filter, loadData]);

  async function handleUploadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const created = await api.uploadDocument(file, docTitle.trim() || undefined);
      setDocTitle("");
      router.push(`/documents/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengunggah PDF.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function confirmRevoke() {
    if (!revokeTarget) return;
    setRevoking(true);
    setError(null);
    try {
      await api.revokeDocument(revokeTarget.id, revokeReason);
      setRevokeTarget(null);
      await loadData(filter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mencabut dokumen.");
    } finally {
      setRevoking(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar user={user} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 space-y-6">
        {/* Header & Upload PDF */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Dashboard Dokumen
            </h1>
            <p className="text-sm text-slate-600 mt-0.5">
              Unggah PDF baru (termasuk PDF yang sudah bertanda tangan sebelumnya)
              untuk ditandatangani atau dikelola.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={docTitle}
              onChange={(e) => setDocTitle(e.target.value)}
              placeholder="Judul dokumen (opsional)"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700">
              <Upload className="h-4 w-4" />
              {uploading ? "Mengunggah..." : "Upload PDF (Maks 20 MB)"}
              <input
                type="file"
                accept="application/pdf,.pdf"
                disabled={uploading}
                onChange={handleUploadFile}
                className="sr-only"
              />
            </label>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Filter Status */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: "all", label: "Semua" },
              { id: "draft", label: "Draft" },
              { id: "pending", label: "Menunggu" },
              { id: "completed", label: "Selesai" },
              { id: "revoked", label: "Dicabut" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setFilter(tab.id)}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                  filter === tab.id
                    ? "bg-indigo-600 text-white"
                    : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => loadData(filter)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Muat Ulang
          </button>
        </div>

        {/* Tabel Dokumen Responsif */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          {loading ? (
            <div className="p-10 text-center text-sm text-slate-500">
              Memuat daftar dokumen...
            </div>
          ) : docs.length === 0 ? (
            <div className="p-12 text-center space-y-2">
              <FileText className="mx-auto h-10 w-10 text-slate-300" />
              <p className="text-sm font-medium text-slate-700">
                Belum ada dokumen pada kategori ini.
              </p>
              <p className="text-xs text-slate-500">
                Klik tombol &ldquo;Upload PDF&rdquo; di atas untuk memulai.
              </p>
            </div>
          ) : (
            <div
              tabIndex={0}
              role="region"
              aria-labelledby="docs-table-caption"
              className="table-wrapper"
            >
              <table className="responsive-table text-left text-sm">
                <caption id="docs-table-caption" className="sr-only">
                  Daftar dokumen tanda tangan digital
                </caption>
                <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Dokumen</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Tanda Tangan</th>
                    <th className="px-4 py-3 font-semibold">SHA-256 (Ringkas)</th>
                    <th className="px-4 py-3 font-semibold">Diperbarui</th>
                    <th className="px-4 py-3 font-semibold text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {docs.map((doc) => {
                    const badge = STATUS_BADGE[doc.status] || STATUS_BADGE.draft;
                    return (
                      <tr key={doc.id} className="hover:bg-slate-50/70">
                        <th className="px-4 py-3 font-medium text-slate-900">
                          <Link
                            href={`/documents/${doc.id}`}
                            className="hover:text-indigo-600 font-semibold block"
                          >
                            {doc.title}
                          </Link>
                          <span className="text-xs font-normal text-slate-500">
                            {doc.original_filename} &middot; {doc.page_count} hal
                          </span>
                        </th>
                        <td data-label="Status" className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${badge.cls}`}
                          >
                            {badge.label}
                          </span>
                        </td>
                        <td data-label="Tanda Tangan" className="px-4 py-3 text-slate-700">
                          {doc.signature_count} ttd
                        </td>
                        <td
                          data-label="SHA-256"
                          className="px-4 py-3 font-mono text-xs text-slate-500"
                          title={doc.current_hash}
                        >
                          {doc.current_hash.slice(0, 14)}&hellip;
                        </td>
                        <td data-label="Diperbarui" className="px-4 py-3 text-xs text-slate-500">
                          {new Date(doc.updated_at).toLocaleString("id-ID")}
                        </td>
                        <td data-label="Aksi" className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              href={`/documents/${doc.id}`}
                              className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              Buka / TTD
                            </Link>
                            <a
                              href={api.getDownloadUrl(doc.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                            >
                              <Download className="h-3.5 w-3.5" />
                              Unduh
                            </a>
                            {user?.id === doc.owner_id && doc.status !== "revoked" && (
                              <button
                                type="button"
                                onClick={() => setRevokeTarget(doc)}
                                className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
                              >
                                <Ban className="h-3.5 w-3.5" />
                                Cabut
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Modal Konfirmasi Cabut Tanda Tangan */}
      <NativeModal
        open={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        title="Cabut Tanda Tangan Dokumen?"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Tindakan ini akan menandai seluruh tanda tangan pada dokumen{" "}
            <strong className="text-slate-900">{revokeTarget?.title}</strong>{" "}
            sebagai <strong className="text-red-700">DICABUT</strong> pada
            halaman verifikasi publik QR code.
          </p>
          <div>
            <label
              htmlFor="revoke-reason"
              className="block text-xs font-medium text-slate-700 mb-1"
            >
              Alasan Pencabutan
            </label>
            <input
              id="revoke-reason"
              type="text"
              value={revokeReason}
              onChange={(e) => setRevokeReason(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <button
              type="button"
              autoFocus
              onClick={() => setRevokeTarget(null)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Batal
            </button>
            <button
              type="button"
              disabled={revoking}
              onClick={confirmRevoke}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            >
              {revoking ? "Mencabut..." : "Ya, Cabut Tanda Tangan"}
            </button>
          </div>
        </div>
      </NativeModal>
    </div>
  );
}
