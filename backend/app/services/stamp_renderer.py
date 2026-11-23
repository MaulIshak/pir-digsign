"""
Modul inti rendering stempel tanda tangan visual + konversi koordinat layar -> PDF.

Desain minimalis & bersih (menyerupai stempel tanda tangan profesional):
- Latar transparan secara default (opsi putih tersedia).
- KIRI (opsional, `show_qr`): QR code kotak penuh setinggi blok utama (error correction H).
- KANAN: Gambar tanda tangan PNG transparan berukuran besar & proporsional (rasio terjaga),
  dengan bingkai tipis opsional (`show_border`) dan teks mikro abu-abu opsional (`show_labels`:
  "Digitally signed" di kiri atas & "Simple signed" di kiri bawah).
- BAWAH (opsional, `show_name` / `show_date`): Nama jelas, jabatan, dan tanggal/waktu WIB.
"""

import io
from datetime import datetime, timedelta, timezone
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
    """
    if canvas_w <= 0 or canvas_h <= 0:
        raise ValueError("Dimensi canvas pratinjau harus lebih besar dari 0.")

    scale_x = pdf_page_w / canvas_w
    scale_y = pdf_page_h / canvas_h

    pdf_x = screen_x * scale_x
    pdf_w = screen_w * scale_x
    pdf_h = screen_h * scale_y
    pdf_y = pdf_page_h - ((screen_y + screen_h) * scale_y)

    pdf_w = max(30.0, min(pdf_w, pdf_page_w))
    pdf_h = max(20.0, min(pdf_h, pdf_page_h))
    pdf_x = max(0.0, min(pdf_x, pdf_page_w - pdf_w))
    pdf_y = max(0.0, min(pdf_y, pdf_page_h - pdf_h))

    return pdf_x, pdf_y, pdf_w, pdf_h


def generate_qr_pil_image(url: str) -> Image.Image:
    """Membuat QR code beresolusi tinggi dengan error correction level H tanpa margin berlebih."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=0,
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
    transparent_background: bool = True,
    show_qr: bool = True,
    show_labels: bool = True,
    show_name: bool = False,
    show_date: bool = False,
    show_border: bool = True,
) -> bytes:
    """
    Merender blok stempel horizontal sebagai 1 halaman PDF vektor presisi (ReportLab)
    dengan ukuran tepat (width_pt x height_pt) untuk ditanam sebagai Signature Widget Appearance.
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    pad = 4.0 if (show_border and show_labels) else 1.5
    gray_micro = HexColor("#6B7280")
    border_color = HexColor("#374151")
    dark_text = HexColor("#111827")

    # Latar belakang putih hanya jika pengguna mematikan mode transparan
    if not transparent_background:
        c.setFillColor(Color(1, 1, 1, alpha=1.0))
        c.rect(0, 0, width_pt, height_pt, stroke=0, fill=1)

    # Hitung tinggi footer opsional (hanya jika show_name atau show_date aktif)
    meta_font_size = max(5.2, min(7.0, height_pt * 0.085))
    name_font_size = max(5.8, min(8.0, height_pt * 0.095))
    line_h = meta_font_size + 2.0

    footer_items = []
    if show_name and signer_name.strip():
        footer_items.append(("name", signer_name.strip()))
        if signer_title and signer_title.strip():
            footer_items.append(("title", signer_title.strip()))
    if show_date:
        ts_str = signed_at.astimezone(WIB).strftime("%d/%m/%Y %H:%M WIB")
        footer_items.append(("date", ts_str))

    footer_h = (len(footer_items) * line_h + 3.0) if footer_items else 0.0

    # --- Render Footer Opsional di Bawah Blok ---
    if footer_items:
        cur_y = pad + (len(footer_items) - 1) * line_h
        for kind, text in footer_items:
            if kind == "name":
                c.setFillColor(dark_text)
                c.setFont("Helvetica-Bold", name_font_size)
                c.drawString(
                    pad,
                    cur_y,
                    _truncate_text(c, text, "Helvetica-Bold", name_font_size, width_pt - 2 * pad),
                )
            else:
                c.setFillColor(gray_micro)
                c.setFont("Helvetica", meta_font_size)
                c.drawString(
                    pad,
                    cur_y,
                    _truncate_text(c, text, "Helvetica", meta_font_size, width_pt - 2 * pad),
                )
            cur_y -= line_h

    # --- Area Utama (QR di kiri + Kotak Tanda Tangan di kanan) ---
    main_bottom = pad + footer_h
    main_top = height_pt - pad
    main_h = max(16.0, main_top - main_bottom)

    # Ukuran font mikro untuk "Digitally signed" & "Simple signed" (halus seperti referensi)
    micro_font_size = max(3.8, min(5.2, main_h * 0.09))

    # KIRI: QR Code penuh setinggi blok utama (jika show_qr=True)
    if show_qr:
        # QR kotak setinggi main_h, maksimal 44% lebar agar sisi kanan tetap lega untuk TTD
        qr_size = min(main_h, (width_pt - 2 * pad) * 0.44)
        qr_x = pad
        qr_y = main_bottom + (main_h - qr_size) / 2.0

        qr_img = generate_qr_pil_image(verify_url)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

        # Kotak kanan tepat berdampingan dengan QR (jarak kecil rapi)
        gap = max(2.5, min(6.0, width_pt * 0.02))
        sig_box_x = qr_x + qr_size + gap
        sig_box_y = qr_y
        sig_box_w = max(16.0, (width_pt - pad) - sig_box_x)
        sig_box_h = qr_size
    else:
        # Tanpa QR -> Tanda tangan memenuhi seluruh area utama!
        sig_box_x = pad
        sig_box_y = main_bottom
        sig_box_w = max(16.0, width_pt - 2 * pad)
        sig_box_h = main_h

    # Bingkai tipis di sekitar area tanda tangan (gaya referensi profesional)
    if show_border:
        c.setStrokeColor(border_color)
        c.setLineWidth(0.55)
        c.rect(sig_box_x, sig_box_y, sig_box_w, sig_box_h, stroke=1, fill=0)

    # Label mikro halus di kiri-atas & kiri-bawah kotak tanda tangan (opsional)
    inner_top_pad = 2.0
    inner_bottom_pad = 2.0
    if show_labels:
        top_label = "Digitally signed"
        bot_label = "Simple signed"
        label_x = sig_box_x + 3.0

        # Jika ada border, beri sedikit ruang latar di belakang teks agar garis tidak menabrak huruf
        c.setFont("Helvetica", micro_font_size)
        if show_border:
            top_w = c.stringWidth(top_label, "Helvetica", micro_font_size) + 3.0
            bot_w = c.stringWidth(bot_label, "Helvetica", micro_font_size) + 3.0
            c.setFillColor(Color(1, 1, 1, alpha=1.0))
            c.rect(label_x - 1.5, sig_box_y + sig_box_h - micro_font_size * 0.55, top_w, micro_font_size + 1.0, stroke=0, fill=1)
            c.rect(label_x - 1.5, sig_box_y - micro_font_size * 0.45, bot_w, micro_font_size + 1.0, stroke=0, fill=1)
            top_text_y = sig_box_y + sig_box_h - micro_font_size * 0.35
            bot_text_y = sig_box_y - micro_font_size * 0.25
        else:
            top_text_y = sig_box_y + sig_box_h - micro_font_size - 1.0
            bot_text_y = sig_box_y + 1.0
            inner_top_pad = micro_font_size + 2.5
            inner_bottom_pad = micro_font_size + 2.5

        c.setFillColor(gray_micro)
        c.drawString(label_x, top_text_y, _truncate_text(c, top_label, "Helvetica", micro_font_size, sig_box_w - 6.0))
        c.drawString(label_x, bot_text_y, _truncate_text(c, bot_label, "Helvetica", micro_font_size, sig_box_w - 6.0))

    # Gambar Tanda Tangan PNG Transparan (mengisi penuh kotak kanan, rasio aspek 100% terjaga)
    avail_w = max(10.0, sig_box_w - 6.0)
    avail_h = max(10.0, sig_box_h - inner_top_pad - inner_bottom_pad)

    with Image.open(io.BytesIO(signature_png_bytes)) as sig_pil:
        sig_rgba = sig_pil.convert("RGBA")
        sw, sh = sig_rgba.size
        if sw > 0 and sh > 0:
            ratio = min(avail_w / float(sw), avail_h / float(sh))
            draw_w = sw * ratio
            draw_h = sh * ratio
            draw_x = sig_box_x + (sig_box_w - draw_w) / 2.0
            draw_y = sig_box_y + inner_bottom_pad + (avail_h - draw_h) / 2.0

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
