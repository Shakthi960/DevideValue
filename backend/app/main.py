from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import APP_VERSION
from app.core.logger import get_logger, setup_logging
from app.core.database import engine, Base


setup_logging()

logger = get_logger("app.main")


def ensure_inspection_extensions(db_engine):
    """Idempotently add newer inspection columns to existing DBs."""
    statements = [
        'ALTER TABLE inspections ADD COLUMN link_code VARCHAR(10)',
        'ALTER TABLE inspections ADD COLUMN working VARCHAR(20)',
        'ALTER TABLE inspections ADD COLUMN diagnostics_score FLOAT',
        'ALTER TABLE inspections ADD COLUMN diagnostics_report TEXT',
    ]

    for statement in statements:
        try:
            with db_engine.connect() as connection:
                connection.execute(
                    connection.text(statement)
                )
                connection.commit()
        except Exception:
            # Column already exists (or unsupported) - ignore.
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Device Valuation Platform API...")
    ensure_inspection_extensions(engine)
    yield
    logger.info("Shutting down Device Valuation Platform API...")
from app.models import Device, Inspection
from app.routes.inspection import router as inspection_router

from app.models.device_catalog import DeviceCatalog

from app.routes.device_catalog import router as device_catalog_router

from app.routes.photos import router as photo_router

from app.routes.ml_valuation import router as ml_valuation_router

from app.routes.rag import router as rag_router

from app.routes.device_knowledge import router as device_knowledge_router

from app.routes.photo_analysis import (
    router as photo_analysis_router
)

from app.routes.auth import router as auth_router

from app.routes.device_prices import router as device_prices_router

from app.routes.health import router as health_router
from app.routes.health import check_database

app = FastAPI(
    title="Device Valuation Platform API",
    description="AI-powered smartphone inspection and valuation platform",
    version=APP_VERSION,
    lifespan=lifespan
)

app.include_router(device_catalog_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://devide-value.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ml_valuation_router)
app.include_router(rag_router)
app.include_router(device_knowledge_router)

app.include_router(inspection_router)
app.include_router(photo_router)
app.include_router(
    photo_analysis_router
)
app.include_router(auth_router)
app.include_router(device_prices_router)
app.include_router(health_router)

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "message": "Device Valuation Platform API is running",
        "version": APP_VERSION
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": APP_VERSION
    }


@app.get("/health/database")
def database_health():
    return {
        "database": check_database()
    }