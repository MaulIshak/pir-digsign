"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FileSignature, LogOut, ShieldCheck, PenTool, LayoutDashboard } from "lucide-react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

interface NavbarProps {
  user?: User | null;
}

export default function Navbar({ user }: NavbarProps) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    try {
      await api.logout();
    } catch {
      // Abaikan error saat logout
    }
    router.push("/login");
  }

  const navLinkClass = (href: string) =>
    `inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
      pathname.startsWith(href)
        ? "bg-indigo-50 text-indigo-700"
        : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
    }`;

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-6">
          <Link
            href={user ? "/dashboard" : "/"}
            className="flex items-center gap-2 font-bold text-slate-900"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
              <FileSignature className="h-5 w-5" />
            </span>
            <span className="text-base tracking-tight">PirDigSign</span>
          </Link>

          <nav className="hidden sm:flex items-center gap-1" aria-label="Navigasi utama">
            {user && (
              <>
                <Link href="/dashboard" className={navLinkClass("/dashboard")}>
                  <LayoutDashboard className="h-4 w-4" />
                  Dashboard
                </Link>
                <Link href="/signatures" className={navLinkClass("/signatures")}>
                  <PenTool className="h-4 w-4" />
                  Tanda Tangan & 2FA
                </Link>
              </>
            )}
            <Link href="/verify" className={navLinkClass("/verify")}>
              <ShieldCheck className="h-4 w-4" />
              Verifikasi PDF
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden md:block text-right">
                <p className="text-sm font-semibold text-slate-800 leading-tight">
                  {user.name}
                </p>
                <p className="text-xs text-slate-500">
                  {user.email}
                  {!user.is_verified && (
                    <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
                      Belum verifikasi email
                    </span>
                  )}
                </p>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Keluar</span>
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Masuk
              </Link>
              <Link
                href="/register"
                className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Daftar
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
