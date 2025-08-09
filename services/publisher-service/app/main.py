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
    """
    این تابع به محض دریافت پیام از RabbitMQ اجرا می‌شود.
    """
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