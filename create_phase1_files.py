# FILE: create_phase1_files.py

import os
from pathlib import Path

# --- محتوای فایل‌ها ---

# محتوای فایل app/models/management.py
MODELS_CODE = """
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
"""

# محتوای فایل app/schemas/management.py
SCHEMAS_CODE = """
from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Dict, Any

# --- Source Schemas ---
class SourceBase(BaseModel):
    name: str
    url: HttpUrl

class SourceCreate(SourceBase):
    pass

class SourceInDB(SourceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Destination Schemas ---
class DestinationBase(BaseModel):
    name: str
    platform: str
    credentials: Dict[str, Any]

class DestinationCreate(DestinationBase):
    pass

class DestinationInDB(DestinationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
"""

# محتوای فایل app/api/endpoints/management.py
ENDPOINTS_CODE = """
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from common.database import get_db
from app.models import management as models
from app.schemas import management as schemas

router = APIRouter()

@router.post("/sources", response_model=schemas.SourceInDB, status_code=201)
def create_source(source: schemas.SourceCreate, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.url == str(source.url)).first()
    if db_source:
        raise HTTPException(status_code=400, detail="Source URL already registered")
    
    new_source = models.Source(name=source.name, url=str(source.url))
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source

@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    db_source = db.query(models.Source).filter(models.Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(db_source)
    db.commit()
    return

@router.post("/destinations", response_model=schemas.DestinationInDB, status_code=201)
def create_destination(dest: schemas.DestinationCreate, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.name == dest.name).first()
    if db_dest:
        raise HTTPException(status_code=400, detail="Destination name already exists")
        
    new_dest = models.Destination(**dest.model_dump()) # Use .model_dump() for Pydantic v2
    db.add(new_dest)
    db.commit()
    db.refresh(new_dest)
    return new_dest

@router.delete("/destinations/{destination_id}", status_code=204)
def delete_destination(destination_id: int, db: Session = Depends(get_db)):
    db_dest = db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    if not db_dest:
        raise HTTPException(status_code=404, detail="Destination not found")
        
    db.delete(db_dest)
    db.commit()
    return
"""

# محتوای فایل app/api/router.py
ROUTER_CODE = """
from fastapi import APIRouter
from app.api.endpoints import management

api_router = APIRouter()
api_router.include_router(management.router, tags=["Management"])
"""

# محتوای فایل app/main.py
MAIN_APP_CODE = """
import logging
import time
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text # Import text

from common.logging_config import setup_logging
from common.database import get_db, engine
from common.rabbit import RabbitMQClient

# مدل‌ها را import می‌کنیم تا SQLAlchemy آنها را بشناسد
from app.models import management as management_models
from app.api.router import api_router

# --- پیکربندی اولیه ---
setup_logging()
logger = logging.getLogger(__name__)

def init_db():
    \"\"\"برای اتصال به دیتابیس با منطق تلاش مجدد تلاش می‌کند.\"\"\"
    db_connected = False
    max_retries = 10
    for i in range(max_retries):
        try:
            with engine.connect() as connection:
                pass
            management_models.Base.metadata.create_all(bind=engine)
            logger.info("Database connection and table creation successful!")
            db_connected = True
            break
        except SQLAlchemyError as e:
            sleep_time = 2 ** i
            logger.warning(
                f"Database connection failed. Retrying in {sleep_time} seconds... (Attempt {i+1}/{max_retries})"
            )
            time.sleep(sleep_time)
    if not db_connected:
        logger.critical("Could not connect to the database after several retries. Application will exit.")
        exit(1)

# --- اجرای برنامه ---
init_db()

app = FastAPI(title="RoboPost - Management API")

@app.on_event("startup")
def startup_event():
    logger.info("Management API is starting up...")
    try:
        with RabbitMQClient() as client:
            logger.info("RabbitMQ connection test successful on startup.")
    except Exception as e:
        logger.error(f"Could not connect to RabbitMQ on startup: {e}")

app.include_router(api_router)

@app.get("/healthz", tags=["Monitoring"])
def health_check(db: Session = Depends(get_db)):
    db_status = "OK"
    rabbit_status = "OK"
    try:
        db.execute(text('SELECT 1')) # Use text() for literal SQL
    except Exception:
        db_status = "Error"
    try:
        with RabbitMQClient():
            pass
    except Exception:
        rabbit_status = "Error"
    
    return {"status": "OK", "database": db_status, "rabbitmq": rabbit_status}
"""


# --- ساختار فایل‌ها ---

# این دیکشنری ساختار فایل و پوشه و محتوای هر فایل را تعریف می‌کند
PHASE_1_STRUCTURE = {
    "services/management-api/app": {
        "models": {
            "management.py": MODELS_CODE
        },
        "schemas": {
            "management.py": SCHEMAS_CODE
        },
        "api": {
            "endpoints": {
                "management.py": ENDPOINTS_CODE
            },
            "router.py": ROUTER_CODE
        },
        "main.py": MAIN_APP_CODE
    }
}

def create_structure(base_path: Path, structure: dict):
    """
    به صورت بازگشتی ساختار فایل و پوشه را بر اساس دیکشنری ورودی ایجاد می‌کند.
    """
    for name, content in structure.items():
        current_path = base_path / name
        if isinstance(content, dict):
            # اگر محتوا یک دیکشنری دیگر باشد، یک پوشه است
            current_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 پوشه ایجاد/تأیید شد: {current_path}/")
            create_structure(current_path, content)
        else:
            # در غیر این صورت، یک فایل است
            # اطمینان حاصل می‌کنیم که پوشه والد وجود دارد
            current_path.parent.mkdir(parents=True, exist_ok=True)
            # محتوای کد را در فایل می‌نویسیم
            # .strip() برای حذف فضاهای خالی احتمالی در ابتدا و انتهای رشته کد است
            current_path.write_text(content.strip(), encoding='utf-8')
            print(f"📄 فایل نوشته شد: {current_path}")


def main():
    """
    تابع اصلی برای اجرای اسکریپت
    """
    print("🚀 شروع ساخت فایل‌های فاز ۱...")
    print("-" * 50)
    
    root_path = Path(".") # مسیر ریشه پروژه (جایی که اسکریپت اجرا می‌شود)
    create_structure(root_path, PHASE_1_STRUCTURE)
    
    print("-" * 50)
    print("✅ تمام فایل‌های فاز ۱ با موفقیت ایجاد و به‌روزرسانی شدند!")
    print("ℹ️ اکنون می‌توانید 'docker-compose up --build' را اجرا کنید.")

if __name__ == "__main__":
    main()