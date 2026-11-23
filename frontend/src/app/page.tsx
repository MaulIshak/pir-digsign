import Link from "next/link";
import {
  FileSignature,
  ShieldCheck,
  QrCode,
  Users,
  Lock,
  ArrowRight,
} from "lucide-react";
import Navbar from "@/components/Navbar";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-1">
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 border border-indigo-200 px-3 py-1 text-xs font-semibold text-indigo-700">
              <Lock className="h-3.5 w-3.5" />
              PAdES Incremental Signing + Verifikasi QR Publik
            </span>
            <h1 className="mt-5 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              Tandatangani Dokumen PDF Secara Digital dengan Aman & Terverifikasi
            </h1>
            <p className="mt-4 text-lg text-slate-600 leading-relaxed">
              Unggah dokumen PDF, buat tanda tangan tangan/upload/ketik, atur
              posisi stempel visual (QR code kiri + tanda tangan kanan), dan
              tanam tanda tangan kriptografis PAdES tanpa merusak tanda tangan
              sebelumnya.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
              >
                Mulai Gratis
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Buka Dashboard
              </Link>
              <Link
                href="/verify"
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-800 hover:bg-emerald-100"
              >
                <ShieldCheck className="h-4 w-4" />
                Verifikasi Keaslian PDF
              </Link>
            </div>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <FileSignature className="h-7 w-7 text-indigo-600" />
              <h2 className="mt-3 text-base font-semibold text-slate-900">
                Stempel Visual Presisi
              </h2>
              <p className="mt-1.5 text-sm text-slate-600">
                Drag &amp; resize langsung di atas halaman PDF. Ditanam ke
                koordinat PDF asli dengan QR kiri &amp; tanda tangan kanan.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <QrCode className="h-7 w-7 text-indigo-600" />
              <h2 className="mt-3 text-base font-semibold text-slate-900">
                QR Verifikasi Publik
              </h2>
              <p className="mt-1.5 text-sm text-slate-600">
                Pindai QR untuk mengecek status VALID / TIDAK VALID / DICABUT
                serta mencocokkan hash SHA-256 dokumen PDF.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <Users className="h-7 w-7 text-indigo-600" />
              <h2 className="mt-3 text-base font-semibold text-slate-900">
                Multi-Penanda Tangan
              </h2>
              <p className="mt-1.5 text-sm text-slate-600">
                Undang beberapa penanda tangan berurutan atau tandatangani ulang
                PDF yang sudah bertanda tangan memakai incremental update.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <ShieldCheck className="h-7 w-7 text-indigo-600" />
              <h2 className="mt-3 text-base font-semibold text-slate-900">
                Siap Integrasi PSrE
              </h2>
              <p className="mt-1.5 text-sm text-slate-600">
                Memakai pyHanko berstandar PAdES dengan antarmuka SignerProvider
                modular untuk KMS/HSM dan PSrE Indonesia (BSrE/Privy/Peruri/VIDA).
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
