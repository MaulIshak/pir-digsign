"use client";

import { Rnd } from "react-rnd";
import { QrCode } from "lucide-react";
import type { Rect } from "@/lib/coordinates";

interface StampOverlayProps {
  rect: Rect;
  onChange: (next: Rect) => void;
  signatureImageUrl?: string | null;
  signerName: string;
  signerTitle?: string;
}

/**
 * Pratinjau interaktif (drag & resize dengan react-rnd) yang sesuai 1:1 dengan
 * spesifikasi stempel akhir di PDF:
 * - KIRI: "Digitally signed" (6-7pt abu-abu) + kotak QR (~25mm)
 * - KANAN: Gambar tanda tangan PNG transparan + "Simple signed" + nama penanda tangan
 * - BAWAH: Nama jelas, jabatan (opsional), dan tanggal/waktu penandatanganan
 */
export default function StampOverlay({
  rect,
  onChange,
  signatureImageUrl,
  signerName,
  signerTitle,
}: StampOverlayProps) {
  const nowStr = new Date().toLocaleString("id-ID", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <Rnd
      bounds="parent"
      size={{ width: rect.w, height: rect.h }}
      position={{ x: rect.x, y: rect.y }}
      minWidth={170}
      minHeight={82}
      onDragStop={(_e, d) => {
        onChange({ ...rect, x: d.x, y: d.y });
      }}
      onResizeStop={(_e, _dir, ref, _delta, pos) => {
        onChange({
          x: pos.x,
          y: pos.y,
          w: parseFloat(ref.style.width),
          h: parseFloat(ref.style.height),
        });
      }}
      className="z-20 group"
    >
      <div className="h-full w-full rounded border-2 border-indigo-500 bg-white/95 shadow-md p-1.5 flex flex-col justify-between cursor-move overflow-hidden">
        {/* Blok horizontal atas: KIRI = QR + "Digitally signed", KANAN = TTD + "Simple signed" */}
        <div className="flex flex-1 min-h-0 items-center gap-2">
          {/* KIRI: QR Code */}
          <div className="flex flex-col items-start justify-center shrink-0 h-full">
            <span className="text-[8px] leading-none text-slate-500 mb-0.5">
              Digitally signed
            </span>
            <div className="aspect-square h-[calc(100%-12px)] max-h-[72px] rounded-sm border border-slate-300 bg-white flex items-center justify-center p-0.5">
              <QrCode className="h-full w-full text-slate-900" />
            </div>
          </div>

          {/* KANAN: Gambar tanda tangan PNG transparan + label */}
          <div className="flex flex-1 min-w-0 h-full flex-col justify-between">
            <div className="flex-1 min-h-0 flex items-center justify-center overflow-hidden">
              {signatureImageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={signatureImageUrl}
                  alt="Pratinjau tanda tangan"
                  draggable={false}
                  className="max-h-full max-w-full object-contain pointer-events-none"
                />
              ) : (
                <span className="text-[10px] italic text-slate-400">
                  Pilih tanda tangan
                </span>
              )}
            </div>
            <div className="leading-tight pt-0.5">
              <p className="text-[8px] text-slate-500 truncate">Simple signed</p>
              <p className="text-[8.5px] font-medium text-slate-800 truncate">
                {signerName || "Nama Penanda Tangan"}
              </p>
            </div>
          </div>
        </div>

        {/* Bagian bawah blok: Nama jelas, jabatan (opsional), waktu */}
        <div className="mt-1 border-t border-slate-200 pt-0.5 leading-tight">
          <p className="text-[9px] font-bold text-slate-900 truncate">
            {signerName || "Nama Jelas"}
          </p>
          {signerTitle && signerTitle.trim() && (
            <p className="text-[8px] text-slate-600 truncate">{signerTitle}</p>
          )}
          <p className="text-[7.5px] text-slate-500 truncate">{nowStr} WIB</p>
        </div>

        {/* Badge petunjuk pojok kanan atas saat hover */}
        <div className="pointer-events-none absolute -top-5 left-0 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-medium text-white opacity-0 group-hover:opacity-100 transition">
          Geser & ubah ukuran stempel
        </div>
      </div>
    </Rnd>
  );
}
