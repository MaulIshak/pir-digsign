"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "ok" | "err">("loading");
  const [msg, setMsg] = useState("Memverifikasi email Anda...");

  useEffect(() => {
    if (!token) {
      setStatus("err");
      setMsg("Token verifikasi tidak ditemukan di URL.");
      return;
    }
    api
      .verifyEmail(token)
      .then((res) => {
        setStatus("ok");
        setMsg(res.message);
      })
      .catch((err) => {
        setStatus("err");
        setMsg(err instanceof Error ? err.message : "Verifikasi email gagal.");
      });
  }, [token]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm space-y-4">
          {status === "loading" && (
            <p className="text-sm text-slate-600">{msg}</p>
          )}
          {status === "ok" && (
            <>
              <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
              <h1 className="text-xl font-bold text-slate-900">
                Email Terverifikasi
              </h1>
              <p className="text-sm text-slate-600">{msg}</p>
              <Link
                href="/dashboard"
                className="inline-block rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Buka Dashboard
              </Link>
            </>
          )}
          {status === "err" && (
            <>
              <XCircle className="mx-auto h-12 w-12 text-red-600" />
              <h1 className="text-xl font-bold text-slate-900">
                Verifikasi Gagal
              </h1>
              <p className="text-sm text-red-600">{msg}</p>
              <Link
                href="/login"
                className="inline-block rounded-lg border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Kembali ke Login
              </Link>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-slate-500">Memuat...</div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
