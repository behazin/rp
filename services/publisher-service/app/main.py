# FILE: ./services/publisher-service/app/main.py

import logging
import os
import json
import requests
import telegram
from dotenv import load_dotenv

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

QUEUE_NAME = "post_approval_queue"
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

def get_post_details(post_id: int):
    """اطلاعات کامل یک پست را از management-api دریافت می‌کند."""
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/{post_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch details for post_id: {post_id}. Error: {e}")
        return None

def publish_to_telegram(destination: dict, post_translation: dict):
    """یک پست را به یک مقصد تلگرامی مشخص ارسال می‌کند."""
    bot_token = destination.get("credentials", {}).get("bot_token")
    chat_id = destination.get("credentials", {}).get("chat_id")
    
    if not bot_token or not chat_id:
        logger.error(f"Missing bot_token or chat_id for destination: {destination.get('name')}")
        return False
        
    try:
        bot = telegram.Bot(token=bot_token)
        
        # ترکیب عنوان، محتوای خلاصه شده و لینک اصلی
        message = (
            f"*{post_translation.get('title_translated')}*\n\n"
            f"{post_translation.get('content_telegram')}\n\n"
            f"[Read More]({post_translation.get('url_original')})"
        )

        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=telegram.ParseMode.MARKDOWN,
            disable_web_page_preview=False
        )
        logger.info(f"Successfully published to Telegram destination: {destination.get('name')}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to Telegram destination: {destination.get('name')}. Error: {e}")
        return False

def callback(ch, method, properties, body):
    """این تابع به محض دریافت پیام از RabbitMQ اجرا می‌شود."""
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        
        if not post_id:
            logger.warning("Received a message without a post_id.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 Received post approval for post_id: {post_id}. Starting publishing process...")
        
        post_details = get_post_details(post_id)
        if not post_details:
            # اگر نتوانستیم اطلاعات پست را بگیریم، پیام را رها می‌کنیم تا بعداً دوباره تلاش شود
            ch.basic_nack(delivery_tag=method.delivery_tag)
            return

        source = post_details.get("source", {})
        destinations = source.get("destinations", [])
        
        # فقط مقصدهایی که پلتفرمشان تلگرام است را فیلتر می‌کنیم
        telegram_destinations = [d for d in destinations if d.get("platform") == "TELEGRAM"]
        
        # فرض می‌کنیم اولین ترجمه موجود، ترجمه مورد نظر ماست
        # در آینده می‌توان منطق انتخاب زبان را پیچیده‌تر کرد
        if post_details.get("translations"):
            translation_data = post_details["translations"][0]
            translation_data['url_original'] = post_details.get('url_original') # افزودن URL اصلی

            for dest in telegram_destinations:
                publish_to_telegram(dest, translation_data)
        else:
            logger.warning(f"No translations found for post_id: {post_id}. Cannot publish.")

        # TODO: وضعیت پست را در دیتابیس به 'published' تغییر بده
        
        logger.info(f"✅ Successfully processed post_id: {post_id}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process message. Error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag)


def main():
    logger.info("--- 📮 Publisher Service Started ---")
    with RabbitMQClient() as client:
        client.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info(f"Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
        client.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()