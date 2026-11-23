"use client";

import { useState } from "react";
import { Plus, Trash2, Send } from "lucide-react";
import NativeModal from "./NativeModal";
import { api } from "@/lib/api";
import type { DocumentDetail } from "@/lib/types";

interface InviteSignersModalProps {
  open: boolean;
  onClose: () => void;
  documentId: string;
  nextOrderStart: number;
  onInvited: (updated: DocumentDetail) => void;
}

interface SignerRow {
  email: string;
  name: string;
  order_no: number;
}

export default function InviteSignersModal({
  open,
  onClose,
  documentId,
  nextOrderStart,
  onInvited,
}: InviteSignersModalProps) {
  const [rows, setRows] = useState<SignerRow[]>([
    { email: "", name: "", order_no: nextOrderStart },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addRow() {
    const maxOrder = Math.max(...rows.map((r) => r.order_no), nextOrderStart - 1);
    setRows([...rows, { email: "", name: "", order_no: maxOrder + 1 }]);
  }

  function removeRow(index: number) {
    if (rows.length <= 1) return;
    setRows(rows.filter((_, i) => i !== index));
  }

  function updateRow(index: number, patch: Partial<SignerRow>) {
    setRows(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const valid = rows.filter((r) => r.email.trim());
    if (valid.length === 0) {
      setError("Masukkan minimal satu alamat email penanda tangan.");
      return;
    }

    setSubmitting(true);
    try {
      const updated = await api.inviteSigners(
        documentId,
        valid.map((r) => ({
          email: r.email.trim(),
          name: r.name.trim() || undefined,
          order_no: Number(r.order_no) || 1,
        }))
      );
      onInvited(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengirim undangan.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <NativeModal
      open={open}
      onClose={onClose}
      title="Undang Penanda Tangan (Multi-Signer)"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Tambahkan penanda tangan secara berurutan. Setiap penanda tangan akan
          menerima tautan unik dan tanda tangannya ditanam sebagai revisi baru
          (<em>incremental update</em>) tanpa menghapus tanda tangan sebelumnya.
        </p>

        <div className="space-y-3">
          {rows.map((row, idx) => (
            <div
              key={idx}
              className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-end rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Urutan
                </label>
                <input
                  type="number"
                  min={1}
                  value={row.order_no}
                  onChange={(e) =>
                    updateRow(idx, { order_no: Number(e.target.value) })
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm"
                  required
                />
              </div>
              <div className="sm:col-span-5">
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Email Penanda Tangan
                </label>
                <input
                  type="email"
                  spellCheck={false}
                  value={row.email}
                  onChange={(e) => updateRow(idx, { email: e.target.value })}
                  placeholder="nama@perusahaan.com"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  required
                />
              </div>
              <div className="sm:col-span-4">
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Nama (Opsional)
                </label>
                <input
                  type="text"
                  value={row.name}
                  onChange={(e) => updateRow(idx, { name: e.target.value })}
                  placeholder="Nama Lengkap"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
              </div>
              <div className="sm:col-span-1 flex justify-end">
                <button
                  type="button"
                  onClick={() => removeRow(idx)}
                  disabled={rows.length <= 1}
                  aria-label="Hapus baris"
                  className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={addRow}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-800"
        >
          <Plus className="h-4 w-4" />
          Tambah penanda tangan berikutnya
        </button>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {submitting ? "Mengirim..." : "Kirim Undangan"}
          </button>
        </div>
      </form>
    </NativeModal>
  );
}
