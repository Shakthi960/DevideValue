from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.device_catalog import DeviceCatalog
from app.models.price_cache import PriceCache
from app.schemas.device_catalog import (
    DeviceCatalogCreate,
    DeviceCatalogCreateResponse,
)
from app.services.device_registry import register_device


router = APIRouter(
    prefix="/api/device-catalog",
    tags=["Device Catalog"]
)


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _paginate(
    items: list,
    page: int,
    page_size: int
) -> dict:
    total = len(items)

    total_pages = (
        (total + page_size - 1) // page_size
        if total > 0
        else 0
    )

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }


def _page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE
    ),
):
    return page, page_size


@router.post("/devices")
def add_device(
    payload: DeviceCatalogCreate,
    db: Session = Depends(get_db),
):
    try:
        result = register_device(
            db=db,
            brand=payload.brand,
            model=payload.model,
            storage=payload.storage,
            new_price_inr=payload.new_price_inr,
            release_date=payload.release_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return DeviceCatalogCreateResponse(**result)


@router.get("/devices/recent")
def get_recent_devices(
    db: Session = Depends(get_db),
    limit: int = Query(
        30,
        ge=1,
        le=200,
    ),
):
    """
    Admin view: recently added catalog devices.

    Rows added through ``POST /devices`` (or the "Add to catalog"
    flow) carry ``price_source == "custom"``, so we surface those
    newest-first for review.
    """
    rows = (
        db.query(PriceCache)
        .filter(
            PriceCache.price_source == "custom"
        )
        .order_by(
            PriceCache.fetched_at.desc()
        )
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": row.id,
                "brand": row.brand,
                "model": row.model,
                "storage": row.storage,
                "price_inr": (
                    row.new_price_inr
                    if row.new_price_inr is not None
                    else row.used_resale_price_inr
                ),
                "price_source": row.price_source,
                "notes": row.notes,
                "added_at": row.fetched_at,
            }
            for row in rows
        ]
    }


@router.get("/brands")
def get_brands(
    db: Session = Depends(get_db),
    paging=Depends(_page_params)
):
    page, page_size = paging

    rows = (
        db.query(DeviceCatalog.brand)
        .distinct()
        .order_by(DeviceCatalog.brand)
        .all()
    )

    names = [row[0] for row in rows]

    return _paginate(
        names,
        page,
        page_size
    )


@router.get("/brands/{brand}/models")
def get_models(
    brand: str,
    db: Session = Depends(get_db),
    paging=Depends(_page_params)
):
    page, page_size = paging

    rows = (
        db.query(DeviceCatalog.model)
        .filter(
            DeviceCatalog.brand == brand
        )
        .distinct()
        .order_by(DeviceCatalog.model)
        .all()
    )

    names = [row[0] for row in rows]

    return _paginate(
        names,
        page,
        page_size
    )


@router.get("/models/{brand}/{model}/variants")
def get_variants(
    brand: str,
    model: str,
    db: Session = Depends(get_db),
    paging=Depends(_page_params)
):
    page, page_size = paging

    query = (
        db.query(DeviceCatalog)
        .filter(
            DeviceCatalog.brand == brand,
            DeviceCatalog.model == model
        )
        .order_by(
            DeviceCatalog.ram,
            DeviceCatalog.storage
        )
    )

    total = query.count()

    rows = (
        query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (
        (total + page_size - 1) // page_size
        if total > 0
        else 0
    )

    return {
        "items": [
            {
                "id": row.id,
                "ram": row.ram,
                "storage": row.storage,
                "variant_name": row.variant_name,
                "release_date": (
                    row.release_date.isoformat()
                    if row.release_date
                    else None
                )
            }
            for row in rows
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }
