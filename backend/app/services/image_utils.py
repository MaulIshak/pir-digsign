import base64
import io
from PIL import Image


def decode_data_url_or_base64(raw: str) -> bytes:
    """Mendekode data URL (data:image/png;base64,...) atau base64 mentah menjadi bytes."""
    if "," in raw and raw.strip().lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw.strip())


def process_signature_image(image_bytes: bytes, remove_background: bool = False) -> bytes:
    """
    Memvalidasi gambar tanda tangan, opsional menghapus latar terang/putih otomatis,
    memangkas ruang kosong (auto-crop), dan mengonversi ke PNG RGBA transparan.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        rgba = img.convert("RGBA")

        # Batasi resolusi maksimal agar hemat memori & cepat dirender ke PDF
        max_dim = 1200
        if rgba.width > max_dim or rgba.height > max_dim:
            rgba.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        if remove_background:
            rgba = _remove_light_background(rgba)

        # Auto-crop ke bounding box tinta dengan sedikit padding
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            pad = 8
            left = max(0, bbox[0] - pad)
            top = max(0, bbox[1] - pad)
            right = min(rgba.width, bbox[2] + pad)
            bottom = min(rgba.height, bbox[3] + pad)
            rgba = rgba.crop((left, top, right, bottom))

        out = io.BytesIO()
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue()


def _remove_light_background(rgba: Image.Image, threshold: int = 215) -> Image.Image:
    """
    Menghapus latar putih/abu-abu terang pada foto/scan tanda tangan.
    Menggunakan transisi alpha halus (anti-aliased) agar garis tinta tetap tajam.
    """
    pixels = rgba.load()
    width, height = rgba.size

    # Estimasi warna latar dari 4 sudut gambar
    corners = [
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    ]
    corner_lums = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in corners if a > 128]
    bg_lum = sum(corner_lums) / len(corner_lums) if corner_lums else 250.0
    cutoff = min(threshold, max(165, int(bg_lum - 25)))
    soft_band = 35

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            # Saturasi warna tinta (biru/merah tidak dianggap latar abu-abu)
            chroma = max(r, g, b) - min(r, g, b)
            if lum >= cutoff and chroma < 28:
                pixels[x, y] = (r, g, b, 0)
            elif lum >= (cutoff - soft_band) and chroma < 28:
                ratio = (cutoff - lum) / float(soft_band)
                new_alpha = int(a * max(0.0, min(1.0, ratio)))
                pixels[x, y] = (r, g, b, new_alpha)

    return rgba


def bytes_to_png_data_url(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"
