"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ShieldCheck, ShieldOff } from "lucide-react";
import Navbar from "@/components/Navbar";
import SignaturePadModal from "@/components/SignaturePadModal";
import { api, ApiError } from "@/lib/api";
import type { SignatureItem, TotpSetupResponse, User } from "@/lib/types";

export default function SignaturesProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [signatures, setSignatures] = useState<SignatureItem[]>([]);
  const [openPad, setOpenPad] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // State 2FA TOTP
  const [totpSetup, setTotpSetup] = useState<TotpSetupResponse | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [totpBusy, setTotpBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me.user);
      const list = await api.listSignatures();
      setSignatures(list);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Gagal memuat profil.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDeleteSig(id: string) {
    try {
      await api.deleteSignature(id);
      setSignatures((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus tanda tangan.");
    }
  }

  async function handleStart2FA() {
    setError(null);
    setInfo(null);
    setTotpBusy(true);
    try {
      const res = await api.setup2FA();
      setTotpSetup(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memulai setup 2FA.");
    } finally {
      setTotpBusy(false);
    }
  }

  async function handleEnable2FA(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setTotpBusy(true);
    try {
      const res = await api.enable2FA(totpCode);
      setInfo(res.message);
      setTotpSetup(null);
      setTotpCode("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kode TOTP tidak valid.");
    } finally {
      setTotpBusy(false);
    }
  }

  async function handleDisable2FA(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setTotpBusy(true);
    try {
      const res = await api.disable2FA(totpCode);
      setInfo(res.message);
      setTotpCode("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kode TOTP tidak valid.");
    } finally {
      setTotpBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar user={user} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 space-y-8">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {info && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {info}
          </div>
        )}

        {/* Bagian 1: Koleksi Tanda Tangan */}
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                Tanda Tangan Tersimpan
              </h1>
              <p className="text-sm text-slate-600">
                Simpan tanda tangan gambar tangan, unggahan PNG/JPG, atau teks
                tulisan tangan untuk dipakai ulang pada dokumen apa pun.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpenPad(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              <Plus className="h-4 w-4" />
              Buat Tanda Tangan
            </button>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">Memuat...</div>
          ) : signatures.length === 0 ? (
            <div className="rounded-xl border-2 border-dashed border-slate-200 bg-white p-10 text-center">
              <p className="text-sm font-medium text-slate-700">
                Anda belum memiliki tanda tangan tersimpan.
              </p>
              <button
                type="button"
                onClick={() => setOpenPad(true)}
                className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Buat Tanda Tangan Pertama
              </button>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {signatures.map((sig) => (
                <div
                  key={sig.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm flex flex-col justify-between"
                >
                  <div className="h-32 rounded-lg border border-slate-100 bg-[repeating-conic-gradient(#f8fafc_0%_25%,white_0%_50%)] bg-[length:14px_14px] flex items-center justify-center p-3">
                    {sig.image_data_url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={sig.image_data_url}
                        alt={sig.label}
                        className="max-h-full max-w-full object-contain"
                      />
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        {sig.label}
                      </p>
                      <p className="text-xs text-slate-500 capitalize">
                        Mode: {sig.type}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteSig(sig.id)}
                      aria-label={`Hapus ${sig.label}`}
                      className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Bagian 2: Keamanan Akun & 2FA TOTP */}
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                {user?.totp_enabled ? (
                  <ShieldCheck className="h-5 w-5 text-emerald-600" />
                ) : (
                  <ShieldOff className="h-5 w-5 text-slate-400" />
                )}
                Autentikasi Dua Faktor (2FA TOTP)
              </h2>
              <p className="text-sm text-slate-600 mt-1">
                Lindungi akun Anda dengan kode sekali pakai dari Google
                Authenticator, Authy, atau aplikasi TOTP lainnya.
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                user?.totp_enabled
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {user?.totp_enabled ? "Aktif" : "Nonaktif"}
            </span>
          </div>

          {!user?.totp_enabled && !totpSetup && (
            <button
              type="button"
              disabled={totpBusy}
              onClick={handleStart2FA}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            >
              Aktifkan 2FA (TOTP)
            </button>
          )}

          {totpSetup && (
            <div className="grid gap-6 md:grid-cols-2 items-center rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
              <div className="text-center space-y-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={totpSetup.qr_data_url}
                  alt="QR Code Setup 2FA TOTP"
                  className="mx-auto h-44 w-44 rounded-lg border border-slate-200 bg-white p-2"
                />
                <p className="text-xs text-slate-600">
                  Kunci manual:{" "}
                  <code className="rounded bg-white px-2 py-0.5 font-mono text-slate-900">
                    {totpSetup.secret}
                  </code>
                </p>
              </div>
              <form onSubmit={handleEnable2FA} className="space-y-3">
                <p className="text-sm text-slate-700">
                  Pindai QR code di samping dengan aplikasi Authenticator, lalu
                  masukkan kode 6 digit untuk mengaktifkan:
                </p>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  value={totpCode}
                  onChange={(e) =>
                    setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  placeholder="000000"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-lg tracking-widest text-center"
                />
                <button
                  type="submit"
                  disabled={totpBusy}
                  className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Konfirmasi &amp; Aktifkan 2FA
                </button>
              </form>
            </div>
          )}

          {user?.totp_enabled && (
            <form
              onSubmit={handleDisable2FA}
              className="flex flex-wrap items-center gap-3 pt-2"
            >
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                required
                value={totpCode}
                onChange={(e) =>
                  setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                }
                placeholder="Kode 6 digit TOTP"
                className="rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm"
              />
              <button
                type="submit"
                disabled={totpBusy}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
              >
                Nonaktifkan 2FA
              </button>
            </form>
          )}
        </section>
      </main>

      <SignaturePadModal
        open={openPad}
        onClose={() => setOpenPad(false)}
        defaultName={user?.name}
        onCreated={(sig) => setSignatures((prev) => [sig, ...prev])}
      />
    </div>
  );
}
