import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, documents, signatures, verify
from app.security import limiter
from app.services.signer_providers import get_signer_provider
from app.services.storage import get_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("digsign")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Buat tabel otomatis jika belum ada (untuk dev / quickstart Docker Compose)
    Base.metadata.create_all(bind=engine)
    # Pastikan direktori storage dan sertifikat self-signed dev siap saat startup
    get_storage()
    get_signer_provider()
    logger.info("%s backend berjalan (env=%s, signer=%s)", settings.APP_NAME, settings.APP_ENV, settings.SIGNER_PROVIDER)
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="API Aplikasi Tanda Tangan Digital (PAdES Incremental + QR Verifikasi Publik)",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

app.include_router(auth.router)
app.include_router(signatures.router)
app.include_router(documents.router)
app.include_router(verify.router)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "signer_provider": settings.SIGNER_PROVIDER,
        "storage_provider": settings.STORAGE_PROVIDER,
    }
