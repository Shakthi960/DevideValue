from sqlalchemy import Column, Integer, String, Date
from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    brand = Column(String(100), nullable=False)
    model = Column(String(150), nullable=False)
    storage = Column(String(50), nullable=True)

    purchase_date = Column(Date, nullable=True)

    imei = Column(String(50), nullable=True)

    created_at = Column(
        String(50),
        nullable=False
    )