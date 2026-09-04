from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.device_catalog import DeviceCatalog


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
