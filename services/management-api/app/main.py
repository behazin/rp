import logging
import time
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from common.logging_config import setup_logging
from common.database import get_db, engine
from common.rabbit import RabbitMQClient

from app.models import management as management_models
from app.api.router import api_router

setup_logging()
logger = logging.getLogger(__name__)


def init_db():
    """برای اتصال به دیتابیس با منطق تلاش مجدد و لاگ دقیق خطا تلاش می‌کند."""
    db_connected = False
    max_retries = 10
    for i in range(max_retries):
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
            
            management_models.Base.metadata.create_all(bind=engine)
            logger.info("✅ اتصال به پایگاه داده با موفقیت برقرار و جداول ایجاد شدند!")
            db_connected = True
            break
        except Exception as e:
            # --- START: بخش کلیدی اصلاح شده ---
            # نمایش دقیق خطا در لاگ
            sleep_time = 2 ** i
            logger.warning(
                f"اتصال به پایگاه داده ناموفق بود. خطا: [{e}]. تلاش مجدد تا {sleep_time} ثانیه دیگر... (تلاش {i + 1}/{max_retries})"
            )
            time.sleep(sleep_time)
            # --- END: بخش کلیدی اصلاح شده ---

    if not db_connected:
        logger.critical("❌ پس از چندین تلاش، اتصال به پایگاه داده برقرار نشد. برنامه خاتمه می‌یابد.")
        exit(1)


# --- اجرای برنامه ---
init_db()

app = FastAPI(title="RoboPost - Management API")

@app.on_event("startup")
def startup_event():
    logger.info("Management API در حال راه‌اندازی است...")
    try:
        with RabbitMQClient() as client:
            logger.info("تست اتصال به RabbitMQ در هنگام راه‌اندازی موفقیت‌آمیز بود.")
    except Exception as e:
        logger.error(f"اتصال به RabbitMQ در هنگام راه‌اندازی با خطا مواجه شد: {e}")

app.include_router(api_router)

@app.get("/healthz", tags=["Monitoring"])
def health_check(db: Session = Depends(get_db)):
    db_status = "OK"
    rabbit_status = "OK"
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        db_status = "Error"
    try:
        with RabbitMQClient():
            pass
    except Exception:
        rabbit_status = "Error"
    
    return {"status": "OK", "database": db_status, "rabbitmq": rabbit_status}