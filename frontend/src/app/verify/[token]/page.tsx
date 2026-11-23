"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ShieldCheck,
  ShieldAlert,
  Ban,
  Upload,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";
import type { PublicVerifyResult, VerifyUploadResult } from "@/lib/types";

export default function PublicVerifyTokenPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [record, setRecord] = useState<PublicVerifyResult | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);

  const [checkingPdf, setCheckingPdf] = useState(false);
  const [uploadResult, setUploadResult] = useState<VerifyUploadResult | null>(
    null
  );
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .verifyToken(token)
      .then((res) => {
        setRecord(res);
      })
      .catch(() => {
        setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function handleUploadCheck(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadErr(null);
    setUploadResult(null);
    setCheckingPdf(true);
    try {
      const res = await api.verifyUpload(file, token);
      setUploadResult(res);
    } catch (err) {
      setUploadErr(
        err instanceof Error ? err.message : "Gagal memeriksa file PDF."
      );
    } finally {
      setCheckingPdf(false);
      e.target.value = "";
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 space-y-6">
        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
            Memeriksa keaslian tanda tangan...
          </div>
        ) : notFound || !record ? (
          <div className="rounded-2xl border border-red-300 bg-red-50 p-8 text-center space-y-3">
            <ShieldAlert className="mx-auto h-12 w-12 text-red-600" />
            <h1 className="text-2xl font-bold text-red-900">
              Status: TIDAK VALID
            </h1>
            <p className="text-sm text-red-700">
              Token verifikasi tidak ditemukan di sistem. Dokumen atau QR code
              kemungkinan palsu atau tidak sah.
            </p>
          </div>
        ) : (
          <>
            {/* Kartu Status Utama */}
            <div
              className={`rounded-2xl border p-6 sm:p-8 shadow-sm space-y-5 ${
                record.status === "VALID"
                  ? "border-emerald-300 bg-white"
                  : record.status === "DICABUT"
                  ? "border-amber-300 bg-white"
                  : "border-red-300 bg-white"
              }`}
            >
              <div className="flex items-center gap-3.5">
                {record.status === "VALID" ? (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                    <ShieldCheck className="h-7 w-7" />
                  </div>
                ) : record.status === "DICABUT" ? (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                    <Ban className="h-7 w-7" />
                  </div>
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-700">
                    <ShieldAlert className="h-7 w-7" />
                  </div>
                )}

                <div>
                  <span
                    className={`inline-block rounded-full px-3 py-0.5 text-xs font-bold ${
                      record.status === "VALID"
                        ? "bg-emerald-100 text-emerald-800"
                        : record.status === "DICABUT"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {record.status}
                  </span>
                  <h1 className="mt-1 text-xl font-bold text-slate-900">
                    Hasil Verifikasi Tanda Tangan Digital
                  </h1>
                  <p className="text-sm text-slate-600">{record.message}</p>
                </div>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-xl bg-slate-50 border border-slate-200 p-4 text-sm">
                <div>
                  <dt className="text-xs font-medium text-slate-500">
                    Nama Dokumen
                  </dt>
                  <dd className="mt-0.5 font-semibold text-slate-900">
                    {record.document_title}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-slate-500">
                    Penanda Tangan
                  </dt>
                  <dd className="mt-0.5 font-semibold text-slate-900">
                    {record.signer_name}
                    {record.signer_title && (
                      <span className="block text-xs font-normal text-slate-600">
                        {record.signer_title}
                      </span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-slate-500">
                    Waktu Penandatanganan
                  </dt>
                  <dd className="mt-0.5 font-medium text-slate-900">
                    {new Date(record.signed_at).toLocaleString("id-ID")}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-slate-500">
                    Field PAdES &amp; Halaman
                  </dt>
                  <dd className="mt-0.5 font-mono text-slate-900">
                    {record.field_name} (Halaman {record.page}, total{" "}
                    {record.total_signatures_on_doc} ttd)
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium text-slate-500">
                    Hash SHA-256 Dokumen
                  </dt>
                  <dd className="mt-1 rounded bg-white border border-slate-200 px-3 py-2 font-mono text-xs text-slate-800 break-all">
                    {record.doc_hash_sha256}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Opsi Unggah Ulang PDF untuk Dicocokkan Hash-nya */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Cocokkan File PDF Asli (Cek Integritas Hash SHA-256)
                </h2>
                <p className="text-xs text-slate-600 mt-0.5">
                  Unggah file PDF yang Anda terima untuk memastikan isi file
                  tidak pernah diubah meskipun hanya 1 byte sejak ditandatangani.
                </p>
              </div>

              <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 cursor-pointer hover:bg-slate-100 transition">
                <Upload className="h-7 w-7 text-indigo-600 mb-1.5" />
                <span className="text-sm font-semibold text-slate-800">
                  {checkingPdf
                    ? "Menghitung SHA-256 & memeriksa PAdES..."
                    : "Unggah PDF untuk dicocokkan hash-nya"}
                </span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={checkingPdf}
                  onChange={handleUploadCheck}
                  className="sr-only"
                />
              </label>

              {uploadErr && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {uploadErr}
                </div>
              )}

              {uploadResult && (
                <div
                  className={`rounded-xl border p-4 space-y-2.5 ${
                    uploadResult.status === "VALID"
                      ? "border-emerald-300 bg-emerald-50"
                      : uploadResult.status === "DICABUT"
                      ? "border-amber-300 bg-amber-50"
                      : "border-red-300 bg-red-50"
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold text-base">
                    {uploadResult.status === "VALID" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-700" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-700" />
                    )}
                    <span>Hasil Pencocokan: {uploadResult.status}</span>
                  </div>
                  <p className="text-sm text-slate-700">{uploadResult.message}</p>
                  <div className="rounded bg-white/80 p-2.5 font-mono text-[11px] break-all space-y-1">
                    <p>
                      <strong>Hash PDF Diunggah:</strong>{" "}
                      {uploadResult.uploaded_sha256}
                    </p>
                    {uploadResult.expected_sha256 && (
                      <p>
                        <strong>Hash Tercatat:</strong>{" "}
                        {uploadResult.expected_sha256}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
