"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from "lucide-react";

export interface PageMetrics {
  canvasWidth: number;
  canvasHeight: number;
  pdfWidthPt: number;
  pdfHeightPt: number;
  totalPages: number;
}

interface PdfViewerCanvasProps {
  pdfBytes: ArrayBuffer | null;
  pageNumber: number;
  onPageChange: (page: number) => void;
  onMetricsChange: (metrics: PageMetrics) => void;
  overlay?: React.ReactNode;
}

export default function PdfViewerCanvas({
  pdfBytes,
  pageNumber,
  onPageChange,
  onMetricsChange,
  overlay,
}: PdfViewerCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1.15);
  const [totalPages, setTotalPages] = useState(1);
  const [pdfDocVersion, setPdfDocVersion] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pdfDocRef = useRef<any>(null);

  // Muat dokumen PDF saat pdfBytes berubah
  useEffect(() => {
    if (!pdfBytes) return;
    let cancelled = false;

    async function loadPdf() {
      setError(null);
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url
        ).toString();

        // Salin buffer karena pdf.js mentransfer ArrayBuffer ke worker
        const copy = new Uint8Array(pdfBytes!.slice(0));
        const loadingTask = pdfjs.getDocument({ data: copy });
        const doc = await loadingTask.promise;
        if (cancelled) return;
        pdfDocRef.current = doc;
        setTotalPages(doc.numPages);
        setPdfDocVersion((v) => v + 1);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Gagal merender pratinjau PDF."
          );
        }
      }
    }

    loadPdf();
    return () => {
      cancelled = true;
    };
  }, [pdfBytes]);

  // Render halaman aktif saat pageNumber / zoom / totalPages berubah
  useEffect(() => {
    const doc = pdfDocRef.current;
    const canvas = canvasRef.current;
    if (!doc || !canvas || pdfDocVersion === 0) return;

    let cancelled = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let renderTask: any = null;

    async function renderPage() {
      setRendering(true);
      try {
        const safePage = Math.max(1, Math.min(pageNumber, doc.numPages));
        const page = await doc.getPage(safePage);
        if (cancelled) return;

        const baseViewport = page.getViewport({ scale: 1.0 });
        const viewport = page.getViewport({ scale: zoom });
        const dpr = Math.min(window.devicePixelRatio || 1, 2);

        canvas!.width = Math.floor(viewport.width * dpr);
        canvas!.height = Math.floor(viewport.height * dpr);
        canvas!.style.width = `${Math.floor(viewport.width)}px`;
        canvas!.style.height = `${Math.floor(viewport.height)}px`;

        const ctx = canvas!.getContext("2d");
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        renderTask = page.render({ canvasContext: ctx, viewport });
        await renderTask.promise;
        if (cancelled) return;

        const cw = Math.floor(viewport.width);
        const ch = Math.floor(viewport.height);
        setCanvasSize({ width: cw, height: ch });
        onMetricsChange({
          canvasWidth: cw,
          canvasHeight: ch,
          pdfWidthPt: baseViewport.width,
          pdfHeightPt: baseViewport.height,
          totalPages: doc.numPages,
        });
      } catch (err: unknown) {
        if (
          !cancelled &&
          !(err instanceof Error && err.name === "RenderingCancelledException")
        ) {
          setError(err instanceof Error ? err.message : "Gagal render halaman.");
        }
      } finally {
        if (!cancelled) setRendering(false);
      }
    }

    renderPage();
    return () => {
      cancelled = true;
      if (renderTask) {
        try {
          renderTask.cancel();
        } catch {
          // ignore
        }
      }
    };
  }, [pdfDocVersion, pageNumber, zoom, onMetricsChange]);

  return (
    <div className="flex flex-col rounded-xl border border-slate-200 bg-slate-100 overflow-hidden">
      {/* Toolbar navigasi halaman & zoom */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={pageNumber <= 1}
            onClick={() => onPageChange(pageNumber - 1)}
            aria-label="Halaman sebelumnya"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium text-slate-700">
            Halaman{" "}
            <strong className="text-slate-900">{pageNumber}</strong> /{" "}
            {totalPages}
          </span>
          <button
            type="button"
            disabled={pageNumber >= totalPages}
            onClick={() => onPageChange(pageNumber + 1)}
            aria-label="Halaman berikutnya"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-700 hover:bg-slate-50 disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.6, Number((z - 0.15).toFixed(2))))}
            aria-label="Perkecil"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-700 hover:bg-slate-50"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="w-12 text-center text-xs font-semibold text-slate-700">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.0, Number((z + 0.15).toFixed(2))))}
            aria-label="Perbesar"
            className="rounded-lg border border-slate-200 p-1.5 text-slate-700 hover:bg-slate-50"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Area kanvas PDF + overlay stempel */}
      <div className="relative overflow-auto p-4 sm:p-6 flex justify-center min-h-[540px]">
        {error ? (
          <div className="self-center rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <div
            className="relative shadow-lg bg-white select-none"
            style={{
              width: canvasSize.width || "auto",
              height: canvasSize.height || "auto",
            }}
          >
            <canvas ref={canvasRef} className="block" />
            {rendering && (
              <div className="pointer-events-none absolute inset-0 bg-white/40 flex items-center justify-center">
                <span className="rounded-full bg-slate-900/80 px-3 py-1 text-xs text-white">
                  Memuat halaman...
                </span>
              </div>
            )}
            {canvasSize.width > 0 && overlay}
          </div>
        )}
      </div>
    </div>
  );
}
