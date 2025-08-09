# FILE: ./services/management-api/app/main.py
import logging
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# مهم: این ایمپورت‌ها به لطف volume mount در docker-compose.override.yml کار می‌کنند
from common.logging_config import setup_logging
from common.database import get_db, engine, Base
from common.rabbit import RabbitMQClient

# --- پیکربندی اولیه ---
setup_logging()  # تنظیم لاگر در ابتدای برنامه
logger = logging.getLogger(__name__)

# ایجاد جداول در دیتابیس (اگر وجود نداشته باشند)
# در یک سناریوی واقعی از ابزارهایی مثل Alembic استفاده می‌شود
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="RoboPost - Management API")


@app.on_event("startup")
def startup_event():
    logger.info("Management API is starting up...")
    # تست اتصال به RabbitMQ
    try:
        with RabbitMQClient() as client:
            logger.info("RabbitMQ connection test successful on startup.")
    except Exception as e:
        logger.error(f"Could not connect to RabbitMQ on startup: {e}")
    # تست اتصال به دیتابیس
    try:
        # The get_db dependency will handle the connection test on first request
        logger.info("Database connection will be tested on the first request.")
    except Exception as e:
        logger.error(f"Could not connect to Database on startup: {e}")


@app.get("/healthz", tags=["Monitoring"])
def health_check(db: Session = Depends(get_db)):
    """بررسی وضعیت سلامت سرویس، دیتابیس و RabbitMQ"""
    db_status = "OK"
    rabbit_status = "OK"
    try:
        # یک کوئری ساده برای تست اتصال به دیتابیس
        db.execute('SELECT 1')
    except Exception:
        db_status = "Error"

    try:
        with RabbitMQClient():
            pass # فقط اتصال را تست می‌کنیم
    except Exception:
        rabbit_status = "Error"
    
    logger.info(f"Health check performed: DB={db_status}, RabbitMQ={rabbit_status}")
    return {"status": "OK", "database": db_status, "rabbitmq": rabbit_status}