"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Lock, ShieldCheck } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, ApiError } from "@/lib/api";

function LoginFormContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [need2FA, setNeed2FA] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.login(email, password, need2FA ? totpCode : undefined);
      router.push(nextPath);
    } catch (err) {
      if (err instanceof ApiError && err.detail === "2FA_REQUIRED") {
        setNeed2FA(true);
        setError("Masukkan kode 6 digit dari aplikasi Authenticator (2FA) Anda.");
      } else {
        setError(err instanceof Error ? err.message : "Gagal masuk.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-start justify-center px-4 py-12 sm:py-16">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Masuk ke Akun</h1>
            <p className="mt-1 text-sm text-slate-600">
              Kelola dokumen dan bubuhkan tanda tangan digital Anda.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
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
                placeholder="nama@contoh.com"
                className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>

            <div>
              <label
                htmlFor="current-password"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Kata Sandi
              </label>
              <div className="relative">
                <input
                  id="current-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  enterKeyHint={need2FA ? "next" : "done"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 pr-10 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={
                    showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"
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

            {need2FA && (
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-3.5">
                <label
                  htmlFor="totp-code"
                  className="flex items-center gap-1.5 text-sm font-semibold text-indigo-900 mb-1"
                >
                  <ShieldCheck className="h-4 w-4" />
                  Kode 2FA (Authenticator)
                </label>
                <input
                  id="totp-code"
                  name="totp_code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  enterKeyHint="done"
                  maxLength={6}
                  required
                  value={totpCode}
                  onChange={(e) =>
                    setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  placeholder="123456"
                  className="w-full rounded-lg border border-indigo-300 bg-white px-3.5 py-2 text-center font-mono text-lg tracking-widest focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </div>
            )}

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
              <Lock className="h-4 w-4" />
              {loading ? "Memproses..." : "Masuk"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-600">
            Belum punya akun?{" "}
            <Link
              href={`/register${nextPath !== "/dashboard" ? `?next=${encodeURIComponent(nextPath)}` : ""}`}
              className="font-semibold text-indigo-600 hover:text-indigo-800"
            >
              Daftar sekarang
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-slate-500">Memuat...</div>}>
      <LoginFormContent />
    </Suspense>
  );
}
