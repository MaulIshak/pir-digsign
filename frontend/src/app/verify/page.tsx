"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  ShieldAlert,
  Ban,
  Upload,
  Search,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";
import type { VerifyUploadResult } from "@/lib/types";

export default function StandaloneVerifyPage() {
  const router = useRouter();
  const [tokenInput, setTokenInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<VerifyUploadResult | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);

  function handleTokenSearch(e: React.FormEvent) {
    e.preventDefault();
    const cleaned = tokenInput.trim().split("/").pop() || "";
    if (cleaned) {
      router.push(`/verify/${encodeURIComponent(cleaned)}`);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploadResult(null);
    setUploading(true);
    try {
      const res = await api.verifyUpload(file);
      setUploadResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memverifikasi PDF.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">
            Verifikasi Keaslian Dokumen PDF
          </h1>
          <p className="text-sm text-slate-600">
            Unggah dokumen PDF bertanda tangan untuk mencocokkan hash SHA-256
            dan memeriksa keutuhan tanda tangan kriptografis PAdES.
          </p>
        </div>

        {/* Upload PDF Verifikasi */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
          <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50/40 p-8 cursor-pointer hover:bg-indigo-50 transition">
            <Upload className="h-9 w-9 text-indigo-600 mb-2" />
            <span className="text-sm font-semibold text-slate-800">
              {uploading ? "Memeriksa hash & tanda tangan..." : "Pilih atau jatuhkan file PDF di sini"}
            </span>
            <span className="text-xs text-slate-500 mt-1">
              Perubahan 1 byte saja akan langsung terdeteksi sebagai TIDAK VALID
            </span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              disabled={uploading}
              onChange={handleFileUpload}
              className="sr-only"
            />
          </label>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {uploadResult && (
            <div
              className={`rounded-xl border p-5 space-y-3 ${
                uploadResult.status === "VALID"
                  ? "border-emerald-300 bg-emerald-50"
                  : uploadResult.status === "DICABUT"
                  ? "border-amber-300 bg-amber-50"
                  : "border-red-300 bg-red-50"
              }`}
            >
              <div className="flex items-center gap-2.5">
                {uploadResult.status === "VALID" ? (
                  <ShieldCheck className="h-7 w-7 text-emerald-700" />
                ) : uploadResult.status === "DICABUT" ? (
                  <Ban className="h-7 w-7 text-amber-700" />
                ) : (
                  <ShieldAlert className="h-7 w-7 text-red-700" />
                )}
                <div>
                  <p className="text-lg font-bold text-slate-900">
                    Status: {uploadResult.status}
                  </p>
                  <p className="text-sm text-slate-700">{uploadResult.message}</p>
                </div>
              </div>

              <div className="rounded-lg bg-white/80 p-3 text-xs space-y-1.5 font-mono break-all">
                <p>
                  <span className="font-sans font-semibold text-slate-600">
                    SHA-256 PDF Diunggah:{" "}
                  </span>
                  {uploadResult.uploaded_sha256}
                </p>
                {uploadResult.expected_sha256 && (
                  <p>
                    <span className="font-sans font-semibold text-slate-600">
                      SHA-256 Tercatat:{" "}
                    </span>
                    {uploadResult.expected_sha256}
                  </p>
                )}
              </div>

              {uploadResult.matched_record && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-white/80 rounded-lg p-3">
                  <div>
                    <span className="text-slate-500">Dokumen:</span>{" "}
                    <strong>{uploadResult.matched_record.document_title}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Penanda Tangan:</span>{" "}
                    <strong>{uploadResult.matched_record.signer_name}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Waktu:</span>{" "}
                    <strong>
                      {new Date(
                        uploadResult.matched_record.signed_at
                      ).toLocaleString("id-ID")}
                    </strong>
                  </div>
                  <div>
                    <span className="text-slate-500">Field PAdES:</span>{" "}
                    <strong className="font-mono">
                      {uploadResult.matched_record.field_name}
                    </strong>
                  </div>
                </div>
              )}

              {uploadResult.embedded_signatures.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-700">
                    Tanda Tangan Kriptografis di Dalam PDF:
                  </p>
                  {uploadResult.embedded_signatures.map((e, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded bg-white/90 px-3 py-1.5 text-xs"
                    >
                      <span className="font-mono font-semibold">{e.field_name}</span>
                      {e.intact ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Utuh
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-700 font-semibold">
                          <XCircle className="h-3.5 w-3.5" />
                          Dimodifikasi / Rusak
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Atau cari via Token QR */}
        <form
          onSubmit={handleTokenSearch}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col sm:flex-row gap-2"
        >
          <input
            type="text"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Atau tempel Token / URL dari QR code..."
            className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2 text-sm"
          />
          <button
            type="submit"
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            <Search className="h-4 w-4" />
            Cek Token
          </button>
        </form>
      </main>
    </div>
  );
}
