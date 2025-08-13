# FILE: ./services/processor-service/app/main.py
# Updated for latest Google Gen AI SDK (google-genai): structured JSON output + client.models.generate_content

import logging
import os
import json
import requests
from typing import Optional

from dotenv import load_dotenv

# Google Gen AI SDK (latest)
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

QUEUE_NAME = os.getenv("QUEUE_NAME", "post_created_queue")
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

# The SDK auto-detects GEMINI_API_KEY or GOOGLE_API_KEY from env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# ---- Logging: FIXED (no arg to setup_logging) ----
setup_logging()
logger = logging.getLogger("processor-service")

# ---------------------------
# Structured Output Schemas
# ---------------------------
class Translation(BaseModel):
    title_translated: str
    content_translated: str

class TelegramSummary(BaseModel):
    summary: str

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
# Prompts (JSON shape enforced by response_schema)
# ---------------------------
TRANSLATE_PROMPT = (
"You are a professional editor and translator tasked with translating English tech news into Persian.\n"
    "Your instructions are:\n"
    "1. First, analyze the **Content** field. You MUST 'clean' it by completely removing any text that is not part of the main article, such as advertisements, event promotions, or author bios.\n"
    "2. Second, translate the original **Title** and the now-cleaned **Content** into fluent Persian.\n"
    "3. **CRUCIAL:** You MUST preserve the original paragraph structure from the cleaned content. The translated text must have the exact same line breaks and paragraph separations as the source.\n"
    "4. Finally, return ONLY the translated fields in the specified format. Do not add any extra comments or explanations.\n\n"
    '**Title:** "{title}"\n'
    '**Content:** "{content}"'
)

TELEGRAM_SUMMARY_PROMPT = (
    "Based on the following translated tech news, generate a concise and engaging summary for a Telegram channel. "
    "The summary must be in Persian and should not exceed {max_chars} characters. "
    "Provide the response as a single string of plain text, without any special formatting.\n\n"
    '**Title:** "{title}"\n'
    '**Content:** "{content}"'
)

# ---------------------------
# HTTP helpers
# ---------------------------
def get_post_details(post_id: int):
    """Fetch a post from management-api."""
    try:
        resp = requests.get(f"{MANAGEMENT_API_URL}/posts/{post_id}")
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch details for post_id={post_id}: {e}")
        return None

def save_translation(post_id: int, translation_data: dict):
    """Persist processed translation/summary to management-api."""
    try:
        resp = requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/translations", json=translation_data)
        resp.raise_for_status()
        logger.info(f"✅ Saved translation for post_id={post_id}")
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not save translation for post_id={post_id}: {e}")
        return None

# ---------------------------
# Core processing
# ---------------------------
def _safety_settings():
    # tune as needed for prod
    return [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
    ]

def translate_with_gemini(title: str, content: str) -> Translation:
    if not client:
        raise RuntimeError("Gemini client not initialized")

    sys_instruction = "You are a professional Persian translator. Return ONLY the translation fields. Preserve numbers, punctuation, and line breaks."
    prompt = TRANSLATE_PROMPT.format(title=title or "", content=content or "")
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=sys_instruction,
            response_mime_type="application/json",
            response_schema=Translation,
            temperature=0.2,
            safety_settings=_safety_settings(),
        ),
    )
    obj: Translation = resp.parsed  # Parsed via schema
    if obj:
        return obj
    # Fallback if schema parsing failed
    data = json.loads(resp.text)
    return Translation(**data)

def summarize_for_telegram(title_fa: str, content_fa: str, max_chars: int = 1000) -> str:
    if not client:
        raise RuntimeError("Gemini client not initialized")

    sys_instruction = "You are a concise Persian copywriter for a Telegram tech channel. Return ONLY the summary text without extra formatting or emojis."
    prompt = TELEGRAM_SUMMARY_PROMPT.format(title=title_fa or "", content=content_fa or "", max_chars=max_chars)
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=sys_instruction,
            response_mime_type="application/json",
            response_schema=TelegramSummary,
            temperature=0.3,
            safety_settings=_safety_settings(),
        ),
    )
    obj: TelegramSummary = resp.parsed
    return obj.summary.strip() if (obj and obj.summary) else resp.text.strip()

def process_post_with_ai(post_details: dict):
    """Main pipeline: translate EN->FA then create Telegram summary, send to management-api."""
    post_id = post_details.get("id")
    title = post_details.get("title_original")
    content = post_details.get("content_original")

    if not client:
        logger.error("AI client is not available. Skipping processing.")
        return

    try:
        # 1) Translate
        logger.info(f"Translating post_id={post_id}")
        translation = translate_with_gemini(title, content)

        # 2) Summarize for Telegram
        logger.info(f"Summarizing for Telegram, post_id={post_id}")
        telegram_summary = summarize_for_telegram(
            translation.title_translated, translation.content_translated, max_chars=1000
        )

        # 3) Build payload and persist
        featured_image_url = None
        try:
            imgs = post_details.get("image_urls_original") or []
            if isinstance(imgs, list) and imgs:
                featured_image_url = imgs[0]
        except Exception:
            featured_image_url = None

        final_data = {
            "language": "fa",
            "title_translated": translation.title_translated,
            "content_translated": translation.content_translated,
            "content_telegram": telegram_summary,
            "featured_image_url": featured_image_url,
            "content_instagram": "NULL",
            "content_twitter": "NULL",
        }
        save_translation(post_id, final_data)

    except Exception as e:
        logger.error(f"Error during AI processing for post_id={post_id}: {e}", exc_info=True)

# ---------------------------
# RabbitMQ callback & main
# ---------------------------
def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        if not post_id:
            logger.warning("Received message without post_id; acking.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"📬 Received post_created for post_id={post_id}")
        post_details = get_post_details(post_id)
        if not post_details:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

        process_post_with_ai(post_details)
        logger.info(f"✅ Processed post_id={post_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    logger.info("--- 🧠 Processor Service Started ---")
    if not GEMINI_API_KEY and not os.getenv("GOOGLE_API_KEY"):
        logger.warning("⚠️ No GEMINI_API_KEY/GOOGLE_API_KEY found in env; relying on default client auth.")
    if not client:
        logger.critical("❌ Gemini client is not available; exiting.")
        return

    with RabbitMQClient() as rmq:
        rmq.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info(f"Waiting for messages in '{QUEUE_NAME}'...")
        rmq.start_consuming(queue_name=QUEUE_NAME, callback=callback)

if __name__ == "__main__":
    main()
