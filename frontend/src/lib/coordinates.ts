export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Konversi koordinat kotak stempel di layar (origin kiri-atas, piksel CSS)
 * ke koordinat PDF (origin kiri-bawah, satuan PDF points 1/72 inci).
 */
export function screenRectToPdfRect(
  screen: Rect,
  canvasWidthPx: number,
  canvasHeightPx: number,
  pdfPageWidthPt: number,
  pdfPageHeightPt: number
): Rect {
  if (canvasWidthPx <= 0 || canvasHeightPx <= 0) {
    return { x: 50, y: 80, w: 210, h: 95 };
  }

  const scaleX = pdfPageWidthPt / canvasWidthPx;
  const scaleY = pdfPageHeightPt / canvasHeightPx;

  const pdfW = screen.w * scaleX;
  const pdfH = screen.h * scaleY;
  const pdfX = screen.x * scaleX;
  const pdfY = pdfPageHeightPt - (screen.y + screen.h) * scaleY;

  return {
    x: Number(Math.max(0, Math.min(pdfX, pdfPageWidthPt - pdfW)).toFixed(2)),
    y: Number(Math.max(0, Math.min(pdfY, pdfPageHeightPt - pdfH)).toFixed(2)),
    w: Number(Math.max(40, Math.min(pdfW, pdfPageWidthPt)).toFixed(2)),
    h: Number(Math.max(30, Math.min(pdfH, pdfPageHeightPt)).toFixed(2)),
  };
}
