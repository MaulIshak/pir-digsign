"""
Engine penandatanganan PDF kriptografis PAdES secara incremental dengan pyHanko.

Fitur utama:
1. Selalu memakai IncrementalPdfFileWriter sehingga tanda tangan ke-1..ke-(N-1) TIDAK pernah rusak.
2. Mendeteksi field tanda tangan yang sudah ada langsung dari /AcroForm PDF sehingga mendukung
   penandatanganan ulang PDF eksternal yang sudah memiliki tanda tangan sebelumnya.
3. Menanamkan stempel visual (QR kiri + tanda tangan kanan + metadata) langsung sebagai
   appearance stream Signature Widget (serta anotasi incremental untuk mode "semua halaman").
4. Mendukung RFC 3161 TSA timestamping opsional dengan graceful fallback.
5. Menyediakan fungsi inspeksi & validasi seluruh tanda tangan kriptografis tertanam di PDF.
"""

import binascii
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple

from pyhanko.pdf_utils import generic, layout
from pyhanko.pdf_utils.content import PdfContent
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.layout import BoxConstraints
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers
from pyhanko.sign.fields import MDPPerm, SigFieldSpec, SigSeedSubFilter
from pyhanko.sign.signers import PdfSignatureMetadata, PdfSigner
from pyhanko.sign.validation import async_validate_pdf_signature, validate_pdf_signature
from pyhanko.stamp import StaticStampStyle

from app.services.signer_providers import SignerProvider, get_signer_provider
from app.services.stamp_renderer import render_stamp_pdf_bytes

logger = logging.getLogger("digsign.pdf_signer")


class InMemoryPdfPage(PdfContent):
    """Mengimpor 1 halaman PDF vektor (hasil ReportLab) langsung dari memori sebagai Form XObject."""

    def __init__(self, pdf_bytes: bytes, page_ix: int = 0):
        self.pdf_bytes = pdf_bytes
        self.page_ix = page_ix
        super().__init__()

    def render(self) -> bytes:
        w = self._ensure_writer
        r = PdfFileReader(io.BytesIO(self.pdf_bytes), strict=False)
        xobj = w.import_page_as_xobject(r, page_ix=self.page_ix)
        resource_name = b"/Stamp" + binascii.hexlify(uuid.uuid4().bytes)
        self.resources.xobject[resource_name.decode("ascii")] = xobj

        x1, y1, x2, y2 = xobj.get_object()["/BBox"]
        self.box = BoxConstraints(width=abs(float(x1) - float(x2)), height=abs(float(y1) - float(y2)))
        return resource_name + b" Do"


@dataclass
class SignResult:
    signed_pdf_bytes: bytes
    field_name: str
    signed_at: datetime


@dataclass
class EmbeddedSignatureInfo:
    field_name: str
    signer_cn: Optional[str]
    signing_time: Optional[str]
    intact: bool
    valid: bool
    summary: str


def get_pdf_info(pdf_bytes: bytes) -> Tuple[int, List[Tuple[float, float]]]:
    """Mengembalikan jumlah halaman dan dimensi (width_pt, height_pt) tiap halaman."""
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    pages = reader.root["/Pages"]["/Kids"]
    # Gunakan reader.root untuk menghitung total halaman akurat (termasuk nested Pages tree)
    page_count = int(reader.root["/Pages"]["/Count"])
    dims: List[Tuple[float, float]] = []
    for idx in range(page_count):
        page_obj = reader.root["/Pages"]
        # pyHanko helper mengambil objek halaman by index
        page_ref = reader.find_page_for_modification(idx)[0]
        page_dict = page_ref.get_object()
        media_box = _resolve_page_box(page_dict)
        w = float(media_box[2]) - float(media_box[0])
        h = float(media_box[3]) - float(media_box[1])
        dims.append((w, h))
    return page_count, dims


def _resolve_page_box(page_dict) -> list:
    cur = page_dict
    while cur is not None:
        if "/CropBox" in cur:
            return cur["/CropBox"]
        if "/MediaBox" in cur:
            return cur["/MediaBox"]
        parent = cur.get("/Parent")
        cur = parent.get_object() if parent is not None else None
    return [0, 0, 595.28, 841.89]  # Default A4


def _collect_existing_field_names(reader: PdfFileReader) -> Set[str]:
    names: Set[str] = set()
    for sig in reader.embedded_signatures:
        if sig.field_name:
            names.add(str(sig.field_name))

    acroform = reader.root.get("/AcroForm")
    if acroform:
        acroform_obj = acroform.get_object()
        for field_ref in acroform_obj.get("/Fields", []):
            try:
                fobj = field_ref.get_object()
                t = fobj.get("/T")
                if t:
                    names.add(str(t))
            except Exception:
                continue
    return names


def _next_unique_sig_field_name(existing_names: Set[str]) -> str:
    idx = 1
    while f"Sig{idx}" in existing_names:
        idx += 1
    return f"Sig{idx}"


def _check_doc_mdp_allows_signing(reader: PdfFileReader) -> None:
    """Memastikan PDF tidak dikunci dengan sertifikasi DocMDP P=1 (NO_CHANGES)."""
    for sig in reader.embedded_signatures:
        try:
            mdp = sig.sig_object.get("/Reference")
            if not mdp:
                continue
            for ref in mdp:
                ref_obj = ref.get_object()
                if ref_obj.get("/TransformMethod") == "/DocMDP":
                    params = ref_obj.get("/TransformParams")
                    if params:
                        p_val = int(params.get_object().get("/P", 2))
                        if p_val == int(MDPPerm.NO_CHANGES):
                            raise ValueError(
                                "Dokumen ini dikunci oleh tanda tangan sertifikasi (DocMDP P=1) "
                                "yang melarang penambahan tanda tangan baru."
                            )
        except ValueError:
            raise
        except Exception:
            continue


def sign_pdf_incremental(
    pdf_bytes: bytes,
    signature_png_bytes: bytes,
    verify_url: str,
    signer_name: str,
    page: int,
    x: float,
    y: float,
    w: float,
    h: float,
    signer_title: Optional[str] = None,
    all_pages: bool = False,
    provider: Optional[SignerProvider] = None,
    transparent_background: bool = True,
    show_qr: bool = True,
    show_labels: bool = True,
    show_name: bool = False,
    show_date: bool = False,
    show_border: bool = True,
) -> SignResult:
    """
    Menanamkan stempel visual (QR kiri + tanda tangan kanan) dan tanda tangan kriptografis
    PAdES menggunakan pyHanko secara incremental update.

    Args:
        pdf_bytes: Byte PDF asli atau PDF yang sudah memiliki 1..N tanda tangan sebelumnya.
        signature_png_bytes: Byte PNG transparan tanda tangan pengguna.
        verify_url: URL publik verifikasi (https://domain/verify/{token}).
        signer_name: Nama jelas penanda tangan.
        page: Nomor halaman (1-based) tempat Signature Widget utama ditanam.
        x, y, w, h: Koordinat kotak stempel dalam PDF points (origin kiri-bawah).
        signer_title: Jabatan opsional.
        all_pages: Jika True, stempel visual juga ditambahkan ke halaman lain secara incremental.
        provider: SignerProvider (default mengikuti konfigurasi env).
    """
    signer_provider = provider or get_signer_provider()
    signed_at = datetime.now(timezone.utc)

    # 1. Baca PDF untuk cek jumlah halaman, DocMDP, dan field nama yang sudah ada
    reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    page_count = int(reader.root["/Pages"]["/Count"])
    if page < 1 or page > page_count:
        raise ValueError(f"Nomor halaman {page} di luar rentang dokumen (1..{page_count}).")

    _check_doc_mdp_allows_signing(reader)
    existing_fields = _collect_existing_field_names(reader)
    field_name = _next_unique_sig_field_name(existing_fields)

    # 2. Clamp koordinat sesuai dimensi halaman target
    page_idx = page - 1
    page_ref = reader.find_page_for_modification(page_idx)[0]
    media_box = _resolve_page_box(page_ref.get_object())
    page_min_x, page_min_y = float(media_box[0]), float(media_box[1])
    page_w = float(media_box[2]) - page_min_x
    page_h = float(media_box[3]) - page_min_y

    box_w = max(40.0, min(float(w), page_w))
    box_h = max(30.0, min(float(h), page_h))
    box_x1 = page_min_x + max(0.0, min(float(x), page_w - box_w))
    box_y1 = page_min_y + max(0.0, min(float(y), page_h - box_h))
    box_x2 = box_x1 + box_w
    box_y2 = box_y1 + box_h

    # 3. Render stempel visual vektor (ReportLab 1-halaman PDF)
    stamp_pdf_bytes = render_stamp_pdf_bytes(
        verify_url=verify_url,
        signature_png_bytes=signature_png_bytes,
        signer_name=signer_name,
        signed_at=signed_at,
        width_pt=box_w,
        height_pt=box_h,
        signer_title=signer_title,
        transparent_background=transparent_background,
        show_qr=show_qr,
        show_labels=show_labels,
        show_name=show_name,
        show_date=show_date,
        show_border=show_border,
    )

    # 4. Buka dengan IncrementalPdfFileWriter (TIDAK pernah menulis ulang revisi sebelumnya!)
    in_buf = io.BytesIO(pdf_bytes)
    writer = IncrementalPdfFileWriter(in_buf, strict=False)

    # Tambahkan field tanda tangan baru (Sig1, Sig2, ...) pada halaman utama
    fields.append_signature_field(
        writer,
        SigFieldSpec(
            sig_field_name=field_name,
            on_page=page_idx,
            box=(box_x1, box_y1, box_x2, box_y2),
        ),
    )

    # Jika pengguna memilih "semua halaman", tambahkan anotasi stempel visual
    # pada halaman lain di dalam IncrementalPdfFileWriter yang sama (non-destruktif)
    if all_pages and page_count > 1:
        _append_visual_stamps_to_other_pages(
            writer=writer,
            stamp_pdf_bytes=stamp_pdf_bytes,
            primary_page_idx=page_idx,
            page_count=page_count,
            rel_x=float(x),
            rel_y=float(y),
            box_w=box_w,
            box_h=box_h,
        )

    # 5. Bungkus stempel vektor sebagai StaticStampStyle untuk Signature Widget Appearance
    imported_stamp = InMemoryPdfPage(stamp_pdf_bytes, page_ix=0)
    stamp_style = StaticStampStyle(
        background=imported_stamp,
        border_width=0,
        background_opacity=1.0,
        background_layout=layout.SimpleBoxLayoutRule(
            x_align=layout.AxisAlignment.ALIGN_MID,
            y_align=layout.AxisAlignment.ALIGN_MID,
            margins=layout.Margins.uniform(0),
        ),
    )

    # 6. Metadata PAdES & Signer dari SignerProvider
    cms_signer = signer_provider.get_pyhanko_signer(signer_name=signer_name)
    timestamper = signer_provider.get_timestamper()

    reason_text = f"Ditandatangani secara digital oleh {signer_name}"
    if signer_title:
        reason_text += f" ({signer_title})"

    sig_meta = PdfSignatureMetadata(
        field_name=field_name,
        md_algorithm="sha256",
        subfilter=SigSeedSubFilter.PADES,
        name=signer_name,
        reason=reason_text,
        location="Indonesia",
        certify=False,  # Approval signature agar penanda tangan berikutnya tetap diizinkan
    )

    pdf_signer = PdfSigner(
        signature_meta=sig_meta,
        signer=cms_signer,
        stamp_style=stamp_style,
        timestamper=timestamper,
    )

    out_buf = io.BytesIO()
    try:
        pdf_signer.sign_pdf(writer, output=out_buf)
    except Exception as exc:
        # Jika gagal khusus karena TSA offline/timeout, ulangi tanpa TSA agar tidak memblokir dev
        if timestamper is not None:
            logger.warning("Timestamping RFC 3161 gagal (%s), mengulangi tanpa TSA.", exc)
            writer_retry = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes), strict=False)
            fields.append_signature_field(
                writer_retry,
                SigFieldSpec(
                    sig_field_name=field_name,
                    on_page=page_idx,
                    box=(box_x1, box_y1, box_x2, box_y2),
                ),
            )
            if all_pages and page_count > 1:
                _append_visual_stamps_to_other_pages(
                    writer=writer_retry,
                    stamp_pdf_bytes=stamp_pdf_bytes,
                    primary_page_idx=page_idx,
                    page_count=page_count,
                    rel_x=float(x),
                    rel_y=float(y),
                    box_w=box_w,
                    box_h=box_h,
                )
            style_retry = StaticStampStyle(
                background=InMemoryPdfPage(stamp_pdf_bytes, page_ix=0),
                border_width=0,
                background_opacity=1.0,
                background_layout=layout.SimpleBoxLayoutRule(
                    x_align=layout.AxisAlignment.ALIGN_MID,
                    y_align=layout.AxisAlignment.ALIGN_MID,
                    margins=layout.Margins.uniform(0),
                ),
            )
            pdf_signer_no_tsa = PdfSigner(
                signature_meta=sig_meta,
                signer=cms_signer,
                stamp_style=style_retry,
                timestamper=None,
            )
            out_buf = io.BytesIO()
            pdf_signer_no_tsa.sign_pdf(writer_retry, output=out_buf)
        else:
            raise

    return SignResult(
        signed_pdf_bytes=out_buf.getvalue(),
        field_name=field_name,
        signed_at=signed_at,
    )


def _append_visual_stamps_to_other_pages(
    writer: IncrementalPdfFileWriter,
    stamp_pdf_bytes: bytes,
    primary_page_idx: int,
    page_count: int,
    rel_x: float,
    rel_y: float,
    box_w: float,
    box_h: float,
) -> None:
    """
    Menambahkan anotasi stempel visual (Form XObject /Stamp) pada halaman selain halaman utama
    secara murni incremental melalui IncrementalPdfFileWriter.
    """
    stamp_reader = PdfFileReader(io.BytesIO(stamp_pdf_bytes), strict=False)
    xobj_ref = writer.import_page_as_xobject(stamp_reader, page_ix=0)

    for idx in range(page_count):
        if idx == primary_page_idx:
            continue
        page_ref = writer.find_page_for_modification(idx)[0]
        page_dict = page_ref.get_object()
        media_box = _resolve_page_box(page_dict)
        p_min_x, p_min_y = float(media_box[0]), float(media_box[1])
        pw = float(media_box[2]) - p_min_x
        ph = float(media_box[3]) - p_min_y

        cw = max(40.0, min(box_w, pw))
        ch = max(30.0, min(box_h, ph))
        cx1 = p_min_x + max(0.0, min(rel_x, pw - cw))
        cy1 = p_min_y + max(0.0, min(rel_y, ph - ch))

        annot = generic.DictionaryObject(
            {
                generic.pdf_name("/Type"): generic.pdf_name("/Annot"),
                generic.pdf_name("/Subtype"): generic.pdf_name("/Stamp"),
                generic.pdf_name("/Rect"): generic.ArrayObject(
                    [
                        generic.FloatObject(cx1),
                        generic.FloatObject(cy1),
                        generic.FloatObject(cx1 + cw),
                        generic.FloatObject(cy1 + ch),
                    ]
                ),
                generic.pdf_name("/F"): generic.NumberObject(4),  # Print flag
                generic.pdf_name("/AP"): generic.DictionaryObject(
                    {generic.pdf_name("/N"): xobj_ref}
                ),
            }
        )
        annot_ref = writer.add_object(annot)

        if "/Annots" in page_dict:
            annots_obj = page_dict["/Annots"]
            if isinstance(annots_obj, generic.IndirectObject):
                arr = annots_obj.get_object()
                arr.append(annot_ref)
                writer.update_container(arr)
            else:
                annots_obj.append(annot_ref)
                writer.update_container(page_dict)
        else:
            page_dict[generic.pdf_name("/Annots")] = generic.ArrayObject([annot_ref])
            writer.update_container(page_dict)


def _extract_sig_meta(sig) -> Tuple[str, Optional[str], Optional[str]]:
    field_name = str(sig.field_name or "Unknown")
    signer_cn: Optional[str] = None
    signing_time: Optional[str] = None
    try:
        cert = sig.signer_cert
        if cert is not None:
            signer_cn = cert.subject.human_friendly
    except Exception:
        pass
    try:
        raw_m = sig.sig_object.get("/M")
        if raw_m:
            signing_time = str(raw_m)
    except Exception:
        pass
    return field_name, signer_cn, signing_time


async def async_inspect_embedded_signatures(
    pdf_bytes: bytes,
    provider: Optional[SignerProvider] = None,
) -> List[EmbeddedSignatureInfo]:
    """Versi async untuk dipanggil dari endpoint `async def` FastAPI tanpa konflik event loop."""
    signer_provider = provider or get_signer_provider()
    vc = signer_provider.get_validation_context()
    results: List[EmbeddedSignatureInfo] = []

    try:
        reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    except Exception as exc:
        logger.warning("Gagal membaca PDF untuk inspeksi tanda tangan: %s", exc)
        return results

    for sig in reader.embedded_signatures:
        field_name, signer_cn, signing_time = _extract_sig_meta(sig)
        try:
            status = await async_validate_pdf_signature(sig, signer_validation_context=vc)
            intact = bool(status.intact)
            valid = bool(status.valid)
            summary = status.summary()
        except Exception as exc:
            intact = False
            valid = False
            summary = f"Gagal memvalidasi: {exc}"

        results.append(
            EmbeddedSignatureInfo(
                field_name=field_name,
                signer_cn=signer_cn,
                signing_time=signing_time,
                intact=intact,
                valid=valid,
                summary=summary,
            )
        )

    return results


def inspect_embedded_signatures(
    pdf_bytes: bytes,
    provider: Optional[SignerProvider] = None,
) -> List[EmbeddedSignatureInfo]:
    """
    Memeriksa seluruh tanda tangan kriptografis PAdES/PKCS#7 yang tertanam dalam file PDF
    dan memvalidasi integritas byte-range serta validitas kriptografis masing-masing revisi.
    Aman dipanggil baik dari fungsi sync maupun jika sudah ada event loop aktif.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def _run_sync() -> List[EmbeddedSignatureInfo]:
        signer_provider = provider or get_signer_provider()
        vc = signer_provider.get_validation_context()
        results: List[EmbeddedSignatureInfo] = []

        try:
            reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
        except Exception as exc:
            logger.warning("Gagal membaca PDF untuk inspeksi tanda tangan: %s", exc)
            return results

        for sig in reader.embedded_signatures:
            field_name, signer_cn, signing_time = _extract_sig_meta(sig)
            try:
                status = validate_pdf_signature(sig, signer_validation_context=vc)
                intact = bool(status.intact)
                valid = bool(status.valid)
                summary = status.summary()
            except Exception as exc:
                intact = False
                valid = False
                summary = f"Gagal memvalidasi: {exc}"

            results.append(
                EmbeddedSignatureInfo(
                    field_name=field_name,
                    signer_cn=signer_cn,
                    signing_time=signing_time,
                    intact=intact,
                    valid=valid,
                    summary=summary,
                )
            )
        return results

    try:
        asyncio.get_running_loop()
        # Jika sedang berada dalam event loop aktif, jalankan di thread terpisah
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run_sync).result()
    except RuntimeError:
        return _run_sync()
