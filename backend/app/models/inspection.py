from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)

    inspection_code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    device_id = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False
    )

    inspection_type = Column(
        String(50),
        nullable=False,
        default="quick_value"
    )

    status = Column(
        String(50),
        nullable=False,
        default="created"
    )

    estimated_resale_price = Column(
        Float,
        nullable=True
    )

    estimated_exchange_price = Column(
        Float,
        nullable=True
    )

    device = relationship("Device")