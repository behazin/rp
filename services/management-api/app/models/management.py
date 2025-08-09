from sqlalchemy import Column, Integer, String, JSON
from common.database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    url = Column(String(2048), unique=True, nullable=False)

class Destination(Base):
    __tablename__ = "destinations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    platform = Column(String(50), nullable=False) # e.g., "TELEGRAM", "WORDPRESS"
    credentials = Column(JSON, nullable=False)