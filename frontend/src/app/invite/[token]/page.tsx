"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { api, ApiError } from "@/lib/api";

export default function InviteAcceptPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.token;
    if (!token) return;

    api
      .resolveInvite(token)
      .then((res) => {
        router.replace(`/documents/${res.document_id}`);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(`/invite/${token}`)}`);
          return;
        }
        setError(
          err instanceof Error
            ? err.message
            : "Gagal memproses tautan undangan."
        );
      });
  }, [params.token, router]);

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm space-y-4">
          {error ? (
            <>
              <h1 className="text-lg font-bold text-slate-900">
                Tidak Dapat Membuka Undangan
              </h1>
              <p className="text-sm text-red-600">{error}</p>
              <div className="flex justify-center gap-3 pt-2">
                <Link
                  href={`/login?next=${encodeURIComponent(`/invite/${params.token}`)}`}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Masuk dengan Akun Lain
                </Link>
                <Link
                  href="/dashboard"
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Dashboard
                </Link>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-600">
              Memeriksa undangan tanda tangan...
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
