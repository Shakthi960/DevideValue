from sqlalchemy import Column, Integer, String, Float, ForeignKey

from app.core.database import Base


class InspectionAnswer(Base):
    __tablename__ = "inspection_answers"

    id = Column(Integer, primary_key=True, index=True)

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    question_key = Column(
        String(100),
        nullable=False
    )

    answer_value = Column(
        String(200),
        nullable=False
    )

    score = Column(
        Float,
        nullable=True
    )