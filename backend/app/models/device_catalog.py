from sqlalchemy import Column, Integer, String, Date
from app.core.database import Base


class DeviceCatalog(Base):
    __tablename__ = "device_catalog"

    id = Column(Integer, primary_key=True, index=True)

    brand = Column(
        String(100),
        nullable=False,
        index=True
    )

    model = Column(
        String(150),
        nullable=False,
        index=True
    )

    ram = Column(
        String(50),
        nullable=False
    )

    storage = Column(
        String(50),
        nullable=False
    )

    variant_name = Column(
        String(100),
        nullable=False
    )

    release_date = Column(
        Date,
        nullable=True
    )