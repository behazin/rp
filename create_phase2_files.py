# FILE: ./create_phase2_files.py

from pathlib import Path

# --- محتوای فایل‌های fetcher-service ---

FETCHER_REQUIREMENTS = """
# FILE: ./services/fetcher-service/requirements.txt
requests
python-dotenv
python-json-logger
schedule
"""

FETCHER_DOCKERFILE = """
# FILE: ./services/fetcher-service/Dockerfile
FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /usr/src/app/app

# فایل‌های مشترک را نیز کپی می‌کنیم
COPY ../../common /usr/src/app/common

CMD ["python", "app/main.py"]
"""

FETCHER_MAIN_PY = """
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
    \"\"\"
    وظیفه اصلی که به صورت زمان‌بندی شده اجرا می‌شود.
    \"\"\"
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
"""

# --- محتوای فایل‌های publisher-service ---

PUBLISHER_REQUIREMENTS = """
# FILE: ./services/publisher-service/requirements.txt
pika
python-dotenv
python-json-logger
requests
# در آینده کتابخانه‌های تلگرام، اینستاگرام و... به اینجا اضافه می‌شوند
"""

PUBLISHER_DOCKERFILE = """
# FILE: ./services/publisher-service/Dockerfile
FROM python:3.9-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /usr/src/app/app

# فایل‌های مشترک را نیز کپی می‌کنیم
COPY ../../common /usr/src/app/common

CMD ["python", "app/main.py"]
"""

PUBLISHER_MAIN_PY = """
# FILE: ./services/publisher-service/app/main.py
import logging
import os
import json
from dotenv import load_dotenv

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

QUEUE_NAME = "post_approval_queue" # نام صفی که به آن گوش می‌دهیم

def callback(ch, method, properties, body):
    \"\"\"
    این تابع به محض دریافت پیام از RabbitMQ اجرا می‌شود.
    \"\"\"
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        
        if not post_id:
            logger.warning("Received a message without a post_id.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 Received post approval for post_id: {post_id}. Starting publishing process...")
        
        # TODO:
        # 1. با استفاده از post_id، اطلاعات کامل پست و ترجمه‌هایش را از management-api بگیر.
        # 2. لیست مقصدهای (destinations) مرتبط با منبع این پست را بگیر.
        # 3. برای هر مقصد، بر اساس پلتفرم آن (e.g., TELEGRAM):
        #    a. محتوای مناسب را از آبجکت ترجمه بردار.
        #    b. با استفاده از credentials مقصد، به پلتفرم مربوطه متصل شو.
        #    c. پست را منتشر کن.
        # 4. وضعیت پست را در دیتابیس به 'published' تغییر بده.

        logger.info(f"✅ Successfully processed post_id: {post_id}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process message. Error: {e}")
        # پیام را acknowledge نمی‌کنیم تا بعداً دوباره تلاش شود
        ch.basic_nack(delivery_tag=method.delivery_tag)


def main():
    logger.info("--- 📮 Publisher Service Started ---")
    with RabbitMQClient() as client:
        # صف را تعریف می‌کنیم (اگر وجود نداشته باشد)
        client.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        
        logger.info(f"Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
        client.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()
"""

# --- ساختار فایل‌ها ---

PHASE_2_STRUCTURE = {
    "services": {
        "fetcher-service": {
            "app": {
                "main.py": FETCHER_MAIN_PY
            },
            "Dockerfile": FETCHER_DOCKERFILE,
            "requirements.txt": FETCHER_REQUIREMENTS
        },
        "publisher-service": {
            "app": {
                "main.py": PUBLISHER_MAIN_PY
            },
            "Dockerfile": PUBLISHER_DOCKERFILE,
            "requirements.txt": PUBLISHER_REQUIREMENTS
        }
    }
}

def create_structure(base_path: Path, structure: dict):
    """
    به صورت بازگشتی ساختار فایل و پوشه را بر اساس دیکشنری ورودی ایجاد می‌کند.
    """
    for name, content in structure.items():
        current_path = base_path / name
        if isinstance(content, dict):
            current_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 پوشه ایجاد/تأیید شد: {current_path}/")
            create_structure(current_path, content)
        else:
            current_path.parent.mkdir(parents=True, exist_ok=True)
            current_path.write_text(content.strip(), encoding='utf-8')
            print(f"📄 فایل نوشته شد: {current_path}")

def main():
    """
    تابع اصلی برای اجرای اسکریپت
    """
    print("🚀 شروع ساخت فایل‌های فاز ۲...")
    print("-" * 50)
    
    root_path = Path(".") # مسیر ریشه پروژه
    create_structure(root_path, PHASE_2_STRUCTURE)
    
    print("-" * 50)
    print("✅ تمام فایل‌های فاز ۲ با موفقیت ایجاد شدند!")
    print("ℹ️ اکنون می‌توانید فایل `docker-compose.yml` را به‌روزرسانی کرده و `docker-compose up --build` را اجرا کنید.")

if __name__ == "__main__":
    main()