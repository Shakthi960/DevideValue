from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.core.database import Base


class InspectionPhoto(Base):
    __tablename__ = "inspection_photos"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    inspection_id = Column(
        Integer,
        ForeignKey(
            "inspections.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    photo_type = Column(
        String(30),
        nullable=False
    )

    storage_path = Column(
        String(500),
        nullable=False
    )

    content_type = Column(
        String(100),
        nullable=False
    )

    created_at = Column(
        String(50),
        nullable=False
    )