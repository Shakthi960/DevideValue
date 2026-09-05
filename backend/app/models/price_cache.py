from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base


class PriceCache(Base):
    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True, index=True)

    cache_key = Column(String(300), unique=True, index=True, nullable=False)

    brand = Column(String(100), nullable=False)
    model = Column(String(150), nullable=False)
    storage = Column(String(50), nullable=True)

    exists = Column(String(10), nullable=True)

    matched_model = Column(String(150), nullable=True)

    valid_variants = Column(Text, nullable=True)

    new_price_inr = Column(Integer, nullable=True)
    used_resale_price_inr = Column(Integer, nullable=True)

    price_source = Column(String(50), nullable=True)

    confidence = Column(String(50), nullable=True)

    notes = Column(Text, nullable=True)

    fetched_at = Column(String(50), nullable=True)