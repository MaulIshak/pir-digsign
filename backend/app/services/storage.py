from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from app.config import get_settings


class StorageProvider(ABC):
    """Abstraksi penyimpanan file agar mudah berpindah antara Local dan S3/MinIO."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError


class _EncryptionMixin:
    def __init__(self, encryption_key: str = ""):
        self._fernet: Optional[Fernet] = None
        if encryption_key and encryption_key.strip():
            self._fernet = Fernet(encryption_key.strip().encode("utf-8"))

    def _encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data) if self._fernet else data

    def _decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(data) if self._fernet else data


class LocalStorageProvider(_EncryptionMixin, StorageProvider):
    def __init__(self, base_dir: str, encryption_key: str = ""):
        super().__init__(encryption_key=encryption_key)
        self.base_path = Path(base_dir).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        clean_key = key.lstrip("/").replace("..", "_")
        target = (self.base_path / clean_key).resolve()
        if not str(target).startswith(str(self.base_path)):
            raise ValueError("Path storage tidak valid (path traversal terdeteksi).")
        return target

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self._encrypt(data)
        target.write_bytes(payload)
        return key

    def read_bytes(self, key: str) -> bytes:
        target = self._resolve(key)
        if not target.exists():
            raise FileNotFoundError(f"File tidak ditemukan di storage: {key}")
        return self._decrypt(target.read_bytes())

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        if target.exists():
            target.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()


class S3StorageProvider(_EncryptionMixin, StorageProvider):
    """Adapter penyimpanan S3 / MinIO untuk lingkungan produksi."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        region: str = "ap-southeast-3",
        encryption_key: str = "",
    ):
        super().__init__(encryption_key=encryption_key)
        import boto3

        client_kwargs = {"region_name": region}
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key

        self.bucket = bucket
        self.client = boto3.client("s3", **client_kwargs)

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        payload = self._encrypt(data)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key.lstrip("/"),
            Body=payload,
            ContentType=content_type,
        )
        return key

    def read_bytes(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key.lstrip("/"))
        return self._decrypt(resp["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key.lstrip("/"))

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key.lstrip("/"))
            return True
        except ClientError:
            return False


_storage_instance: Optional[StorageProvider] = None


def get_storage() -> StorageProvider:
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    settings = get_settings()
    if settings.STORAGE_PROVIDER.lower() == "s3":
        _storage_instance = S3StorageProvider(
            bucket=settings.S3_BUCKET_NAME,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY_ID,
            secret_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            encryption_key=settings.STORAGE_ENCRYPTION_KEY,
        )
    else:
        _storage_instance = LocalStorageProvider(
            base_dir=settings.LOCAL_STORAGE_DIR,
            encryption_key=settings.STORAGE_ENCRYPTION_KEY,
        )
    return _storage_instance


def reset_storage_cache() -> None:
    global _storage_instance
    _storage_instance = None
