from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.logger import get_logger, setup_logging
from app.core.database import engine, Base


setup_logging()

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Device Valuation Platform API...")
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

app = FastAPI(
    title="Device Valuation Platform API",
    description="AI-powered smartphone inspection and valuation platform",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(device_catalog_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
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

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "message": "Device Valuation Platform API is running",
        "version": "0.1.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected"
        }

    except Exception as e:
        return {
            "database": "error",
            "details": str(e)
        }