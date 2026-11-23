"use client";

import { useEffect, useRef, useState } from "react";
import SignaturePad from "signature_pad";
import { Eraser, RotateCcw, Upload, PenTool, Type } from "lucide-react";
import NativeModal from "./NativeModal";
import { api } from "@/lib/api";
import type { SignatureItem } from "@/lib/types";

interface SignaturePadModalProps {
  open: boolean;
  onClose: () => void;
  defaultName?: string;
  onCreated: (sig: SignatureItem) => void;
}

const INK_COLORS = [
  { name: "Hitam", value: "#0f172a" },
  { name: "Biru Tua", value: "#1e3a8a" },
  { name: "Merah Gelap", value: "#991b1b" },
];

const HANDWRITING_FONTS = [
  { label: "Dancing Script", family: "'Dancing Script', cursive" },
  { label: "Great Vibes", family: "'Great Vibes', cursive" },
  { label: "Pacifico", family: "'Pacifico', cursive" },
  { label: "Caveat", family: "'Caveat', cursive" },
];

export default function SignaturePadModal({
  open,
  onClose,
  defaultName = "",
  onCreated,
}: SignaturePadModalProps) {
  const [mode, setMode] = useState<"draw" | "upload" | "type">("draw");
  const [label, setLabel] = useState("Tanda Tangan Utama");
  const [inkColor, setInkColor] = useState(INK_COLORS[0].value);
  const [typedText, setTypedText] = useState(defaultName);
  const [selectedFont, setSelectedFont] = useState(HANDWRITING_FONTS[0].family);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [removeBg, setRemoveBg] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const padRef = useRef<SignaturePad | null>(null);

  useEffect(() => {
    if (defaultName && !typedText) {
      setTypedText(defaultName);
    }
  }, [defaultName, typedText]);

  useEffect(() => {
    if (!open || mode !== "draw") return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const width = canvas.offsetWidth || 560;
    const height = 210;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.scale(ratio, ratio);
    }

    const pad = new SignaturePad(canvas, {
      penColor: inkColor,
      minWidth: 1.5,
      maxWidth: 3.2,
      backgroundColor: "rgba(0,0,0,0)",
    });
    padRef.current = pad;

    return () => {
      pad.off();
      padRef.current = null;
    };
  }, [open, mode]);

  useEffect(() => {
    if (padRef.current) {
      padRef.current.penColor = inkColor;
    }
  }, [inkColor]);

  function handleUndo() {
    const pad = padRef.current;
    if (!pad) return;
    const data = pad.toData();
    if (data.length > 0) {
      data.pop();
      pad.fromData(data);
    }
  }

  function handleClear() {
    padRef.current?.clear();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploadFile(f);
    setError(null);
    const url = URL.createObjectURL(f);
    setUploadPreview(url);
  }

  function renderTypedSignatureToDataUrl(): string {
    const canvas = document.createElement("canvas");
    canvas.width = 760;
    canvas.height = 220;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas tidak didukung browser.");

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = inkColor;
    ctx.font = `68px ${selectedFont}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(typedText.trim(), canvas.width / 2, canvas.height / 2);
    return canvas.toDataURL("image/png");
  }

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      let created: SignatureItem;

      if (mode === "draw") {
        if (!padRef.current || padRef.current.isEmpty()) {
          setError("Silakan gambar tanda tangan Anda terlebih dahulu di area canvas.");
          setSaving(false);
          return;
        }
        const dataUrl = padRef.current.toDataURL("image/png");
        created = await api.createSignatureBase64({
          label: label.trim() || "Tanda Tangan Gambar",
          type: "draw",
          image_base64: dataUrl,
          remove_background: false,
        });
      } else if (mode === "upload") {
        if (!uploadFile) {
          setError("Pilih file gambar tanda tangan (PNG/JPG) terlebih dahulu.");
          setSaving(false);
          return;
        }
        created = await api.createSignatureFile(
          uploadFile,
          label.trim() || "Tanda Tangan Upload",
          removeBg
        );
      } else {
        if (!typedText.trim()) {
          setError("Ketik nama Anda untuk membuat tanda tangan.");
          setSaving(false);
          return;
        }
        const dataUrl = renderTypedSignatureToDataUrl();
        created = await api.createSignatureBase64({
          label: label.trim() || `TTD ${typedText.trim()}`,
          type: "type",
          image_base64: dataUrl,
          remove_background: false,
        });
      }

      onCreated(created);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan tanda tangan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <NativeModal open={open} onClose={onClose} title="Buat Tanda Tangan Baru">
      <div className="space-y-4">
        {/* Pilihan 3 Mode */}
        <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setMode("draw")}
            className={`flex items-center justify-center gap-1.5 rounded-md py-2 text-sm font-medium transition ${
              mode === "draw"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <PenTool className="h-4 w-4" />
            Gambar
          </button>
          <button
            type="button"
            onClick={() => setMode("upload")}
            className={`flex items-center justify-center gap-1.5 rounded-md py-2 text-sm font-medium transition ${
              mode === "upload"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Upload className="h-4 w-4" />
            Upload Gambar
          </button>
          <button
            type="button"
            onClick={() => setMode("type")}
            className={`flex items-center justify-center gap-1.5 rounded-md py-2 text-sm font-medium transition ${
              mode === "type"
                ? "bg-white text-indigo-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Type className="h-4 w-4" />
            Ketik Nama
          </button>
        </div>

        {/* Nama / Label Tanda Tangan */}
        <div>
          <label
            htmlFor="sig-label"
            className="block text-xs font-medium text-slate-700 mb-1"
          >
            Label Tanda Tangan (tersimpan di profil)
          </label>
          <input
            id="sig-label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Misal: TTD Resmi, Paraf Cepat"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>

        {/* Warna tinta untuk mode Draw & Type */}
        {(mode === "draw" || mode === "type") && (
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-600">Warna Tinta:</span>
            <div className="flex items-center gap-2">
              {INK_COLORS.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setInkColor(c.value)}
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                    inkColor === c.value
                      ? "border-indigo-600 bg-indigo-50 text-indigo-800"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <span
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: c.value }}
                  />
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* MODE A: DRAW */}
        {mode === "draw" && (
          <div className="space-y-2">
            <div className="relative rounded-xl border-2 border-dashed border-slate-300 bg-white overflow-hidden">
              <canvas
                ref={canvasRef}
                className="w-full h-[210px] touch-none cursor-crosshair block"
              />
              <span className="pointer-events-none absolute bottom-2 right-3 text-[11px] text-slate-400">
                Gambar tanda tangan di sini
              </span>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleUndo}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Urungkan
              </button>
              <button
                type="button"
                onClick={handleClear}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <Eraser className="h-3.5 w-3.5" />
                Hapus
              </button>
            </div>
          </div>
        )}

        {/* MODE B: UPLOAD */}
        {mode === "upload" && (
          <div className="space-y-3">
            <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 cursor-pointer hover:bg-slate-100 transition">
              <Upload className="h-8 w-8 text-slate-400 mb-2" />
              <span className="text-sm font-medium text-slate-700">
                Pilih file PNG atau JPG (maks 5 MB)
              </span>
              <span className="text-xs text-slate-500 mt-0.5">
                Foto tanda tangan di kertas putih dapat dihapus latarnya otomatis
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleFileChange}
                className="sr-only"
              />
            </label>

            {uploadPreview && (
              <div className="rounded-lg border border-slate-200 p-3 bg-[repeating-conic-gradient(#f1f5f9_0%_25%,white_0%_50%)] bg-[length:16px_16px]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={uploadPreview}
                  alt="Pratinjau tanda tangan yang diunggah"
                  className="mx-auto max-h-36 object-contain"
                />
              </div>
            )}

            <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={removeBg}
                onChange={(e) => setRemoveBg(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              Hapus latar putih/kertas secara otomatis menjadi PNG transparan
            </label>
          </div>
        )}

        {/* MODE C: TYPE */}
        {mode === "type" && (
          <div className="space-y-3">
            <div>
              <label
                htmlFor="typed-sig-input"
                className="block text-xs font-medium text-slate-700 mb-1"
              >
                Ketik Nama Anda
              </label>
              <input
                id="typed-sig-input"
                type="text"
                value={typedText}
                onChange={(e) => setTypedText(e.target.value)}
                placeholder="Nama Penanda Tangan"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              {HANDWRITING_FONTS.map((f) => (
                <button
                  key={f.label}
                  type="button"
                  onClick={() => setSelectedFont(f.family)}
                  className={`rounded-xl border p-3 text-center transition ${
                    selectedFont === f.family
                      ? "border-indigo-600 bg-indigo-50/70 ring-1 ring-indigo-600"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div
                    className="text-3xl truncate py-1"
                    style={{ fontFamily: f.family, color: inkColor }}
                  >
                    {typedText.trim() || "Tanda Tangan"}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">{f.label}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Batal
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={handleSave}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? "Menyimpan..." : "Simpan ke Profil"}
          </button>
        </div>
      </div>
    </NativeModal>
  );
}
