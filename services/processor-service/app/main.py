# FILE: ./services/processor-service/app/main.py
# (نسخه بازنویسی شده برای پشتیبانی از پردازش دو مرحله‌ای)

import logging
import os
import json
import requests
from typing import Optional, List
import threading

from dotenv import load_dotenv

# Google Gen AI SDK
from google import genai
from google.genai import types
from pydantic import BaseModel

# Project-shared utilities
from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

# ---------------------------
# Environment & Config
# ---------------------------
load_dotenv()

# --- نام صف‌های جدید ---
POST_CREATED_QUEUE = os.getenv("POST_CREATED_QUEUE", "post_created_queue")
CONTENT_PROCESSING_QUEUE = os.getenv("CONTENT_PROCESSING_QUEUE", "content_processing_queue")
REVIEW_NOTIFICATIONS_QUEUE = "review_notifications_queue" 
FINAL_APPROVAL_NOTIFICATIONS_QUEUE = "final_approval_notifications_queue"
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

setup_logging()
logger = logging.getLogger("processor-service-v2")

# ---------------------------
# Structured Output Schemas
# ---------------------------
# خروجی مرحله اول: پیش‌پردازش
class PreProcessOutput(BaseModel):
    title_translated: str
    quality_score: float  # 0..10

# خروجی مرحله دوم: پردازش محتوا
class ContentProcessOutput(BaseModel):
    content_translated: Optional[str] = None
    content_telegram: Optional[str] = None
    content_instagram: Optional[str] = None
    content_twitter: Optional[str] = None

# ---------------------------
# Gemini Client
# ---------------------------
try:
    client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else genai.Client()
    logger.info("✅ Gemini client initialized (google-genai)")
except Exception as e:
    client = None
    logger.critical(f"❌ Failed to initialize Gemini client: {e}", exc_info=True)

# ---------------------------
# HTTP Helpers
# ---------------------------
def get_post_details(post_id: int):
    # ... (بدون تغییر) ...
    try:
        resp = requests.get(f"{MANAGEMENT_API_URL}/posts/{post_id}")
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch details for post_id={post_id}: {e}")
        return None

def save_preprocessing_result(post_id: int, result: PreProcessOutput, featured_image_url: Optional[str]):
    """نتایج پیش‌پردازش را ذخیره و یک پیام برای اطلاع‌رسانی به مدیر ارسال می‌کند."""
    payload = {
        "language": "fa",
        "title_translated": result.title_translated,
        "score": result.quality_score,
        "featured_image_url": featured_image_url
    }
    try:
        # ۱. ذخیره نتیجه در دیتابیس
        requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/translations", json=payload).raise_for_status()
        logger.info(f"✅ Saved preprocessing result for post_id={post_id}")
        
        # ۲. تغییر وضعیت پست
        requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/preprocessed").raise_for_status()
        logger.info(f"✅ Post status set to PREPROCESSED for post_id={post_id}")

        # ۳. اطلاع‌رسانی به مدیر تلگرام از طریق RabbitMQ
        with RabbitMQClient() as rmq:
            message_body = json.dumps({"post_id": post_id})
            rmq.channel.queue_declare(queue=REVIEW_NOTIFICATIONS_QUEUE, durable=True)
            rmq.publish(exchange_name="", routing_key=REVIEW_NOTIFICATIONS_QUEUE, body=message_body)
            logger.info(f"📤 Sent review notification for post_id={post_id}")
            
        return True
    except Exception as e:
        logger.error(f"Could not save preprocessing result or notify for post_id={post_id}: {e}")
        return False

def update_translation_with_content(translation_id: int, post_id: int, result: ContentProcessOutput):
    """ترجمه را با محتوای جدید آپدیت کرده و پیامی برای تایید نهایی مدیر ارسال می‌کند."""
    
    # --- START: این بخش اصلاح شده است ---
    payload = result.model_dump(exclude_unset=True)
    payload['language'] = 'fa' # فیلد اجباری زبان را اضافه می‌کنیم
    # --- END: پایان بخش اصلاح شده ---

    try:
        # ۱. آپدیت ترجمه در دیتابیس
        requests.patch(f"{MANAGEMENT_API_URL}/translations/{translation_id}", json=payload).raise_for_status()
        logger.info(f"✅ Updated translation with content for translation_id={translation_id}")
        
        # ۲. تغییر وضعیت پست
        requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/ready-for-final-approval").raise_for_status()
        logger.info(f"✅ Post status set to READY_FOR_FINAL_APPROVAL for post_id={post_id}")
        
        # ۳. اطلاع‌رسانی به مدیر تلگرام برای تایید نهایی
        with RabbitMQClient() as rmq:
            message_body = json.dumps({"post_id": post_id})
            rmq.channel.queue_declare(queue=FINAL_APPROVAL_NOTIFICATIONS_QUEUE, durable=True)
            rmq.publish(exchange_name="", routing_key=FINAL_APPROVAL_NOTIFICATIONS_QUEUE, body=message_body)
            logger.info(f"📤 Sent final approval notification for post_id={post_id}")
            
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not update translation or notify for post_id={post_id}: {e}")
        return False

# ---------------------------
# Core AI Processing
# ---------------------------
def _safety_settings():
    # ... (بدون تغییر) ...
    pass

def preprocess_title_and_score(title: str, model: str = "gemini-2.5-flash") -> PreProcessOutput:
    """مرحله ۱: فقط عنوان را ترجمه و به آن امتیاز می‌دهد."""
    if not client:
        raise RuntimeError("Gemini client not initialized")

    sys_instruction = (
        "You are a professional Persian translator and editor. "
        "Return ONLY JSON with fields: title_translated (string), quality_score (number). "
        "Requirements: "
        "1) Translate the title to fluent, engaging Persian. "
        "2) quality_score in [0,10] reflecting translation fidelity and clarity; use a dot for decimals."
    )
    prompt = f'**Title:** "{title or ""}"'

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=sys_instruction,
            response_mime_type="application/json",
            response_schema=PreProcessOutput,
            temperature=0.2,
            safety_settings=_safety_settings(),
        ),
    )
    return resp.parsed

def process_content_for_platforms(content: str, platforms: List[str], model: str = "gemini-2.5-flash") -> ContentProcessOutput:
    """مرحله ۲: محتوای اصلی را بر اساس پلتفرم‌های درخواستی و با بهینه‌سازی دقیق هزینه پردازش می‌کند."""
    if not client:
        raise RuntimeError("Gemini client not initialized")

    # --- START: منطق نهایی و اصلاح شده برای ساخت پرامپت ---
    
    # اگر بیش از یک پلتفرم در لیست باشد، به معنی "تایید کل" است
    is_approve_all = len(platforms) > 1

    platform_requirements = []
    
    if is_approve_all:
        # حالت کامل: ابتدا ترجمه کامل، سپس خلاصه‌سازی برای همه
        platform_requirements.append("1. First, translate the entire original **Content** into fluent Persian. The result MUST be in the 'content_translated' field.")
        platform_requirements.append("2. From the translated content, generate 'content_telegram': A concise Persian summary, under 1000 characters.")
        platform_requirements.append("3. From the translated content, generate 'content_instagram': An engaging Persian summary for Instagram, under 2200 characters, with relevant hashtags.")
        platform_requirements.append("4. From the translated content, generate 'content_twitter': A very short Persian summary for Twitter/X, under 280 characters.")
    else:
        # حالت بهینه: فقط خلاصه مستقیم برای پلتفرم مشخص شده
        target_platform = platforms[0] # چون در این حالت فقط یک پلتفرم داریم
        if target_platform == "telegram":
            platform_requirements.append("- Directly translate and summarize the original English **Content** into a concise Persian summary for Telegram. The result MUST be in the 'content_telegram' field and be under 1000 characters. Do NOT provide a full 'content_translated'.")
        elif target_platform == "instagram":
            platform_requirements.append("- Directly translate and summarize the original English **Content** into an engaging Persian summary for Instagram. The result MUST be in the 'content_instagram' field, be under 2200 characters, and include relevant hashtags. Do NOT provide a full 'content_translated'.")
        elif target_platform == "twitter":
            platform_requirements.append("- Directly translate and summarize the original English **Content** into a very short Persian summary for Twitter/X. The result MUST be in the 'content_twitter' field and be under 280 characters. Do NOT provide a full 'content_translated'.")

    sys_instruction = (
        "You are a professional Persian translator and multi-platform copywriter.\n"
        "Return ONLY a JSON object with the requested fields.\n"
        "Instructions:\n" + "\n".join(platform_requirements)
    )
    # --- END: پایان منطق نهایی ---

    prompt = f'**Content:**\n"{content or ""}"'

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=sys_instruction,
            response_mime_type="application/json",
            response_schema=ContentProcessOutput,
            temperature=0.3,
        ),
    )
    return resp.parsed

# ---------------------------
# RabbitMQ Callbacks
# ---------------------------
def on_post_created_callback(ch, method, properties, body):
    """Callback برای صف post_created_queue (مرحله ۱: پیش‌پردازش)"""
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        if not post_id:
            logger.warning("Received message without post_id; acking.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 [PREPROCESS] Received post_created for post_id={post_id}")
        post_details = get_post_details(post_id)
        if not post_details:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

        title = post_details.get("title_original")
        result = preprocess_title_and_score(title)
        
        # استخراج اولین تصویر به عنوان تصویر شاخص
        featured_image_url = (post_details.get("images")[0].get("url") 
                              if post_details.get("images") else None)

        save_preprocessing_result(post_id, result, featured_image_url)
        logger.info(f"✅ [PREPROCESS] Finished for post_id={post_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to preprocess message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

# FILE: ./services/processor-service/app/main.py

def on_content_processing_callback(ch, method, properties, body):
    """Callback برای صف content_processing_queue (مرحله ۲: پردازش محتوا)"""
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        platforms = message.get("platforms", [])
        if not post_id or not platforms:
            logger.warning("Received invalid content processing request; acking.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        logger.info(f"📬 [PROCESS CONTENT] Received request for post_id={post_id}, platforms={platforms}")
        post_details = get_post_details(post_id)
        if not post_details or not post_details.get("translations"):
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

        content = post_details.get("content_original")
        result = process_content_for_platforms(content, platforms)
        
        translation_id = post_details["translations"][0]["id"]
        
        # --- START: این خط اصلاح شده است ---
        # ما post_id را به عنوان ورودی سوم به تابع پاس می‌دهیم
        if update_translation_with_content(translation_id, post_id, result):
        # --- END: پایان بخش اصلاح شده ---
            logger.info(f"✅ [PROCESS CONTENT] Finished for post_id={post_id}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        logger.error(f"Failed to process content message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

# ---------------------------
# Main Function
# ---------------------------
def main():
    logger.info("--- 🧠 Processor Service V2 Started ---")
    if not client:
        logger.critical("❌ Gemini client is not available; exiting.")
        return

    # ایجاد و اجرای هر listener در یک thread جداگانه
    def listen(queue_name, callback_func):
        with RabbitMQClient() as rmq:
            rmq.channel.queue_declare(queue=queue_name, durable=True)
            logger.info(f"Waiting for messages in '{queue_name}'...")
            rmq.start_consuming(queue_name=queue_name, callback=callback_func)

    preprocess_thread = threading.Thread(target=listen, args=(POST_CREATED_QUEUE, on_post_created_callback))
    content_process_thread = threading.Thread(target=listen, args=(CONTENT_PROCESSING_QUEUE, on_content_processing_callback))

    preprocess_thread.start()
    content_process_thread.start()

    preprocess_thread.join()
    content_process_thread.join()

if __name__ == "__main__":
    main()