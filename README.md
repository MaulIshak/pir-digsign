# PirDigSign — Aplikasi Web Tanda Tangan Digital (PAdES + QR Verifikasi)

Aplikasi web full-stack untuk mengunggah dokumen PDF, membuat tanda tangan (gambar tangan / upload gambar + hapus latar otomatis / ketik font tulisan tangan), menempatkan stempel visual (QR code kiri + tanda tangan kanan) di koordinat PDF asli, menanamkan tanda tangan kriptografis berstandar **PAdES** secara **incremental update** (`pyHanko`), mendukung multi-penanda tangan maupun penandatanganan ulang PDF yang sudah bertanda tangan, serta menyediakan halaman verifikasi publik (`/verify/{token}`).

---

## Catatan Hukum Penting (UU ITE & PP 71/2019)

> **PERHATIAN HUKUM:**
> Stempel visual + sertifikat *self-signed* (mode development bawaan proyek ini) tergolong **Tanda Tangan Elektronik Tidak Tersertifikasi** dan **TIDAK setara** dengan **Tanda Tangan Elektronik (TTE) Tersertifikasi** menurut **UU No. 11 Tahun 2008 jo. UU No. 19 Tahun 2016 jo. UU No. 1 Tahun 2024 (UU ITE)** serta **PP No. 71 Tahun 2019 (PP PSTE)**.
>
> Untuk memperoleh kekuatan hukum pembuktian penuh (TTE Tersertifikasi) di Indonesia, Anda **wajib** mengintegrasikan aplikasi ini dengan **PSrE (Penyelenggara Sertifikasi Elektronik) yang terdaftar dan diakui oleh Kementerian Komunikasi dan Digital (Komdigi)** — seperti **BSrE (BSSN)**, **PrivyID**, **Peruri Digital Security**, atau **VIDA** — melalui antarmuka modular [`PsreIndonesiaProvider`](backend/app/services/signer_providers.py) tanpa mengubah logika inti penandatanganan PDF.

---

## Arsitektur & Struktur Folder

```text
pir-digsign/
├── .env.example
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py                      # Entrypoint FastAPI, CORS, rate limiter, startup
│   │   ├── config.py                    # Konfigurasi environment (pydantic-settings)
│   │   ├── database.py                  # SQLAlchemy engine & SessionLocal
│   │   ├── models.py                    # Skema PostgreSQL (users, signatures, documents, document_signers, signature_records, audit_logs)
│   │   ├── schemas.py                   # Validasi request/response Pydantic
│   │   ├── security.py                  # Argon2id, JWT HttpOnly cookie, CSRF, 2FA TOTP, validasi magic bytes PDF
│   │   ├── routers/
│   │   │   ├── auth.py                  # Register, login, verifikasi email, 2FA TOTP
│   │   │   ├── signatures.py            # Simpan/daftar/hapus tanda tangan profil
│   │   │   ├── documents.py             # Upload PDF, sign incremental, invite multi-signer, download, revoke
│   │   │   └── verify.py                # Verifikasi publik QR (/verify/{token}) & cocokkan hash (/verify/upload)
│   │   └── services/
│   │       ├── storage.py               # Abstraksi LocalStorageProvider (+ Fernet at-rest) & S3StorageProvider
│   │       ├── email.py                 # ConsoleEmailProvider (dev) & SmtpEmailProvider (prod)
│   │       ├── image_utils.py           # Penghapusan latar otomatis & sanitasi PNG transparan
│   │       ├── stamp_renderer.py        # Render stempel horizontal (QR kiri + TTD kanan + metadata) & konversi koordinat
│   │       ├── pdf_signer.py            # Penandatanganan PAdES incremental pyHanko (Sig1..SigN) & inspeksi integritas
│   │       └── signer_providers.py      # SignerProvider ABC: LocalSelfSignedProvider, KmsHsmSignerProvider, PsreIndonesiaProvider
│   └── tests/
│       └── test_incremental_signing.py  # Tes otomatis lengkap (2x sign, 3x sign, tamper 1 byte, revoke, 2FA)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.ts
    └── src/
        ├── lib/
        │   ├── api.ts                   # REST client (HttpOnly cookie + X-CSRF-Token)
        │   ├── coordinates.ts           # Konversi koordinat layar -> PDF points
        │   └── types.ts
        ├── components/
        │   ├── Navbar.tsx
        │   ├── NativeModal.tsx          # Modal berbasis elemen native <dialog>
        │   ├── SignaturePadModal.tsx    # 3 mode: Gambar (signature_pad), Upload + hapus latar, Ketik font tulisan tangan
        │   ├── PdfViewerCanvas.tsx      # Pratinjau PDF per halaman (pdfjs-dist) + zoom
        │   ├── StampOverlay.tsx         # Drag & resize stempel (react-rnd) sesuai tampilan PDF akhir
        │   └── InviteSignersModal.tsx   # Undang penanda tangan berurutan
        └── app/
            ├── page.tsx                 # Beranda
            ├── login/page.tsx           # Login + challenge 2FA TOTP
            ├── register/page.tsx        # Registrasi + verifikasi email
            ├── verify-email/page.tsx
            ├── dashboard/page.tsx       # Daftar dokumen, upload PDF, unduh, cabut
            ├── signatures/page.tsx      # Koleksi tanda tangan & pengaturan 2FA
            ├── documents/[id]/page.tsx  # Studio penandatanganan PDF + audit trail
            ├── invite/[token]/page.tsx  # Terima undangan multi-signer
            └── verify/
                ├── page.tsx             # Verifikasi publik lewat upload PDF / input token
                └── [token]/page.tsx     # Halaman verifikasi publik tujuan QR code
```

---

## Cara Menjalankan (Langkah demi Langkah)

### Opsi 1: Menggunakan Docker Compose (Direkomendasikan)

1. Salin berkas konfigurasi environment:
   ```bash
   cp .env.example .env
   ```
   *(Opsional: ubah `JWT_SECRET_KEY`, `CERT_KEY_PASSPHRASE`, atau isi `TSA_URL=http://timestamp.digicert.com` jika ingin menambahkan timestamp RFC 3161).*

2. Jalankan seluruh layanan (PostgreSQL, FastAPI Backend, Next.js Frontend):
   ```bash
   docker compose up --build
   ```

3. Akses aplikasi:
   - **Frontend Web:** `http://localhost:3000`
   - **API Swagger Docs:** `http://localhost:8000/docs`

### Opsi 2: Menjalankan Lokal Tanpa Docker (Development)

**Backend (Python 3.12+):**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
*(Secara default tanpa PostgreSQL, backend dapat berjalan langsung memakai SQLite dev, atau set `DATABASE_URL=postgresql+psycopg2://...` ke PostgreSQL lokal Anda).*

**Frontend (Node.js 20+):**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

---

## Cara Mengetes (Verifikasi Kriteria Selesai)

### A. Pengujian Otomatis (`pytest`)
Menjalankan seluruh skenario kritis secara otomatis (konversi koordinat, penandatanganan 2x dan 3x secara incremental, validasi bahwa `Sig1` tetap `intact=True` & `valid=True`, upload ulang PDF bertanda tangan, deteksi ubah 1 byte -> `TIDAK VALID`, 2FA TOTP, serta pencabutan -> `DICABUT`):
```bash
cd backend
.venv/bin/pytest -v
```

### B. Pengujian Manual End-to-End di Browser

1. **Upload, Gambar TTD, Tempatkan Stempel, dan Unduh:**
   - Buka `http://localhost:3000/register`, buat akun baru (User 1).
   - Klik tautan verifikasi email (ditampilkan pada banner `[Dev Mode]` atau log backend).
   - Di **Dashboard**, unggah file PDF apa saja (maks 20 MB).
   - Klik **Buat Baru** untuk menggambar tanda tangan (atau upload foto tanda tangan dengan *Hapus latar otomatis*, atau ketik nama dengan font tulisan tangan).
   - Geser dan ubah ukuran kotak stempel (QR kiri + TTD kanan + teks *"Digitally signed"* & *"Simple signed"*) di atas pratinjau PDF, isi jabatan (opsional), lalu klik **Tandatangani Sekarang**.
   - Klik **Unduh PDF** dan buka file PDF tersebut untuk memastikan stempel tertanam langsung di halaman PDF.

2. **Pindai QR -> Status `VALID`:**
   - Pindai QR code di PDF (atau klik **Buka** pada panel *Tautan Verifikasi QR Publik* di kanan).
   - Halaman `/verify/{token}` akan menampilkan status **VALID**, nama penanda tangan, waktu, judul dokumen, dan hash SHA-256.
   - Unggah file PDF yang baru diunduh pada kotak *"Cocokkan File PDF Asli"* -> hasil **VALID**.

3. **Ubah 1 Byte pada PDF -> Status `TIDAK VALID`:**
   - Ubah tepat 1 byte pada PDF bertanda tangan:
     ```bash
     python3 -c "b=bytearray(open('dokumen_signed.pdf','rb').read()); b[-10]^=1; open('dokumen_tampered.pdf','wb').write(b)"
     ```
   - Unggah `dokumen_tampered.pdf` di halaman `/verify/{token}` atau `/verify` -> status langsung berubah menjadi **TIDAK VALID** (hash tidak cocok & integritas kriptografis rusak).

4. **Tanda Tangan ke-2 (Multi-Signer) & Cek Tanda Tangan ke-1 Tetap Valid:**
   - Dari halaman dokumen User 1, klik **Undang Penanda Tangan**, masukkan email User 2 (urutan ke-2), lalu salin tautan undangannya.
   - Buka jendela Incognito/browser lain, daftar/masuk sebagai User 2, lalu buka tautan undangan tersebut.
   - Tempatkan stempel User 2 di lokasi berbeda dan klik **Tandatangani Sekarang**.
   - Periksa panel **Tanda Tangan Kriptografis di PDF**: baik `Sig1` maupun `Sig2` keduanya berstatus **Utuh (Intact)**.
   - Anda juga dapat memverifikasi PDF akhir langsung via CLI `pyHanko`:
     ```bash
     cd backend
     .venv/bin/python -c "
     from app.services.pdf_signer import inspect_embedded_signatures
     for s in inspect_embedded_signatures(open('dokumen_2signers.pdf','rb').read()):
         print(s.field_name, '| intact:', s.intact, '| valid:', s.valid)
     "
     ```
   - Selain itu, Anda juga dapat mengunggah file PDF yang **sebelumnya sudah bertanda tangan** di Dashboard lalu menandatanganinya lagi — engine otomatis mendeteksi field lama di `/AcroForm` dan memakai field baru (`Sig3`, dst.) secara incremental tanpa merusak tanda tangan sebelumnya.

---

## Keamanan Produksi & Enkripsi At-Rest

Sebelum deploy ke produksi:
1. Set `APP_ENV=production`, `COOKIE_SECURE=true`, dan `JWT_SECRET_KEY` acak kuat (minimal 64 karakter).
2. Aktifkan enkripsi dokumen *at-rest* dengan mengisi `STORAGE_ENCRYPTION_KEY`:
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Untuk skala besar, gunakan `STORAGE_PROVIDER=s3` (AWS S3 / MinIO) dengan Server-Side Encryption (SSE-KMS).
3. Ganti `SIGNER_PROVIDER=self_signed` menjadi `kms_hsm` atau `psre_indonesia` agar kunci privat tidak pernah berada di disk server aplikasi.
4. Pasang Reverse Proxy HTTPS (Nginx/Caddy/Cloudflare) dengan HSTS dan batas ukuran body request 25 MB.
5. Gunakan Redis sebagai backend `slowapi` (`storage_uri="redis://..."`) bila menjalankan lebih dari satu replika worker backend.

---

## Daftar Kekurangan / Risiko & Saran Pengembangan Lanjutan

| No | Kekurangan / Risiko Saat Ini | Mitigasi & Saran Pengembangan Lanjutan |
|----|------------------------------|----------------------------------------|
| 1 | **Sertifikat Self-Signed (Dev)** tidak dipercaya otomatis oleh Adobe Reader/Foxit (muncul ikon kuning *Unknown Signer*) dan bukan TTE Tersertifikasi UU ITE. | Implementasikan adapter `PsreIndonesiaProvider` (BSrE/Privy/Peruri/VIDA) dan tanam rantai sertifikat Root CA Komdigi + LTV (OCSP/CRL) untuk PAdES-B-LT / B-LTA. |
| 2 | **Rate Limiter In-Memory (`slowapi`)** hanya berlaku per-proses worker dan reset saat restart. | Pindahkan storage rate limiter ke Redis pada deployment multi-worker/Kubernetes. |
| 3 | **Migrasi Database Otomatis (`create_all`)** tidak menangani perubahan skema tabel pada produksi yang sudah berisi data. | Tambahkan **Alembic** untuk migrasi skema database terversi. |
| 4 | **Enkripsi At-Rest Berbasis Satu Kunci Fernet** belum memiliki rotasi kunci otomatis. | Gunakan `MultiFernet` atau envelope encryption (DEK per dokumen dibungkus KEK di AWS/GCP KMS). |
| 5 | **Latar Belakang Upload Tanda Tangan** memakai algoritma ambang luminansi + chroma (cepat, tanpa GPU), kurang optimal untuk foto pencahayaan sangat gelap/berbayang. | Tambahkan opsi *slider threshold* di UI atau model segmentasi ringan (`rembg` / ONNX) di worker terpisah. |
| 6 | **PAdES Long-Term Validation (LTV / DSS)** dan **RFC 3161 TSA** bersifat opsional di dev karena membutuhkan koneksi internet ke TSA/OCSP/CRL. | Wajibkan TSA bersertifikat + embed DSS (*Document Security Store*) melalui `pyHanko` di produksi agar tanda tangan tetap dapat diverifikasi bertahun-tahun setelah sertifikat kedaluwarsa. |
| 7 | **Penandatanganan PDF Terenkripsi/Berpassword** atau **XFA Dynamic Forms** belum didukung. | Tambahkan alur dekripsi password PDF pengguna (sebelum signing) dan deteksi awal PDF XFA dengan pesan error yang ramah pengguna. |
