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
    storage: str


class ValuationResponse(BaseModel):
    inspection_code: str

    market_price: float

    resale_price: float

    exchange_price: float

    new_price_inr: float | None = None

    price_source: str | None = None

    condition_score: int

    condition_grade: str

    device: ValuationDevice

    model_source: str

    valuation_type: str