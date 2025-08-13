# FILE: ./services/processor-service/app/main.py

import logging
import os
import json
import requests
import time
from dotenv import load_dotenv

# --- ایمپورت‌های جدید برای کتابخانه google-genai ---
from google import genai
from google.generative_ai.types import HarmCategory, HarmBlockThreshold

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# --- پیکربندی‌ها ---
QUEUE_NAME = "post_created_queue"
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- راه‌اندازی مدل هوش مصنوعی با genai ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    logger.info("✅ Gemini AI model configured successfully using 'google-genai'.")
except Exception as e:
    logger.critical(f"❌ Failed to configure Gemini AI model. Error: {e}")
    model = None

# --- پرامپت‌های مهندسی شده ---
TRANSLATE_PROMPT = """
Translate the following English tech news title and content to Persian.
Provide the response in a valid JSON format with two keys: "title_translated" and "content_translated".
Do not add any extra explanations or markdown formatting like ```json.

**Title:** "{title}"
**Content:** "{content}"
"""

TELEGRAM_SUMMARY_PROMPT = """
Based on the following translated tech news, generate a concise and engaging summary for a Telegram channel.
The summary must be in Persian and should not exceed 1000 characters.
Provide the response as a single string of plain text, without any special formatting.

**Title:** "{title}"
**Content:** "{content}"
"""

def get_post_details(post_id: int):
    """اطلاعات کامل یک پست را از management-api دریافت می‌کند."""
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

def process_post_with_ai(post_details: dict):
    """
    وظیفه اصلی پردازش با استفاده از Gemini AI.
    """
    post_id = post_details.get("id")
    title = post_details.get("title_original")
    content = post_details.get("content_original")

    if not model:
        logger.error("AI model is not available. Skipping processing.")
        return

    try:
        # ۱. ترجمه
        logger.info(f"Translating post_id: {post_id}")
        prompt = TRANSLATE_PROMPT.format(title=title, content=content)
        response = model.generate_content(
            prompt,
            safety_settings={ # برای جلوگیری از بلاک شدن به دلیل مسائل ایمنی
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        translation_result = json.loads(response.text)
        
        # ۲. خلاصه‌سازی برای تلگرام
        logger.info(f"Summarizing for Telegram, post_id: {post_id}")
        prompt = TELEGRAM_SUMMARY_PROMPT.format(
            title=translation_result.get("title_translated"), 
            content=translation_result.get("content_translated")
        )
        response = model.generate_content(
            prompt,
             safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        telegram_summary = response.text.strip()

        # ۳. آماده‌سازی داده‌ها برای ذخیره‌سازی
        final_data = {
            "language": "fa",
            "title_translated": translation_result.get("title_translated"),
            "content_translated": translation_result.get("content_translated"),
            "content_telegram": telegram_summary,
            "featured_image_url": post_details.get("image_urls_original")[0] if post_details.get("image_urls_original") else None
        }

        save_translation(post_id, final_data)

    except Exception as e:
        logger.error(f"An error occurred during AI processing for post_id: {post_id}. Error: {e}", exc_info=True)

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        
        if not post_id:
            logger.warning("Received a message without a post_id.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 Received post creation notification for post_id: {post_id}. Starting AI processing...")
        
        post_details = get_post_details(post_id)
        if not post_details:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        
        process_post_with_ai(post_details)

        logger.info(f"✅ Successfully processed post_id: {post_id}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process message. Error: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    logger.info("--- 🧠 Processor Service Started ---")
    if not GEMINI_API_KEY:
        logger.critical("❌ GEMINI_API_KEY is not set. The service cannot function.")
        return
        
    with RabbitMQClient() as client:
        client.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info(f"Waiting for messages in queue '{QUEUE_NAME}'. To exit press CTRL+C")
        client.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()