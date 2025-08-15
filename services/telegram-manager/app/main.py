# FILE: ./services/telegram-manager/app/main.py

import logging
import os
import requests
import time
import schedule
import json
import threading
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

# --- Configuration ---
load_dotenv()
setup_logging()
logger = logging.getLogger("telegram-manager")

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")
TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
REJECTED_QUEUE_NAME = "post_rejected_queue"

# --- API Helpers ---
def get_posts_for_admin_review():
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/fetched")
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        body = e.response.text if getattr(e, "response", None) else ""
        logger.error(f"Could not fetch posts for admin review. {e}. Body: {body}")
        return []

def mark_as_pending_approval(post_id: int):
    try:
        response = requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/pending")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not mark post {post_id} as pending. Error: {e}")
        return False

def send_approval_request(bot, post):
    """یک پست را برای ادمین ارسال می‌کند و در صورت نامعتبر بودن عکس، به حالت متنی بازمی‌گردد."""
    post_id = post.get('id')
    translation = post.get('translations')[0] if post.get('translations') else {}
    title = translation.get('title_translated') or post.get('title_original')
    summary = translation.get('content_telegram') or post.get('content_original', '')[:200]
    featured_image_url = translation.get('featured_image_url')
    
    text = f"📰 **پست جدید برای تایید**\n\n"
    text += f"**شناسه:** `{post_id}`\n"
    text += f"**عنوان:** {title}\n\n"
    text += f"**خلاصه:**\n{summary}..."
    
    keyboard = [[
        InlineKeyboardButton("✅ تایید", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"reject_{post_id}"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent_message = None
    try:
        if featured_image_url:
            try:
                # ۱. تلاش اولیه برای ارسال با عکس
                sent_message = bot.send_photo(
                    chat_id=TELEGRAM_ADMIN_CHAT_ID,
                    photo=featured_image_url,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            except telegram.error.BadRequest as e:
                # ۲. اگر خطا مربوط به محتوای نامعتبر بود، به حالت متنی بازمی‌گردیم
                if 'Wrong type of the web page content' in str(e):
                    logger.warning(f"Invalid image URL for post_id {post_id}. Sending as text. URL: {featured_image_url}")
                    sent_message = bot.send_message(
                        chat_id=TELEGRAM_ADMIN_CHAT_ID,
                        text=text,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                else:
                    # اگر خطای دیگری بود، آن را دوباره ایجاد می‌کنیم تا مدیریت شود
                    raise e
        else:
            # اگر از ابتدا تصویری وجود نداشت
            sent_message = bot.send_message(
                chat_id=TELEGRAM_ADMIN_CHAT_ID, 
                text=text, 
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

        logger.info(f"Sent post_id {post_id} for approval.")
        
        # ۳. اطلاعات پیام (چه با عکس چه بی عکس) را ذخیره می‌کنیم
        if sent_message:
            info_payload = {"admin_chat_id": sent_message.chat_id, "admin_message_id": sent_message.message_id}
            try:
                requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/admin-message-info", json=info_payload).raise_for_status()
                logger.info(f"Successfully saved admin message info for post_id {post_id}.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to save admin message info for post_id {post_id}. Error: {e}")
                
        return True
    except Exception as e:
        logger.error(f"Failed to send post_id {post_id} to admin. Error: {e}")
        return False


def button_callback(update, context):
    query = update.callback_query
    query.answer()
    action, post_id_str = query.data.split("_")
    post_id = int(post_id_str)
    api_url = f"{MANAGEMENT_API_URL}/posts/{post_id}/{action}"
    try:
        response = requests.post(api_url)
        response.raise_for_status()

        # --- START: بخش کلیدی اصلاح شده ---
        if action == "approve":
            response_text = f"✅ پست شماره {post_id} با موفقیت تایید شد."
            logger.info(f"Admin approved post_id: {post_id}")
            # فقط در صورت تایید، کپشن را ویرایش می‌کنیم
            if query.message.photo:
                query.edit_message_caption(caption=response_text)
            else:
                query.edit_message_text(text=response_text)

        elif action == "reject":
            # در صورت رد کردن، فقط لاگ می‌اندازیم و منتظر حذف پیام از طریق RabbitMQ می‌مانیم
            logger.info(f"Admin rejected post_id: {post_id}")
            # هیچ ویرایشی روی پیام انجام نمی‌شود
        # --- END: پایان بخش اصلاح شده ---

    except requests.exceptions.RequestException as e:
        error_text = f"⚠️ خطا در پردازش درخواست برای پست {post_id}."
        if query.message.photo:
            query.edit_message_caption(caption=error_text)
        else:
            query.edit_message_text(text=error_text)
        logger.error(f"API call failed for post_id {post_id}, action {action}. Error: {e}")

def check_and_send_job(bot):
    logger.info("Checking for new posts to send to admin...")
    posts_to_review = get_posts_for_admin_review()
    if not posts_to_review:
        logger.info("No new processed posts to send.")
        return
    for post in posts_to_review:
        if send_approval_request(bot, post):
            mark_as_pending_approval(post.get('id'))

# --- START: بخش جدید برای مدیریت رویدادهای RabbitMQ ---

def on_post_rejected(ch, method, properties, body):
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        chat_id = message.get("admin_chat_id")
        message_id = message.get("admin_message_id")
        if not all([post_id, chat_id, message_id]):
            logger.warning("Received invalid 'post_rejected' message. Acking.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        logger.info(f"Received 'post_rejected' event for post_id: {post_id}. Deleting message...")
        bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
        bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
        logger.info(f"Successfully deleted admin message for post_id: {post_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Failed to process 'post_rejected' message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag)

def start_rejection_listener():
    logger.info("Starting RabbitMQ listener for rejected posts...")
    with RabbitMQClient() as client:
        client.channel.queue_declare(queue=REJECTED_QUEUE_NAME, durable=True)
        client.start_consuming(queue_name=REJECTED_QUEUE_NAME, callback=on_post_rejected)

# --- END: بخش جدید ---

def main():
    logger.info("--- 🛂 Telegram Manager Service Started ---")
    if not all([TELEGRAM_ADMIN_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID]):
        logger.critical("❌ TELEGRAM_ADMIN_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID must be set.")
        return
    rejection_thread = threading.Thread(target=start_rejection_listener, daemon=True)
    rejection_thread.start()
    updater = Updater(TELEGRAM_ADMIN_BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    schedule.every(1).minutes.do(check_and_send_job, bot=updater.bot)
    time.sleep(10)
    check_and_send_job(updater.bot)
    updater.start_polling()
    logger.info("Telegram bot is polling for updates...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()