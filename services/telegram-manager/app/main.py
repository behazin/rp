# FILE: ./services/telegram-manager/app/main.py

import logging
import os
import requests
import time
import schedule
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler

from common.logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger("telegram-manager")

# --- Configuration ---
MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")
TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

# --- API Helpers ---
def get_posts_for_admin_review():
    """Fetches posts that are 'fetched' AND have translations."""
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/fetched")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch posts for admin review. Error: {e}")
        return []

def mark_as_pending_approval(post_id: int):
    """Marks a post as PENDING_APPROVAL after sending it to the admin."""
    try:
        # نام این تابع در management.py همچنان mark_post_as_pending است
        response = requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/sent_to_admin")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not mark post {post_id} as pending. Error: {e}")
        return False

def send_approval_request(bot, post):
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    post_id = post.get('id')
    title = post.get('translations')[0].get('title_translated') if post.get('translations') else post.get('title_original')
    summary = post.get('translations')[0].get('content_telegram') if post.get('translations') else post.get('content_original', '')[:200]
    
    text = f"📰 **پست جدید برای تایید**\n\n"
    text += f"**شناسه:** `{post_id}`\n"
    text += f"**عنوان:** {title}\n\n"
    text += f"**خلاصه:**\n{summary}..."
    
    keyboard = [[
        InlineKeyboardButton("✅ تایید", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"reject_{post_id}"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID, 
            text=text, 
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logger.info(f"Sent post_id {post_id} for approval.")
        return True
    except Exception as e:
        logger.error(f"Failed to send post_id {post_id} to admin. Error: {e}")
        return False

def button_callback(update, context):
    # ... (این تابع بدون تغییر باقی می‌ماند) ...
    query = update.callback_query
    query.answer()
    action, post_id_str = query.data.split("_")
    post_id = int(post_id_str)
    api_url = f"{MANAGEMENT_API_URL}/posts/{post_id}/{action}"
    try:
        response = requests.post(api_url)
        response.raise_for_status()
        if action == "approve":
            query.edit_message_text(text=f"✅ پست شماره {post_id} با موفقیت تایید شد.")
            logger.info(f"Admin approved post_id: {post_id}")
        elif action == "reject":
            query.edit_message_text(text=f"❌ پست شماره {post_id} رد شد.")
            logger.info(f"Admin rejected post_id: {post_id}")
    except requests.exceptions.RequestException as e:
        query.edit_message_text(text=f"⚠️ خطا در پردازش درخواست برای پست {post_id}. Error: {e}")
        logger.error(f"API call failed for post_id {post_id}, action {action}. Error: {e}")

def check_and_send_job(bot):
    """The scheduled job that sends new processed posts to the admin."""
    logger.info("Checking for new posts to send to admin...")
    posts_to_review = get_posts_for_admin_review()
    
    if not posts_to_review:
        logger.info("No new processed posts to send.")
        return 0 # 0 پست ارسال شد

    sent_count = 0
    for post in posts_to_review:
        if send_approval_request(bot, post):
            if mark_as_pending_approval(post.get('id')):
                sent_count += 1
    
    logger.info(f"Sent {sent_count} new posts to admin for review.")
    return sent_count


def main():
    logger.info("--- 🛂 Telegram Manager Service Started ---")
    if not all([TELEGRAM_ADMIN_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID]):
        logger.critical("❌ TELEGRAM_ADMIN_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID must be set.")
        return

    updater = Updater(TELEGRAM_ADMIN_BOT_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    # --- START: حل مشکل ریس کاندیشن در اجرای اولیه ---
    logger.info("Performing initial check for posts...")
    initial_sent_count = 0
    for i in range(5): # تا ۵ بار تلاش می‌کند
        initial_sent_count = check_and_send_job(updater.bot)
        if initial_sent_count > 0:
            break
        logger.info(f"No posts found on initial check (attempt {i+1}/5). Retrying in 20 seconds...")
        time.sleep(20)
    # --- END: بخش اضافه شده ---

    # زمان‌بندی برای اجرای منظم در آینده
    schedule.every(1).minutes.do(check_and_send_job, bot=updater.bot)
    
    updater.start_polling()
    logger.info("Telegram bot is polling for updates...")

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()