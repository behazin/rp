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

def get_source_with_destinations(source_id: int):
    """اطلاعات کامل یک منبع را به همراه مقصدهای متصل به آن دریافت می‌کند."""
    try:
        # ما لیست تمام منابع را می‌گیریم و منبع مورد نظر را فیلتر می‌کنیم
        response = requests.get(f"{MANAGEMENT_API_URL}/sources")
        response.raise_for_status()
        all_sources = response.json()
        for source in all_sources:
            if source.get("id") == source_id:
                return source
        logger.warning(f"Source with id {source_id} not found.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch sources. Error: {e}")
        return None


def publish_to_telegram(destination: dict, post_translation: dict, post_url: str):
    """یک پست را به یک مقصد تلگرامی مشخص ارسال می‌کند."""
    bot_token = destination.get("credentials", {}).get("bot_token")
    chat_id = destination.get("credentials", {}).get("chat_id")

    if not bot_token or not chat_id:
        logger.error(f"Missing bot_token or chat_id for destination: {destination.get('name')}")
        return False

    try:
        bot = telegram.Bot(token=bot_token)

        message = (
            f"*{post_translation.get('title_translated')}*\n\n"
            f"{post_translation.get('content_telegram')}\n\n"
            f"[Read More]({post_url})"
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
            ch.basic_nack(delivery_tag=method.delivery_tag)
            return

        source_id = post_details.get("source_id")
        source_with_destinations = get_source_with_destinations(source_id)

        if not source_with_destinations:
            logger.warning(f"Could not find source details for source_id: {source_id}. Skipping post.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        destinations = source_with_destinations.get("destinations", [])
        telegram_destinations = [d for d in destinations if d.get("platform") == "TELEGRAM"]

        if not telegram_destinations:
            logger.warning(f"No TELEGRAM destinations found for source_id: {source_id}. Post will not be published.")

        if post_details.get("translations"):
            translation_data = post_details["translations"][0]
            post_url = post_details.get('url_original')

            for dest in telegram_destinations:
                publish_to_telegram(dest, translation_data, post_url)
        else:
            logger.warning(f"No translations found for post_id: {post_id}. Cannot publish.")

        logger.info(f"✅ Successfully processed post_id: {post_id}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag)


def main():
    logger.info("--- 📮 Publisher Service Started ---")
    with RabbitMQClient() as client:
        client.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info(f"Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
        client.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()