# FILE: ./services/processor-service/app/main.py

import logging
import os
import json
import requests
import time
from dotenv import load_dotenv

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

QUEUE_NAME = "post_created_queue" # نام صف جدید
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

def get_post_details(post_id: int):
    """اطلاعات کامل یک پست را از management-api دریافت می‌کند."""
    # ... (کد مشابه publisher-service)
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/{post_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch details for post_id: {post_id}. Error: {e}")
        return None

def save_translation(post_id: int, translation_data: dict):
    """نتایج پردازش را در دیتابیس ذخیره می‌کند."""
    try:
        response = requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/translations", json=translation_data)
        response.raise_for_status()
        logger.info(f"Successfully saved translation for post_id: {post_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not save translation for post_id: {post_id}. Error: {e}")
        return None

def process_post(post_details: dict):
    """
    وظیفه اصلی پردازش: ترجمه، خلاصه‌سازی و امتیازدهی (در حال حاضر شبیه‌سازی شده).
    """
    post_id = post_details.get("id")
    title = post_details.get("title_original")
    content = post_details.get("content_original")
    
    # TODO: در اینجا به Gemini Flash 2 متصل شده و پرامپت‌ها را اجرا می‌کنیم.
    
    # شبیه‌سازی نتایج
    logger.info(f"Simulating AI processing for post_id: {post_id}")
    time.sleep(5) # شبیه‌سازی تاخیر پردازش
    
    # فرض می‌کنیم زبان مقصد فارسی است
    translation = {
        "language": "fa",
        "title_translated": f"[ترجمه شده] {title}",
        "content_translated": f"این محتوای ترجمه شده پست اصلی است: '{content}'",
        "content_telegram": f"خلاصه تلگرامی: {content[:150]}...",
        "featured_image_url": post_details.get("image_urls_original")[0] if post_details.get("image_urls_original") else None
    }
    
    save_translation(post_id, translation)
    
    # TODO: امتیازدهی و آپدیت امتیاز پست

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        
        if not post_id:
            logger.warning("Received a message without a post_id.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 Received post creation notification for post_id: {post_id}. Starting processing...")
        
        post_details = get_post_details(post_id)
        if not post_details:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        
        process_post(post_details)

        logger.info(f"✅ Successfully processed post_id: {post_id}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process message. Error: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    logger.info("--- 🧠 Processor Service Started ---")
    with RabbitMQClient() as client:
        client.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info(f"Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
        client.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()