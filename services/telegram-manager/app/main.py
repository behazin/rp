# FILE: ./services/telegram-manager/app/main.py

import logging
import os
import json
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
def get_pending_posts():
    """Fetches all posts with 'pending_approval' status."""
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/pending")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch pending posts. Error: {e}")
        return []

def send_approval_request(bot, post):
    """Sends a single post to the admin for approval."""
    post_id = post.get('id')
    title = post.get('translations')[0].get('title_translated') if post.get('translations') else post.get('title_original')
    summary = post.get('translations')[0].get('content_telegram') if post.get('translations') else post.get('content_original', '')[:200]
    
    text = f"📰 **پست جدید برای تایید**\n\n"
    text += f"**شناسه:** `{post_id}`\n"
    text += f"**عنوان:** {title}\n\n"
    text += f"**خلاصه:**\n{summary}..."
    
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"reject_{post_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        message = bot.send_message(
            chat_id=TELEGRAM_ADMIN_CHAT_ID, 
            text=text, 
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        # Store message_id to be able to edit it later
        # (This part requires adding a new API endpoint, skipping for now for simplicity)
        logger.info(f"Sent post_id {post_id} for approval.")
    except Exception as e:
        logger.error(f"Failed to send post_id {post_id} to admin. Error: {e}")


def button_callback(update, context):
    """Handles button presses from the admin."""
    query = update.callback_query
    query.answer()
    
    action, post_id_str = query.data.split("_")
    post_id = int(post_id_str)
    
    api_url = f"{MANAGEMENT_API_URL}/posts/{post_id}/{action}" # action will be 'approve' or 'reject'
    
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

def check_for_pending_posts_job(bot):
    """The scheduled job that checks for new posts."""
    logger.info("Checking for pending posts...")
    pending_posts = get_pending_posts()
    
    # In a real scenario, you'd track which posts have already been sent to the admin.
    # For now, we'll keep it simple and send all pending posts each time.
    for post in pending_posts:
        send_approval_request(bot, post)

def main():
    logger.info("--- 🛂 Telegram Manager Service Started ---")
    if not all([TELEGRAM_ADMIN_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID]):
        logger.critical("❌ TELEGRAM_ADMIN_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID must be set.")
        return

    updater = Updater(TELEGRAM_ADMIN_BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    # Schedule the job to run every 1 minute
    schedule.every(1).minutes.do(check_for_pending_posts_job, bot=updater.bot)
    
    # Run the job once at startup after a short delay
    logger.info("Performing initial check for pending posts...")
    time.sleep(10)
    check_for_pending_posts_job(updater.bot)
    
    # Start the bot and the scheduler
    updater.start_polling()
    logger.info("Telegram bot is polling for updates...")

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()