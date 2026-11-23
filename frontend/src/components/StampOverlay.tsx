"use client";

import { Rnd } from "react-rnd";
import { QrCode } from "lucide-react";
import type { Rect } from "@/lib/coordinates";

export interface StampDisplayOptions {
  showQr: boolean;
  showLabels: boolean;
  showName: boolean;
  showDate: boolean;
  showBorder: boolean;
  transparentBackground: boolean;
}

interface StampOverlayProps {
  rect: Rect;
  onChange: (next: Rect) => void;
  signatureImageUrl?: string | null;
  signerName: string;
  signerTitle?: string;
  options: StampDisplayOptions;
}

/**
 * Pratinjau interaktif (drag & resize dengan react-rnd) yang sinkron 1:1
 * dengan hasil rendering ReportLab di PDF:
 * - Desain bersih minimalis (latar transparan, QR penuh setinggi blok di kiri,
 *   tanda tangan besar & proporsional di kanan, label mikro tipis, footer opsional).
 */
export default function StampOverlay({
  rect,
  onChange,
  signatureImageUrl,
  signerName,
  signerTitle,
  options,
}: StampOverlayProps) {
  const nowStr = new Date().toLocaleString("id-ID", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const hasFooter = options.showName || options.showDate;

  return (
    <Rnd
      bounds="parent"
      size={{ width: rect.w, height: rect.h }}
      position={{ x: rect.x, y: rect.y }}
      minWidth={72}
      minHeight={36}
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
      {/* Outline bantu putus-putus indigo hanya terlihat di layar saat menempatkan stempel */}
      <div
        className={`h-full w-full p-0.5 flex flex-col justify-between cursor-move outline outline-1 outline-dashed outline-indigo-500/80 hover:outline-indigo-600 transition ${
          options.transparentBackground ? "bg-transparent" : "bg-white"
        }`}
      >
        {/* Area Utama: KIRI = QR penuh setinggi blok, KANAN = Kotak Tanda Tangan */}
        <div className="flex flex-1 min-h-0 items-stretch gap-1">
          {options.showQr && (
            <div className="aspect-square h-full max-w-[44%] shrink-0 bg-white flex items-center justify-center">
              <QrCode className="h-full w-full text-slate-950" strokeWidth={1.75} />
            </div>
          )}

          {/* Area Tanda Tangan */}
          <div
            className={`relative flex-1 min-w-0 h-full flex items-center justify-center ${
              options.showBorder ? "border border-slate-700" : ""
            }`}
          >
            {options.showLabels && (
              <span
                className={`pointer-events-none absolute left-1 text-[7px] leading-none text-slate-500 whitespace-nowrap ${
                  options.showBorder
                    ? "-top-[4px] bg-white px-0.5"
                    : "top-0.5"
                }`}
              >
                Digitally signed
              </span>
            )}

            <div
              className={`h-full w-full flex items-center justify-center overflow-hidden ${
                options.showLabels && !options.showBorder ? "py-2.5 px-1" : "p-1"
              }`}
            >
              {signatureImageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={signatureImageUrl}
                  alt="Pratinjau tanda tangan"
                  draggable={false}
                  className="max-h-full max-w-full object-contain pointer-events-none"
                />
              ) : (
                <span className="text-[9px] italic text-slate-400">
                  Pilih tanda tangan
                </span>
              )}
            </div>

            {options.showLabels && (
              <span
                className={`pointer-events-none absolute left-1 text-[7px] leading-none text-slate-500 whitespace-nowrap ${
                  options.showBorder
                    ? "-bottom-[4px] bg-white px-0.5"
                    : "bottom-0.5"
                }`}
              >
                Simple signed
              </span>
            )}
          </div>
        </div>

        {/* Footer Opsional (hanya tampil jika showName atau showDate diaktifkan) */}
        {hasFooter && (
          <div className="pt-1 leading-tight shrink-0">
            {options.showName && (
              <>
                <p className="text-[9px] font-bold text-slate-900 truncate">
                  {signerName || "Nama Jelas"}
                </p>
                {signerTitle && signerTitle.trim() && (
                  <p className="text-[8px] text-slate-600 truncate">
                    {signerTitle}
                  </p>
                )}
              </>
            )}
            {options.showDate && (
              <p className="text-[7.5px] text-slate-500 truncate">
                {nowStr} WIB
              </p>
            )}
          </div>
        )}

        {/* Handle indikator sudut kanan-bawah untuk resize */}
        <span className="pointer-events-none absolute -bottom-1 -right-1 h-2.5 w-2.5 rounded-full bg-indigo-600 border border-white opacity-80 group-hover:opacity-100" />
        <div className="pointer-events-none absolute -top-5 left-0 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-medium text-white opacity-0 group-hover:opacity-100 transition whitespace-nowrap">
          Geser &amp; tarik sudut untuk ubah ukuran
        </div>
      </div>
    </Rnd>
  );
}
