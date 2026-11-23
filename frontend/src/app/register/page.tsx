"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, UserPlus, CheckCircle2 } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";

function RegisterFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/dashboard";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devVerifyLink, setDevVerifyLink] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.register(name, email, password);
      if (res.dev_verify_link) {
        setDevVerifyLink(res.dev_verify_link);
      } else {
        router.push(nextPath);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mendaftar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-start justify-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
          {devVerifyLink ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="h-6 w-6" />
                <h1 className="text-xl font-bold">Registrasi Berhasil!</h1>
              </div>
              <p className="text-sm text-slate-600">
                Akun Anda sudah dibuat. Silakan verifikasi email Anda melalui
                tautan yang dikirim (pada mode development, tautan tersedia di
                bawah ini dan di log backend):
              </p>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs break-all">
                <p className="font-semibold text-amber-900 mb-1">
                  [Dev Mode] Tautan Verifikasi Email:
                </p>
                <a
                  href={devVerifyLink}
                  className="text-indigo-700 underline font-mono"
                >
                  {devVerifyLink}
                </a>
              </div>
              <button
                type="button"
                onClick={() => router.push(nextPath)}
                className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Lanjut ke Dashboard
              </button>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-900">Buat Akun</h1>
                <p className="mt-1 text-sm text-slate-600">
                  Daftar untuk mengunggah &amp; menandatangani dokumen PDF.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label
                    htmlFor="full-name"
                    className="block text-sm font-medium text-slate-700 mb-1"
                  >
                    Nama Lengkap
                  </label>
                  <input
                    id="full-name"
                    name="full-name"
                    type="text"
                    autoComplete="name"
                    enterKeyHint="next"
                    required
                    minLength={2}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Budi Santoso"
                    className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                </div>

                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-slate-700 mb-1"
                  >
                    Alamat Email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    spellCheck={false}
                    enterKeyHint="next"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="budi@perusahaan.com"
                    className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  />
                </div>

                <div>
                  <label
                    htmlFor="new-password"
                    className="block text-sm font-medium text-slate-700 mb-1"
                  >
                    Kata Sandi (minimal 8 karakter)
                  </label>
                  <div className="relative">
                    <input
                      id="new-password"
                      name="new-password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      enterKeyHint="done"
                      required
                      minLength={8}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 pr-10 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={
                        showPassword
                          ? "Sembunyikan kata sandi"
                          : "Tampilkan kata sandi"
                      }
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-800"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  <UserPlus className="h-4 w-4" />
                  {loading ? "Mendaftarkan..." : "Buat Akun"}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-slate-600">
                Sudah punya akun?{" "}
                <Link
                  href={`/login${nextPath !== "/dashboard" ? `?next=${encodeURIComponent(nextPath)}` : ""}`}
                  className="font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Masuk
                </Link>
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-slate-500">Memuat...</div>}>
      <RegisterFormContent />
    </Suspense>
  );
}
