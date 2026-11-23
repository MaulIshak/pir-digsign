"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  PenTool,
  Users,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Ban,
  Copy,
  ExternalLink,
  Plus,
  History,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import PdfViewerCanvas, { type PageMetrics } from "@/components/PdfViewerCanvas";
import StampOverlay from "@/components/StampOverlay";
import SignaturePadModal from "@/components/SignaturePadModal";
import InviteSignersModal from "@/components/InviteSignersModal";
import { api, ApiError } from "@/lib/api";
import { screenRectToPdfRect, type Rect } from "@/lib/coordinates";
import type { DocumentDetail, SignatureItem, User } from "@/lib/types";

export default function DocumentStudioPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const docId = params.id;

  const [user, setUser] = useState<User | null>(null);
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [pdfBytes, setPdfBytes] = useState<ArrayBuffer | null>(null);
  const [signatures, setSignatures] = useState<SignatureItem[]>([]);
  const [selectedSigId, setSelectedSigId] = useState<string>("");

  const [pageNumber, setPageNumber] = useState(1);
  const [allPages, setAllPages] = useState(false);
  const [signerTitle, setSignerTitle] = useState("");
  const [signerDisplayName, setSignerDisplayName] = useState("");
  const [metrics, setMetrics] = useState<PageMetrics>({
    canvasWidth: 680,
    canvasHeight: 960,
    pdfWidthPt: 595.28,
    pdfHeightPt: 841.89,
    totalPages: 1,
  });

  // Posisi default stempel di layar (piksel CSS di atas halaman PDF)
  const [stampRect, setStampRect] = useState<Rect>({
    x: 60,
    y: 420,
    w: 250,
    h: 112,
  });

  const [openSigModal, setOpenSigModal] = useState(false);
  const [openInviteModal, setOpenInviteModal] = useState(false);
  const [signing, setSigning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [me, detail, sigs, bytes] = await Promise.all([
        api.me(),
        api.getDocument(docId),
        api.listSignatures(),
        api.fetchDocumentPdfBytes(docId),
      ]);
      setUser(me.user);
      setSignerDisplayName((prev) => prev || me.user.name);
      setDoc(detail);
      setSignatures(sigs);
      if (sigs.length > 0) {
        setSelectedSigId((prev) => prev || sigs[0].id);
      }
      setPdfBytes(bytes);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(`/documents/${docId}`)}`);
        return;
      }
      setError(err instanceof Error ? err.message : "Gagal memuat dokumen.");
    } finally {
      setLoading(false);
    }
  }, [docId, router]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleMetricsChange = useCallback((m: PageMetrics) => {
    setMetrics(m);
  }, []);

  const selectedSig = signatures.find((s) => s.id === selectedSigId) || null;

  async function handleSignNow() {
    if (!doc || !selectedSigId) {
      setError("Pilih atau buat tanda tangan terlebih dahulu.");
      return;
    }
    setError(null);
    setSuccessMsg(null);
    setSigning(true);

    try {
      const pdfCoords = screenRectToPdfRect(
        stampRect,
        metrics.canvasWidth,
        metrics.canvasHeight,
        metrics.pdfWidthPt,
        metrics.pdfHeightPt
      );

      const updated = await api.signDocument(doc.id, {
        signature_id: selectedSigId,
        page: pageNumber,
        x: pdfCoords.x,
        y: pdfCoords.y,
        w: pdfCoords.w,
        h: pdfCoords.h,
        all_pages: allPages,
        signer_title: signerTitle.trim() || undefined,
        signer_display_name: signerDisplayName.trim() || user?.name,
      });

      const refreshedPdf = await api.fetchDocumentPdfBytes(doc.id);
      setDoc(updated);
      setPdfBytes(refreshedPdf);
      setSuccessMsg(
        "Dokumen berhasil ditandatangani (stempel visual + PAdES incremental update)!"
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menandatangani PDF.");
    } finally {
      setSigning(false);
    }
  }

  async function handleRevoke() {
    if (!doc) return;
    if (!window.confirm("Cabut semua tanda tangan pada dokumen ini?")) return;
    try {
      const updated = await api.revokeDocument(doc.id);
      setDoc(updated);
      setSuccessMsg("Tanda tangan dokumen telah dicabut.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mencabut dokumen.");
    }
  }

  function copyText(text: string) {
    navigator.clipboard?.writeText(text);
    setSuccessMsg("Tautan disalin ke clipboard.");
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar user={user} />
        <main className="flex-1 flex items-center justify-center text-sm text-slate-500">
          Memuat ruang kerja dokumen...
        </main>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar user={user} />
        <main className="mx-auto max-w-2xl p-8 text-center space-y-4">
          <p className="text-red-600">{error || "Dokumen tidak ditemukan."}</p>
          <Link
            href="/dashboard"
            className="inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"
          >
            Kembali ke Dashboard
          </Link>
        </main>
      </div>
    );
  }

  const nextOrder =
    Math.max(...doc.signers.map((s) => s.order_no), doc.signature_records.length) + 1;

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar user={user} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 space-y-6">
        {/* Header Dokumen */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-lg border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50"
              aria-label="Kembali ke dashboard"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-slate-900">{doc.title}</h1>
              <p className="text-xs text-slate-500">
                {doc.original_filename} &middot; {doc.page_count} halaman &middot;
                Status:{" "}
                <strong className="uppercase text-slate-800">{doc.status}</strong>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {doc.is_owner && doc.status !== "revoked" && (
              <button
                type="button"
                onClick={() => setOpenInviteModal(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Users className="h-4 w-4" />
                Undang Penanda Tangan
              </button>
            )}
            <a
              href={api.getDownloadUrl(doc.id)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
            >
              <Download className="h-4 w-4" />
              Unduh PDF
            </a>
            {doc.is_owner && doc.status !== "revoked" && (
              <button
                type="button"
                onClick={handleRevoke}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3.5 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
              >
                <Ban className="h-4 w-4" />
                Cabut
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {successMsg}
          </div>
        )}

        {/* Grid Utama: Kiri = Pratinjau PDF + Drag/Resize Stempel, Kanan = Kontrol Penandatanganan */}
        <div className="grid gap-6 lg:grid-cols-12 items-start">
          <div className="lg:col-span-8">
            <PdfViewerCanvas
              pdfBytes={pdfBytes}
              pageNumber={pageNumber}
              onPageChange={setPageNumber}
              onMetricsChange={handleMetricsChange}
              overlay={
                doc.can_sign_now ? (
                  <StampOverlay
                    rect={stampRect}
                    onChange={setStampRect}
                    signatureImageUrl={selectedSig?.image_data_url}
                    signerName={signerDisplayName || user?.name || ""}
                    signerTitle={signerTitle}
                  />
                ) : null
              }
            />
          </div>

          <aside className="lg:col-span-4 space-y-5">
            {/* Panel Penandatanganan */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <PenTool className="h-4 w-4 text-indigo-600" />
                Penempatan &amp; Penandatanganan
              </h2>

              {!doc.can_sign_now ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  {doc.cannot_sign_reason || "Dokumen tidak dapat ditandatangani saat ini."}
                </div>
              ) : (
                <>
                  {/* Pilih Tanda Tangan */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-700">
                        Pilih Tanda Tangan
                      </label>
                      <button
                        type="button"
                        onClick={() => setOpenSigModal(true)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Buat Baru
                      </button>
                    </div>

                    {signatures.length === 0 ? (
                      <button
                        type="button"
                        onClick={() => setOpenSigModal(true)}
                        className="w-full rounded-lg border-2 border-dashed border-indigo-300 bg-indigo-50/50 py-4 text-sm font-semibold text-indigo-700 hover:bg-indigo-50"
                      >
                        + Gambar / Upload / Ketik Tanda Tangan
                      </button>
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        {signatures.map((s) => (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() => setSelectedSigId(s.id)}
                            className={`rounded-lg border p-2 text-left transition ${
                              selectedSigId === s.id
                                ? "border-indigo-600 bg-indigo-50/70 ring-1 ring-indigo-600"
                                : "border-slate-200 hover:bg-slate-50"
                            }`}
                          >
                            <div className="h-12 flex items-center justify-center bg-white rounded">
                              {s.image_data_url && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={s.image_data_url}
                                  alt={s.label}
                                  className="max-h-full max-w-full object-contain"
                                />
                              )}
                            </div>
                            <p className="mt-1 truncate text-[11px] font-medium text-slate-700">
                              {s.label}
                            </p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Info Penanda Tangan di Bawah Blok Stempel */}
                  <div>
                    <label
                      htmlFor="signer-name"
                      className="block text-xs font-semibold text-slate-700 mb-1"
                    >
                      Nama Jelas di Stempel
                    </label>
                    <input
                      id="signer-name"
                      type="text"
                      value={signerDisplayName}
                      onChange={(e) => setSignerDisplayName(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="signer-title"
                      className="block text-xs font-semibold text-slate-700 mb-1"
                    >
                      Jabatan (Opsional)
                    </label>
                    <input
                      id="signer-title"
                      type="text"
                      value={signerTitle}
                      onChange={(e) => setSignerTitle(e.target.value)}
                      placeholder="Misal: Direktur Utama"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>

                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allPages}
                      onChange={(e) => setAllPages(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                    />
                    Terapkan stempel di <strong>semua halaman</strong> ({doc.page_count} hal)
                  </label>

                  <p className="text-[11px] text-slate-500">
                    Geser dan tarik sudut kotak stempel di atas pratinjau PDF
                    untuk menyesuaikan posisi dan ukuran sebelum menandatangani.
                  </p>

                  <button
                    type="button"
                    disabled={signing || !selectedSigId}
                    onClick={handleSignNow}
                    className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {signing ? "Menandatangani PDF..." : "Tandatangani Sekarang"}
                  </button>
                </>
              )}
            </div>

            {/* Daftar Penanda Tangan Multi-Signer */}
            {doc.signers.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                  <Users className="h-4 w-4 text-indigo-600" />
                  Urutan Penanda Tangan
                </h2>
                <ul className="space-y-2.5 text-xs">
                  {doc.signers.map((s) => (
                    <li
                      key={s.id}
                      className="rounded-lg border border-slate-200 p-2.5 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800">
                          #{s.order_no} &middot; {s.signer_name || s.email}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            s.status === "signed"
                              ? "bg-emerald-100 text-emerald-800"
                              : s.status === "revoked"
                              ? "bg-red-100 text-red-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {s.status === "signed"
                            ? "Selesai"
                            : s.status === "revoked"
                            ? "Dicabut"
                            : "Menunggu"}
                        </span>
                      </div>
                      <p className="text-slate-500">{s.email}</p>
                      {s.invite_link && (
                        <button
                          type="button"
                          onClick={() => copyText(s.invite_link!)}
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:underline"
                        >
                          <Copy className="h-3 w-3" />
                          Salin tautan undangan
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Tanda Tangan Kriptografis Tertanam (PAdES) */}
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                Tanda Tangan Kriptografis di PDF ({doc.embedded_signatures.length})
              </h2>
              {doc.embedded_signatures.length === 0 ? (
                <p className="text-xs text-slate-500">
                  Belum ada tanda tangan PAdES tertanam pada file PDF ini.
                </p>
              ) : (
                <ul className="space-y-2 text-xs">
                  {doc.embedded_signatures.map((emb, i) => (
                    <li
                      key={`${emb.field_name}-${i}`}
                      className="rounded-lg border border-slate-200 p-2.5 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold text-slate-800">
                          {emb.field_name}
                        </span>
                        {emb.intact ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Utuh (Intact)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-700 font-semibold">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            Rusak
                          </span>
                        )}
                      </div>
                      {emb.signer_cn && (
                        <p className="text-slate-600 truncate" title={emb.signer_cn}>
                          Sertifikat: {emb.signer_cn}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {/* Tautan Verifikasi QR per Record */}
              {doc.signature_records.length > 0 && (
                <div className="border-t border-slate-100 pt-3 space-y-2">
                  <p className="text-xs font-semibold text-slate-700">
                    Tautan Verifikasi QR Publik:
                  </p>
                  {doc.signature_records.map((rec) => (
                    <div
                      key={rec.id}
                      className="flex items-center justify-between gap-2 rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                    >
                      <span className="truncate font-medium text-slate-800">
                        {rec.field_name}: {rec.signer_name}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => copyText(rec.verify_url)}
                          className="text-slate-500 hover:text-indigo-600"
                          title="Salin URL verifikasi"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                        <Link
                          href={`/verify/${rec.token}`}
                          target="_blank"
                          className="inline-flex items-center gap-0.5 font-semibold text-indigo-600 hover:underline"
                        >
                          Buka
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>

        {/* Audit Trail Dokumen */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <History className="h-4 w-4 text-indigo-600" />
            Audit Trail Dokumen
          </h2>
          <div
            tabIndex={0}
            role="region"
            aria-labelledby="audit-caption"
            className="table-wrapper"
          >
            <table className="responsive-table text-left text-xs">
              <caption id="audit-caption" className="sr-only">
                Riwayat audit dokumen
              </caption>
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase">
                <tr>
                  <th className="px-3 py-2.5">Waktu</th>
                  <th className="px-3 py-2.5">Aksi</th>
                  <th className="px-3 py-2.5">Detail</th>
                  <th className="px-3 py-2.5">IP</th>
                  <th className="px-3 py-2.5">SHA-256</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {doc.audit_logs.map((log) => (
                  <tr key={log.id}>
                    <th className="px-3 py-2 font-medium text-slate-700 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString("id-ID")}
                    </th>
                    <td data-label="Aksi" className="px-3 py-2 font-mono font-semibold text-indigo-700">
                      {log.action}
                    </td>
                    <td data-label="Detail" className="px-3 py-2 text-slate-700">
                      {log.details || "-"}
                    </td>
                    <td data-label="IP" className="px-3 py-2 font-mono text-slate-500">
                      {log.ip || "-"}
                    </td>
                    <td
                      data-label="SHA-256"
                      className="px-3 py-2 font-mono text-slate-500"
                      title={log.doc_hash || ""}
                    >
                      {log.doc_hash ? `${log.doc_hash.slice(0, 14)}…` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <SignaturePadModal
        open={openSigModal}
        onClose={() => setOpenSigModal(false)}
        defaultName={user?.name}
        onCreated={(sig) => {
          setSignatures((prev) => [sig, ...prev]);
          setSelectedSigId(sig.id);
        }}
      />

      <InviteSignersModal
        open={openInviteModal}
        onClose={() => setOpenInviteModal(false)}
        documentId={doc.id}
        nextOrderStart={nextOrder}
        onInvited={(updated) => {
          setDoc(updated);
          setSuccessMsg("Undangan penanda tangan berhasil dikirim.");
        }}
      />
    </div>
  );
}
