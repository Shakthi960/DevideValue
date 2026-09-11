from datetime import date

from pydantic import BaseModel


class DeviceCatalogCreate(BaseModel):
    brand: str
    model: str
    storage: str
    new_price_inr: int | None = None
    release_date: date | None = None


class DeviceCatalogCreateResponse(BaseModel):
    brand: str
    model: str
    ram_gb: int | None
    storage_gb: int
    storage: str
    price_inr: int | None
    added_catalog: bool
    added_dataset: bool
    price_cached: bool