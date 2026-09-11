from pydantic import BaseModel
from typing import Optional


class InspectionCreate(BaseModel):
    brand: str
    model: str
    storage: str | None = None
    inspection_type: str = "quick_value"


class InspectionResponse(BaseModel):
    inspection_code: str
    link_code: Optional[str] = None
    brand: str
    model: str
    storage: str | None
    inspection_type: str
    status: str
    estimated_resale_price: float | None
    estimated_exchange_price: float | None


class InspectionStatusResponse(BaseModel):
    inspection_code: str
    link_code: Optional[str] = None
    brand: str
    model: str
    storage: str | None
    status: str
    photos_captured: int = 0
    photos_total: int = 6
    photos_complete: bool = False
    diagnostics_complete: bool = False
    valuable: bool = False
    working: Optional[str] = None
    diagnostics_score: Optional[float] = None


class LinkInspectionRequest(BaseModel):
    link_code: str


class LinkInspectionResponse(BaseModel):
    inspection_code: str
    link_code: str
    brand: str
    model: str
    storage: str | None
    need: str


class DiagnosticsRequest(BaseModel):
    working: str
    diagnostics_score: float | None = None
    diagnostics_report: dict | None = None


class DiagnosticsResponse(BaseModel):
    inspection_code: str
    accepted: bool
    working: str
    diagnostics_score: float | None = None