# FILE: ./services/fetcher-service/app/main.py
import schedule
import time
import logging
import os
from dotenv import load_dotenv

# از لاگر مشترک استفاده می‌کنیم
from common.logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

def fetch_job():
    """
    وظیفه اصلی که به صورت زمان‌بندی شده اجرا می‌شود.
    """
    logger.info("🚀 Fetcher job started. Looking for new posts...")
    
    # TODO: 
    # 1. به management-api/sources وصل شو و لیست منابع را بگیر.
    # 2. هر منبع را برای محتوای جدید بررسی کن (مثلاً با استفاده از کتابخانه feedparser).
    # 3. برای هر خبر جدید، یک رکورد در جدول Posts با status='pending_approval' ایجاد کن.
    
    logger.info("✅ Fetcher job finished.")


def main():
    logger.info("--- 🤖 Fetcher Service Started ---")
    
    # وظیفه را طوری تنظیم می‌کنیم که هر ساعت اجرا شود
    schedule.every(1).hour.do(fetch_job)
    
    # اجرای اولین بار بلافاصله پس از راه‌اندازی
    fetch_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()