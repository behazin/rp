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

# FILE: ./services/management-api/app/main.py

def init_db():
    """برای اتصال به دیتابیس با منطق تلاش مجدد تلاش می‌کند."""
    db_connected = False
    max_retries = 6
    for i in range(max_retries):
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
            management_models.Base.metadata.create_all(bind=engine)
            logger.info("✅ Database connection and table creation successful!")
            db_connected = True
            break
        except Exception as e:
            sleep_time = 10
            logger.warning(
                f"Database connection failed. Retrying in {sleep_time} seconds... (Attempt {i+1}/{max_retries})"
            )
            time.sleep(sleep_time)

    if not db_connected:
        logger.critical("❌ Could not connect to the database after several retries. Application will exit.")
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