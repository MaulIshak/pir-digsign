from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_NAME: str = "PirDigSign"
    PUBLIC_BASE_URL: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security & JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_SUPER_SECRET_KEY_AT_LEAST_32_CHARS_LONG_DEV_ONLY"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    MAX_PDF_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    MAX_SIGNATURE_IMAGE_BYTES: int = 5 * 1024 * 1024  # 5 MB

    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_SIGN: str = "20/minute"
    RATE_LIMIT_VERIFY: str = "60/minute"

    # Database
    DATABASE_URL: str = "sqlite:///./dev_digsign.db"

    # Storage
    STORAGE_PROVIDER: str = "local"  # local | s3
    LOCAL_STORAGE_DIR: str = "./storage"
    STORAGE_ENCRYPTION_KEY: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET_NAME: str = "digsign-files"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "ap-southeast-3"

    # Cryptographic Signer
    SIGNER_PROVIDER: str = "self_signed"  # self_signed | kms_hsm | psre_indonesia
    CERT_DIR: str = "./certs"
    CERT_KEY_PASSPHRASE: str = "dev-cert-passphrase-change-me"
    CERT_COMMON_NAME: str = "PirDigSign Local CA (Development Self-Signed)"
    CERT_ORG_NAME: str = "PirDigSign Dev"
    TSA_URL: str = ""

    # PSrE Indonesia placeholders (Privy / Peruri / VIDA / BSrE)
    PSRE_VENDOR: str = "bsre"
    PSRE_API_URL: str = ""
    PSRE_API_KEY: str = ""
    PSRE_CLIENT_ID: str = ""

    # Email
    EMAIL_PROVIDER: str = "console"  # console | smtp
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@digsign.local"
    SMTP_USE_TLS: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV.lower() in ("development", "dev", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
