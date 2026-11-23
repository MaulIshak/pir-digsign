"""
Antarmuka SignerProvider untuk penandatanganan kriptografis PAdES (pyHanko).

Memisahkan logika utama penandatanganan PDF dari penyedia sertifikat/kunci privat:
1. LocalSelfSignedProvider  -> Development (file key terenkripsi & cert di filesystem, BUKAN di DB).
2. KmsHsmSignerProvider     -> Produksi dengan AWS KMS / GCP Cloud KMS / PKCS#11 HSM.
3. PsreIndonesiaProvider    -> Integrasi API PSrE terdaftar Komdigi (Privy / Peruri / VIDA / BSrE).
"""

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.sign import signers
from pyhanko.sign.timestamps import HTTPTimeStamper
from pyhanko_certvalidator.context import ValidationContext

from app.config import get_settings

logger = logging.getLogger("digsign.signer_provider")


class SignerProvider(ABC):
    """Interface abstrak penyedia identitas kriptografis penandatanganan PDF."""

    @abstractmethod
    def get_pyhanko_signer(self, signer_name: Optional[str] = None) -> signers.Signer:
        """Mengembalikan instance pyHanko Signer yang siap dipakai PdfSigner."""
        raise NotImplementedError

    @abstractmethod
    def get_validation_context(self) -> ValidationContext:
        """Mengembalikan trust root untuk memverifikasi tanda tangan lokal/PSrE."""
        raise NotImplementedError

    def get_timestamper(self) -> Optional[HTTPTimeStamper]:
        settings = get_settings()
        if settings.TSA_URL and settings.TSA_URL.strip():
            return HTTPTimeStamper(url=settings.TSA_URL.strip(), timeout=10)
        return None


class LocalSelfSignedProvider(SignerProvider):
    """
    Penyedia sertifikat self-signed untuk development.
    Private key dienkripsi passphrase & disimpan pada direktori terproteksi (chmod 600),
    TIDAK PERNAH disimpan di database biasa.
    """

    def __init__(self, cert_dir: str, passphrase: str, common_name: str, org_name: str):
        self.cert_dir = Path(cert_dir).resolve()
        self.passphrase = passphrase.encode("utf-8")
        self.common_name = common_name
        self.org_name = org_name
        self.key_path = self.cert_dir / "dev_signer.key.pem"
        self.cert_path = self.cert_dir / "dev_signer.crt.pem"
        self._ensure_dev_certificate()

    def _ensure_dev_certificate(self) -> None:
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.cert_dir, 0o700)
        except OSError:
            pass

        if self.key_path.exists() and self.cert_path.exists():
            return

        logger.info("Membuat sertifikat self-signed development baru di %s", self.cert_dir)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "ID"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.org_name),
                x509.NameAttribute(NameOID.COMMON_NAME, self.common_name),
            ]
        )

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365 * 3))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .sign(private_key=private_key, algorithm=hashes.SHA256())
        )

        encrypted_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(self.passphrase),
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)

        self.key_path.write_bytes(encrypted_key_pem)
        self.cert_path.write_bytes(cert_pem)
        try:
            os.chmod(self.key_path, 0o600)
            os.chmod(self.cert_path, 0o644)
        except OSError:
            pass

    def get_pyhanko_signer(self, signer_name: Optional[str] = None) -> signers.Signer:
        return signers.SimpleSigner.load(
            key_file=str(self.key_path),
            cert_file=str(self.cert_path),
            ca_chain_files=None,
            key_passphrase=self.passphrase,
        )

    def get_validation_context(self) -> ValidationContext:
        from asn1crypto import pem, x509 as asn1_x509

        cert_bytes = self.cert_path.read_bytes()
        if pem.detect(cert_bytes):
            _, _, der_bytes = pem.unarmor(cert_bytes)
        else:
            der_bytes = cert_bytes
        root_cert = asn1_x509.Certificate.load(der_bytes)
        return ValidationContext(trust_roots=[root_cert], allow_fetching=False)


class KmsHsmSignerProvider(SignerProvider):
    """
    Adapter produksi untuk Cloud KMS (AWS KMS / GCP Cloud KMS) atau PKCS#11 HSM.
    Private key tidak pernah keluar dari HSM/KMS; operasi digest signing didelegasikan via PKCS#11/KMS API.

    Implementasi produksi dapat memakai `pyhanko.sign.pkcs11.PKCS11Signer` atau subclass
    `pyhanko.sign.signers.ExternalSigner` yang memanggil KMS Sign API.
    """

    def __init__(self, key_id: str, cert_chain_path: str):
        self.key_id = key_id
        self.cert_chain_path = cert_chain_path

    def get_pyhanko_signer(self, signer_name: Optional[str] = None) -> signers.Signer:
        raise NotImplementedError(
            "KmsHsmSignerProvider adalah adapter produksi. "
            "Hubungkan pyhanko.sign.pkcs11.PKCS11Signer atau ExternalSigner ke AWS/GCP KMS "
            "dengan mengisi konfigurasi HSM/KMS pada environment."
        )

    def get_validation_context(self) -> ValidationContext:
        return ValidationContext(allow_fetching=True)


class PsreIndonesiaProvider(SignerProvider):
    """
    Adapter antarmuka untuk PSrE (Penyelenggara Sertifikasi Elektronik) terdaftar di Komdigi:
    - BSrE (BSSN)
    - PrivyID
    - Peruri Digital Security
    - VIDA

    Pola integrasi tanpa mengubah logika inti:
    1. Untuk PSrE berbasis remote-hash signing (CSC / Cloud Signature Consortium API):
       kembalikan subclass `pyhanko.sign.signers.ExternalSigner` yang mengirim hash SHA-256
       ByteRange ke endpoint PSrE dan menerima signature CMS/PKCS#7 balik untuk ditanam
       secara incremental ke PDF oleh `pdf_signer.py`.
    2. Untuk PSrE berbasis document-signing API (mis. BSrE /api/sign/pdf):
       panggil metode `sign_pdf_remote(...)` sebagai alternatif pada layer orchestrator.
    """

    def __init__(self, vendor: str, api_url: str, api_key: str, client_id: str = ""):
        self.vendor = vendor
        self.api_url = api_url
        self.api_key = api_key
        self.client_id = client_id

    def get_pyhanko_signer(self, signer_name: Optional[str] = None) -> signers.Signer:
        raise NotImplementedError(
            f"Adapter PSrE ({self.vendor}) memerlukan kredensial produksi & sertifikat elektronik terdaftar "
            f"dari PSrE Komdigi (API URL: {self.api_url or 'belum dikonfigurasi'})."
        )

    def get_validation_context(self) -> ValidationContext:
        # Produksi: muat Root CA Komdigi (Root CA Indonesia) & Intermediate CA PSrE terkait
        return ValidationContext(allow_fetching=True)


_signer_provider_instance: Optional[SignerProvider] = None


def get_signer_provider() -> SignerProvider:
    global _signer_provider_instance
    if _signer_provider_instance is not None:
        return _signer_provider_instance

    settings = get_settings()
    provider_type = settings.SIGNER_PROVIDER.lower()
    if provider_type == "kms_hsm":
        _signer_provider_instance = KmsHsmSignerProvider(
            key_id=os.getenv("KMS_KEY_ID", ""),
            cert_chain_path=os.getenv("KMS_CERT_CHAIN_PATH", ""),
        )
    elif provider_type == "psre_indonesia":
        _signer_provider_instance = PsreIndonesiaProvider(
            vendor=settings.PSRE_VENDOR,
            api_url=settings.PSRE_API_URL,
            api_key=settings.PSRE_API_KEY,
            client_id=settings.PSRE_CLIENT_ID,
        )
    else:
        _signer_provider_instance = LocalSelfSignedProvider(
            cert_dir=settings.CERT_DIR,
            passphrase=settings.CERT_KEY_PASSPHRASE,
            common_name=settings.CERT_COMMON_NAME,
            org_name=settings.CERT_ORG_NAME,
        )
    return _signer_provider_instance


def reset_signer_provider_cache() -> None:
    global _signer_provider_instance
    _signer_provider_instance = None
