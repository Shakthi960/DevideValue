from pydantic import BaseModel
from typing import List


class InspectionAnswerItem(BaseModel):
    question_key: str
    answer_value: str


class InspectionAnswersRequest(BaseModel):
    answers: List[InspectionAnswerItem]


class ValuationDevice(BaseModel):
    brand: str
    model: str
    storage: str | None = None
    storage_gb: int | None = None


class ValuationResponse(BaseModel):
    """Single-value response.

    The old response carried market_price, resale_price and
    exchange_price. The platform now produces ONE number,
    `device_value`, so only that is returned. `resale_price`
    and `exchange_price` are gone by design, not by omission.
    """

    inspection_code: str

    device_value: float
    currency: str = "INR"
    confidence: float

    condition_score: int
    diagnostic_score: float | None = None

    device: ValuationDevice

    valuation_type: str