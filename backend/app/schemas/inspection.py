from pydantic import BaseModel


class InspectionCreate(BaseModel):
    brand: str
    model: str
    storage: str | None = None
    inspection_type: str = "quick_value"


class InspectionResponse(BaseModel):
    inspection_code: str
    brand: str
    model: str
    storage: str | None
    inspection_type: str
    status: str
    estimated_resale_price: float | None
    estimated_exchange_price: float | None