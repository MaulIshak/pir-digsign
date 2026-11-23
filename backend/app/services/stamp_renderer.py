"""
Modul inti rendering stempel tanda tangan visual + konversi koordinat layar -> PDF.

Spesifikasi tampilan stempel (WAJIB SESUAI):
- Blok horizontal dengan latar putih/transparan:
  - KIRI: QR code kotak (~25 mm / proporsional, error correction Q/H).
          Di atas QR ada teks kecil (6-7 pt, abu-abu) "Digitally signed".
  - KANAN: Gambar tanda tangan pengguna (PNG transparan, rasio terjaga).
          Di bawahnya ada teks kecil (6-7 pt, abu-abu) "Simple signed" dan nama penanda tangan.
  - DI BAWAH BLOK: Nama jelas, jabatan (opsional), dan tanggal/waktu penandatanganan.
"""

import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import qrcode
from PIL import Image
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

# Zona waktu default tampilan stempel Indonesia (WIB / UTC+7)
WIB = timezone(timedelta(hours=7))


def screen_to_pdf_coords(
    screen_x: float,
    screen_y: float,
    screen_w: float,
    screen_h: float,
    canvas_w: float,
    canvas_h: float,
    pdf_page_w: float,
    pdf_page_h: float,
) -> Tuple[float, float, float, float]:
    """
    Konversi koordinat layar (origin kiri-atas, satuan piksel CSS)
    menjadi koordinat PDF (origin kiri-bawah, satuan PDF points 1/72 inci).

    Returns:
        (pdf_x, pdf_y, pdf_w, pdf_h) di mana (pdf_x, pdf_y) adalah sudut kiri-bawah stempel.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        raise ValueError("Dimensi canvas pratinjau harus lebih besar dari 0.")

    scale_x = pdf_page_w / canvas_w
    scale_y = pdf_page_h / canvas_h

    pdf_x = screen_x * scale_x
    pdf_w = screen_w * scale_x
    pdf_h = screen_h * scale_y
    pdf_y = pdf_page_h - ((screen_y + screen_h) * scale_y)

    # Clamp agar tidak keluar dari batas halaman PDF
    pdf_w = max(40.0, min(pdf_w, pdf_page_w))
    pdf_h = max(30.0, min(pdf_h, pdf_page_h))
    pdf_x = max(0.0, min(pdf_x, pdf_page_w - pdf_w))
    pdf_y = max(0.0, min(pdf_y, pdf_page_h - pdf_h))

    return pdf_x, pdf_y, pdf_w, pdf_h


def generate_qr_pil_image(url: str) -> Image.Image:
    """Membuat QR code beresolusi tinggi dengan error correction level H."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img


def render_stamp_pdf_bytes(
    verify_url: str,
    signature_png_bytes: bytes,
    signer_name: str,
    signed_at: datetime,
    width_pt: float,
    height_pt: float,
    signer_title: Optional[str] = None,
    transparent_background: bool = False,
) -> bytes:
    """
    Merender blok stempel horizontal sebagai 1 halaman PDF vektor presisi (ReportLab)
    dengan ukuran tepat (width_pt x height_pt) untuk ditanam langsung sebagai
    Signature Widget Appearance Stream di pyHanko.

    Tata letak:
    +------------------------------------------------------+
    | Digitally signed  |       [Gambar Tanda Tangan]      |
    | +---------------+ |         (PNG transparan,         |
    | |   QR CODE     | |          rasio terjaga)          |
    | |  (~25 mm)     | |  Simple signed                   |
    | +---------------+ |  Nama Penanda Tangan             |
    +------------------------------------------------------+
    | Nama Jelas (Bold) | Jabatan (opsional)               |
    | Ditandatangani: DD/MM/YYYY HH:MM:SS WIB              |
    +------------------------------------------------------+
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    pad = max(3.0, min(width_pt, height_pt) * 0.04)

    # Latar putih bersih atau transparan + bingkai tipis halus
    if not transparent_background:
        c.setFillColor(Color(1, 1, 1, alpha=0.96))
        c.setStrokeColor(HexColor("#D1D5DB"))
        c.setLineWidth(0.5)
        c.roundRect(0.5, 0.5, width_pt - 1.0, height_pt - 1.0, radius=3, stroke=1, fill=1)
    else:
        c.setStrokeColor(HexColor("#E5E7EB"))
        c.setLineWidth(0.4)
        c.roundRect(0.5, 0.5, width_pt - 1.0, height_pt - 1.0, radius=3, stroke=1, fill=0)

    # Skala font adaptif (terjaga di kisaran 6-7 pt sesuai spesifikasi)
    scale_factor = min(1.0, max(0.75, height_pt / 95.0))
    label_font_size = max(5.5, min(7.0, 6.5 * scale_factor))
    name_font_size = max(6.0, min(8.0, 7.2 * scale_factor))
    meta_font_size = max(5.5, min(6.8, 6.0 * scale_factor))

    gray_text = HexColor("#6B7280")
    dark_text = HexColor("#111827")

    # Area footer di bawah blok (Nama jelas, jabatan opsional, tanggal/waktu)
    footer_lines = 2 if not (signer_title and signer_title.strip()) else 3
    line_h = meta_font_size + 2.2
    footer_h = (footer_lines * line_h) + pad * 0.6

    # Garis pemisah tipis antara blok utama (QR+TTD) dan footer
    divider_y = pad + footer_h
    c.setStrokeColor(HexColor("#E5E7EB"))
    c.setLineWidth(0.4)
    c.line(pad, divider_y, width_pt - pad, divider_y)

    # --- Render Footer (di bawah blok) ---
    ts_wib = signed_at.astimezone(WIB)
    ts_str = ts_wib.strftime("%d/%m/%Y %H:%M:%S WIB")

    cur_y = divider_y - line_h
    c.setFillColor(dark_text)
    c.setFont("Helvetica-Bold", name_font_size)
    c.drawString(pad, cur_y, _truncate_text(c, signer_name, "Helvetica-Bold", name_font_size, width_pt - 2 * pad))

    if signer_title and signer_title.strip():
        cur_y -= line_h
        c.setFillColor(gray_text)
        c.setFont("Helvetica", meta_font_size)
        c.drawString(pad, cur_y, _truncate_text(c, signer_title.strip(), "Helvetica", meta_font_size, width_pt - 2 * pad))

    cur_y -= line_h
    c.setFillColor(gray_text)
    c.setFont("Helvetica", meta_font_size)
    c.drawString(pad, cur_y, _truncate_text(c, ts_str, "Helvetica", meta_font_size, width_pt - 2 * pad))

    # --- Area Utama (Atas): KIRI = QR + "Digitally signed", KANAN = TTD + "Simple signed" + Nama ---
    main_bottom = divider_y + pad * 0.6
    main_top = height_pt - pad
    main_h = max(20.0, main_top - main_bottom)

    # Ukuran QR ideal (~25mm = 70.87 pt), disesuaikan agar proporsional di dalam kotak
    label_h = label_font_size + 3.0
    max_qr_h = max(16.0, main_h - label_h)
    max_qr_w = (width_pt - 2 * pad) * 0.42
    qr_size = min(71.0, max_qr_h, max_qr_w)

    # KIRI: Teks "Digitally signed" di atas QR code
    qr_x = pad
    qr_y = main_bottom + max(0.0, (main_h - label_h - qr_size) / 2.0)

    c.setFillColor(gray_text)
    c.setFont("Helvetica", label_font_size)
    c.drawString(qr_x, qr_y + qr_size + 2.0, "Digitally signed")

    qr_img = generate_qr_pil_image(verify_url)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    # KANAN: Gambar tanda tangan PNG transparan (rasio terjaga) + "Simple signed" + nama
    right_x = qr_x + qr_size + max(6.0, pad * 1.4)
    right_w = max(20.0, (width_pt - pad) - right_x)

    # Teks di bawah gambar tanda tangan: "Simple signed" & nama penanda tangan
    right_caption_h = (label_font_size + 2.0) * 2
    sig_area_bottom = main_bottom + right_caption_h
    sig_area_h = max(12.0, main_top - sig_area_bottom)

    c.setFillColor(gray_text)
    c.setFont("Helvetica", label_font_size)
    c.drawString(
        right_x,
        main_bottom + label_font_size + 2.5,
        _truncate_text(c, "Simple signed", "Helvetica", label_font_size, right_w),
    )
    c.setFillColor(dark_text)
    c.setFont("Helvetica", label_font_size)
    c.drawString(
        right_x,
        main_bottom + 1.0,
        _truncate_text(c, signer_name, "Helvetica", label_font_size, right_w),
    )

    # Gambar Tanda Tangan (rasio aspek 100% terjaga)
    with Image.open(io.BytesIO(signature_png_bytes)) as sig_pil:
        sig_rgba = sig_pil.convert("RGBA")
        sw, sh = sig_rgba.size
        if sw > 0 and sh > 0:
            ratio = min(right_w / float(sw), sig_area_h / float(sh))
            draw_w = sw * ratio
            draw_h = sh * ratio
            draw_x = right_x + (right_w - draw_w) / 2.0
            draw_y = sig_area_bottom + (sig_area_h - draw_h) / 2.0

            sig_buf = io.BytesIO()
            sig_rgba.save(sig_buf, format="PNG")
            sig_buf.seek(0)
            c.drawImage(
                ImageReader(sig_buf),
                draw_x,
                draw_y,
                width=draw_w,
                height=draw_h,
                mask="auto",
                preserveAspectRatio=True,
            )

    c.showPage()
    c.save()
    return buf.getvalue()


def _truncate_text(c: rl_canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> str:
    if c.stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "..."
    trimmed = text
    while len(trimmed) > 1 and c.stringWidth(trimmed + ellipsis, font_name, font_size) > max_width:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis
