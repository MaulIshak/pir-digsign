import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PirDigSign — Aplikasi Tanda Tangan Digital PAdES",
  description:
    "Platform penandatanganan dokumen PDF secara digital dengan tanda tangan kriptografis PAdES dan QR verifikasi publik.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
