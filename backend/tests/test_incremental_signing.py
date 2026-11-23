import base64
import io
import os
import tempfile
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas as rl_canvas

from app.services.pdf_signer import inspect_embedded_signatures, sign_pdf_incremental
from app.services.signer_providers import LocalSelfSignedProvider
from app.services.stamp_renderer import screen_to_pdf_coords


def _make_sample_pdf(num_pages: int = 2) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(595.28, 841.89))
    for i in range(1, num_pages + 1):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 760, f"Dokumen Uji Tanda Tangan Digital - Halaman {i}")
        c.setFont("Helvetica", 11)
        c.drawString(72, 730, "Ini adalah dokumen PDF contoh untuk menguji incremental PAdES signing.")
        c.showPage()
    c.save()
    return buf.getvalue()


def _make_sample_signature_png(with_white_bg: bool = False) -> bytes:
    bg = (255, 255, 255, 255) if with_white_bg else (0, 0, 0, 0)
    img = Image.new("RGBA", (320, 120), bg)
    draw = ImageDraw.Draw(img)
    draw.line([(20, 90), (80, 30), (140, 85), (210, 25), (290, 75)], fill=(15, 23, 42, 255), width=6)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_screen_to_pdf_coordinate_conversion():
    # Layar 595x842, stempel di (100, 700) ukuran 200x80 (origin kiri-atas)
    x, y, w, h = screen_to_pdf_coords(
        screen_x=100,
        screen_y=700,
        screen_w=200,
        screen_h=80,
        canvas_w=595.0,
        canvas_h=842.0,
        pdf_page_w=595.0,
        pdf_page_h=842.0,
    )
    assert round(x, 2) == 100.0
    assert round(w, 2) == 200.0
    assert round(h, 2) == 80.0
    # Origin kiri-bawah: 842 - (700 + 80) = 62
    assert round(y, 2) == 62.0


def test_incremental_signing_two_signers_and_tamper_detection(tmp_path: Path):
    provider = LocalSelfSignedProvider(
        cert_dir=str(tmp_path / "certs"),
        passphrase="test-passphrase-123",
        common_name="Test Local Signer",
        org_name="Test Org",
    )

    orig_pdf = _make_sample_pdf(num_pages=2)
    sig_png = _make_sample_signature_png(with_white_bg=False)

    # Tanda tangan ke-1 (Sig1)
    res1 = sign_pdf_incremental(
        pdf_bytes=orig_pdf,
        signature_png_bytes=sig_png,
        verify_url="http://localhost:3000/verify/token-signer-1",
        signer_name="Budi Santoso",
        signer_title="Direktur Utama",
        page=1,
        x=60,
        y=80,
        w=220,
        h=95,
        all_pages=False,
        provider=provider,
    )
    assert res1.field_name == "Sig1"

    sigs_after_1 = inspect_embedded_signatures(res1.signed_pdf_bytes, provider=provider)
    assert len(sigs_after_1) == 1
    assert sigs_after_1[0].field_name == "Sig1"
    assert sigs_after_1[0].intact is True
    assert sigs_after_1[0].valid is True

    # Tanda tangan ke-2 (Sig2) pada PDF hasil tanda tangan ke-1
    res2 = sign_pdf_incremental(
        pdf_bytes=res1.signed_pdf_bytes,
        signature_png_bytes=sig_png,
        verify_url="http://localhost:3000/verify/token-signer-2",
        signer_name="Siti Rahma",
        signer_title="Manajer Legal",
        page=1,
        x=310,
        y=80,
        w=220,
        h=95,
        all_pages=False,
        provider=provider,
    )
    assert res2.field_name == "Sig2"

    # KRITERIA WAJIB: Sig1 DAN Sig2 keduanya harus tetap intact & valid!
    sigs_after_2 = inspect_embedded_signatures(res2.signed_pdf_bytes, provider=provider)
    assert len(sigs_after_2) == 2
    by_name = {s.field_name: s for s in sigs_after_2}
    assert by_name["Sig1"].intact is True and by_name["Sig1"].valid is True
    assert by_name["Sig2"].intact is True and by_name["Sig2"].valid is True

    # Tanda tangan ke-3 dengan all_pages=True (menambah anotasi stempel di halaman 2)
    res3 = sign_pdf_incremental(
        pdf_bytes=res2.signed_pdf_bytes,
        signature_png_bytes=sig_png,
        verify_url="http://localhost:3000/verify/token-signer-3",
        signer_name="Andi Wijaya",
        page=2,
        x=60,
        y=80,
        w=220,
        h=95,
        all_pages=True,
        provider=provider,
    )
    assert res3.field_name == "Sig3"
    sigs_after_3 = inspect_embedded_signatures(res3.signed_pdf_bytes, provider=provider)
    assert len(sigs_after_3) == 3
    assert all(s.intact for s in sigs_after_3)

    # Uji ubah 1 byte di dalam body PDF -> integritas kriptografis HARUS rusak (intact=False)
    tampered = bytearray(res2.signed_pdf_bytes)
    marker_idx = tampered.find(b"Dokumen Uji")
    if marker_idx != -1:
        tampered[marker_idx] ^= 0x01
    else:
        tampered[100] ^= 0x01
    sigs_tampered = inspect_embedded_signatures(bytes(tampered), provider=provider)
    assert any(not s.intact for s in sigs_tampered)


def test_full_api_e2e_multi_signer_verify_tamper_and_revoke(tmp_path: Path, monkeypatch):
    # Konfigurasi environment terisolasi untuk test E2E
    db_file = tmp_path / "test_e2e.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CERT_DIR", str(tmp_path / "certs"))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("COOKIE_SECURE", "false")

    # Reload config & database engine agar memakai SQLite tmp_path
    from app import config, database, main
    from app.services import signer_providers, storage

    config.get_settings.cache_clear()
    storage.reset_storage_cache()
    signer_providers.reset_signer_provider_cache()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    database.Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = override_get_db
    # Pastikan lifespan memakai engine test
    monkeypatch.setattr(main, "engine", test_engine)

    with TestClient(main.app) as client1, TestClient(main.app) as client2:
        # 1. Register User 1 (Pemilik) & Verifikasi Email
        r = client1.post(
            "/auth/register",
            json={"name": "Budi Santoso", "email": "budi@example.com", "password": "PasswordKuat123!"},
        )
        assert r.status_code == 201, r.text
        csrf1 = r.json()["csrf_token"]
        h1 = {"X-CSRF-Token": csrf1}
        dev_verify_link = r.json()["dev_verify_link"]
        assert dev_verify_link and "token=" in dev_verify_link
        v_token = dev_verify_link.split("token=")[1]
        assert client1.get(f"/auth/verify-email?token={v_token}").status_code == 200

        # Uji 2FA setup & enable
        setup_2fa = client1.post("/auth/2fa/setup", headers=h1)
        assert setup_2fa.status_code == 200
        totp_secret = setup_2fa.json()["secret"]
        code = pyotp.TOTP(totp_secret).now()
        assert client1.post("/auth/2fa/enable", json={"code": code}, headers=h1).status_code == 200

        # 2. Simpan tanda tangan User 1 (dengan penghapusan latar otomatis)
        sig_b64 = base64.b64encode(_make_sample_signature_png(with_white_bg=True)).decode("ascii")
        sig_res = client1.post(
            "/signatures",
            json={
                "label": "TTD Budi",
                "type": "upload",
                "image_base64": f"data:image/png;base64,{sig_b64}",
                "remove_background": True,
            },
            headers=h1,
        )
        assert sig_res.status_code == 201, sig_res.text
        sig1_id = sig_res.json()["id"]

        # 3. Tolak file non-PDF (magic bytes palsu)
        bad_upload = client1.post(
            "/documents",
            files={"file": ("palsu.pdf", b"NOT_A_PDF_CONTENT", "application/pdf")},
            headers=h1,
        )
        assert bad_upload.status_code == 400

        # 4. Upload PDF valid oleh User 1
        sample_pdf = _make_sample_pdf(2)
        up = client1.post(
            "/documents",
            files={"file": ("kontrak_kerja.pdf", sample_pdf, "application/pdf")},
            data={"title": "Kontrak Kerja 2026"},
            headers=h1,
        )
        assert up.status_code == 201, up.text
        doc_id = up.json()["id"]

        # 5. User 1 menandatangani sendiri (self-sign -> Sig1)
        sign1 = client1.post(
            f"/documents/{doc_id}/sign",
            json={
                "signature_id": sig1_id,
                "page": 1,
                "x": 50,
                "y": 90,
                "w": 210,
                "h": 90,
                "signer_title": "Direktur",
            },
            headers=h1,
        )
        assert sign1.status_code == 200, sign1.text
        rec1 = sign1.json()["signature_records"][0]
        token1 = rec1["token"]
        assert len(token1) >= 22  # >= 128 bit
        assert rec1["field_name"] == "Sig1"

        # 6. Verifikasi QR publik -> VALID
        v1 = client1.get(f"/verify/{token1}")
        assert v1.status_code == 200
        assert v1.json()["status"] == "VALID"
        assert v1.json()["signer_name"] == "Budi Santoso"

        # 7. Unduh PDF bertanda tangan & verifikasi upload -> VALID
        dl1 = client1.get(f"/documents/{doc_id}/download")
        assert dl1.status_code == 200
        signed_pdf_1 = dl1.content

        vu_valid = client1.post(
            "/verify/upload",
            files={"file": ("kontrak_signed.pdf", signed_pdf_1, "application/pdf")},
            data={"token": token1},
        )
        assert vu_valid.status_code == 200
        assert vu_valid.json()["status"] == "VALID"

        # 8. Ubah 1 byte pada PDF -> unggah ulang -> HARUS TIDAK VALID!
        tampered_pdf = bytearray(signed_pdf_1)
        tampered_pdf[-5] ^= 0x01
        vu_tampered = client1.post(
            "/verify/upload",
            files={"file": ("kontrak_tampered.pdf", bytes(tampered_pdf), "application/pdf")},
            data={"token": token1},
        )
        assert vu_tampered.status_code == 200
        assert vu_tampered.json()["status"] == "TIDAK VALID"

        # 9. Multi-signer: User 1 mengundang User 2 -> User 2 menandatangani (Sig2)
        r2 = client2.post(
            "/auth/register",
            json={"name": "Siti Rahma", "email": "siti@example.com", "password": "PasswordKuat456!"},
        )
        assert r2.status_code == 201
        h2 = {"X-CSRF-Token": r2.json()["csrf_token"]}

        sig2_res = client2.post(
            "/signatures",
            json={
                "label": "TTD Siti",
                "type": "draw",
                "image_base64": f"data:image/png;base64,{sig_b64}",
            },
            headers=h2,
        )
        assert sig2_res.status_code == 201
        sig2_id = sig2_res.json()["id"]

        inv = client1.post(
            f"/documents/{doc_id}/invite",
            json={"signers": [{"email": "siti@example.com", "name": "Siti Rahma", "order_no": 2}]},
            headers=h1,
        )
        assert inv.status_code == 200

        sign2 = client2.post(
            f"/documents/{doc_id}/sign",
            json={
                "signature_id": sig2_id,
                "page": 1,
                "x": 300,
                "y": 90,
                "w": 210,
                "h": 90,
                "signer_title": "Head of Legal",
            },
            headers=h2,
        )
        assert sign2.status_code == 200, sign2.text
        detail_after_2 = sign2.json()
        assert len(detail_after_2["signature_records"]) == 2
        assert len(detail_after_2["embedded_signatures"]) == 2
        # Pastikan KEDUA tanda tangan kriptografis tetap valid & intact!
        for emb in detail_after_2["embedded_signatures"]:
            assert emb["intact"] is True
            assert emb["valid"] is True

        # Pastikan upload PDF akhir (2 tanda tangan) tetap VALID terhadap token1 maupun token2!
        final_pdf = client1.get(f"/documents/{doc_id}/download").content
        token2 = detail_after_2["signature_records"][1]["token"]
        for tok in (token1, token2):
            vu_multi = client1.post(
                "/verify/upload",
                files={"file": ("final_2signers.pdf", final_pdf, "application/pdf")},
                data={"token": tok},
            )
            assert vu_multi.status_code == 200
            assert vu_multi.json()["status"] == "VALID"

        # 10. Upload ulang PDF yang SUDAH bertanda tangan (skenario dokumen eksternal bertanda tangan)
        up_existing = client1.post(
            "/documents",
            files={"file": ("sudah_ttd.pdf", final_pdf, "application/pdf")},
            data={"title": "Dokumen Sudah Bertanda Tangan"},
            headers=h1,
        )
        assert up_existing.status_code == 201
        ext_doc_id = up_existing.json()["id"]
        assert len(up_existing.json()["embedded_signatures"]) == 2

        sign3 = client1.post(
            f"/documents/{ext_doc_id}/sign",
            json={"signature_id": sig1_id, "page": 2, "x": 60, "y": 90, "w": 210, "h": 90},
            headers=h1,
        )
        assert sign3.status_code == 200, sign3.text
        assert sign3.json()["signature_records"][0]["field_name"] == "Sig3"
        assert len(sign3.json()["embedded_signatures"]) == 3
        assert all(e["intact"] and e["valid"] for e in sign3.json()["embedded_signatures"])

        # 11. Cabut tanda tangan (revoke) -> /verify/{token} menjadi DICABUT
        rev = client1.post(
            f"/documents/{doc_id}/revoke",
            json={"reason": "Dokumen diganti revisi baru"},
            headers=h1,
        )
        assert rev.status_code == 200
        assert rev.json()["status"] == "revoked"

        v_revoked = client1.get(f"/verify/{token1}")
        assert v_revoked.status_code == 200
        assert v_revoked.json()["status"] == "DICABUT"

    main.app.dependency_overrides.clear()
