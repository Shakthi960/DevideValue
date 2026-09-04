from pydantic import BaseModel
from typing import List


class InspectionAnswerItem(BaseModel):
    question_key: str
    answer_value: str


class InspectionAnswersRequest(BaseModel):
    answers: List[InspectionAnswerItem]


class ValuationResponse(BaseModel):
    inspection_code: str

    market_price: float

    resale_price: float

    exchange_price: float

    condition_score: int

    condition_grade: str

    model_source: str

    valuation_type: str