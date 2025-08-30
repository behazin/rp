# FILE: ./services/telegram-manager/app/main.py (نسخه نهایی با منطق تلاش مجدد داخلی)

import logging
import os
import requests
import json
import threading
import time
from dotenv import load_dotenv

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, error as telegram_error
from telegram.ext import Dispatcher, CallbackQueryHandler

from fastapi import FastAPI, Request, Response

from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

# --- Configuration ---
load_dotenv()
setup_logging()
logger = logging.getLogger("telegram-manager-webhook")

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")
TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_IDS = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").split(',')
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- RabbitMQ Queues ---
REVIEW_QUEUE = "review_notifications_queue"
FINAL_APPROVAL_QUEUE = "final_approval_notifications_queue"
REJECTED_QUEUE = "post_rejected_queue"

# --- Bot & Dispatcher Initialization ---
bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)

# --- FastAPI App ---
app = FastAPI()

# --- API Helpers (بدون تغییر) ---
def get_post_details(post_id: int):
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/{post_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch details for post_id={post_id}: {e}")
        return None

def mark_as_pending_approval(post_id: int):
    try:
        response = requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/pending")
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not mark post {post_id} as pending. Error: {e}")
        return False

# --- Message Senders & Updaters (بدون تغییر) ---
def send_initial_approval_request(bot_instance, post_data):
    post_id = post_data.get('id')
    translation = post_data['translations'][0]
    title = translation.get('title_translated')
    score = translation.get('score')
    featured_image_url = translation.get('featured_image_url')

    text = (f"📰 **پست جدید برای بازبینی**\n\n"
            f"**شناسه:** `{post_id}`\n"
            f"**امتیاز کیفیت:** {score:.1f}/10\n\n"
            f"**عنوان:** {title}")

    keyboard = [
        [InlineKeyboardButton("✅ تأیید کل (همه پلتفرم‌ها)", callback_data=f"process_all_{post_id}")],
        [
            InlineKeyboardButton("💬 فقط تلگرام", callback_data=f"process_telegram_{post_id}"),
            InlineKeyboardButton("📸 اینستاگرام", callback_data=f"process_instagram_{post_id}"),
            InlineKeyboardButton("🐦 توییتر", callback_data=f"process_twitter_{post_id}"),
        ],
        [InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_{post_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_messages_info = {}
    success = False
    for chat_id in TELEGRAM_ADMIN_CHAT_IDS:
        if not chat_id:
            continue
        try:
            sent_message = None
            if featured_image_url:
                sent_message = bot_instance.send_photo(chat_id=chat_id, photo=featured_image_url,
                                                     caption=text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                sent_message = bot_instance.send_message(chat_id=chat_id, text=text,
                                                      parse_mode="Markdown", reply_markup=reply_markup)

            sent_messages_info[str(sent_message.chat_id)] = sent_message.message_id
            logger.info(f"Sent post_id {post_id} for initial approval to chat_id {chat_id}.")
            success = True

        except Exception as e:
            logger.error(f"Failed to send initial request for post_id {post_id} to chat_id {chat_id}. Error: {e}")

    if success:
        # --- START: این بخش کلیدی اصلاح شده است ---
        # ما دیکشنری اطلاعات پیام‌ها را مستقیماً در فیلد admin_messages ارسال می‌کنیم
        # تا با اسکیمای جدید management-api هماهنگ باشد.
        info_payload = {"admin_messages": sent_messages_info}
        # --- END: بخش اصلاح شده ---
        requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/admin-message-info", json=info_payload).raise_for_status()
        mark_as_pending_approval(post_id)
        
    return success

def update_message_for_final_approval(bot_instance, post_data):
    """پیام همه مدیران را با محتوای پردازش شده آپدیت می‌کند."""
    post_id = post_data.get('id')
    admin_messages_str = post_data.get('admin_message_id')
    
    if not admin_messages_str:
        logger.warning(f"No admin message info found for post_id: {post_id}. Cannot update.")
        return

    try:
        admin_messages = json.loads(admin_messages_str)
    except json.JSONDecodeError:
        logger.error(f"Could not decode admin_messages JSON for post_id: {post_id}")
        return

    translation = post_data['translations'][0]

    base_text = (f"📰 **پست آماده برای تأیید نهایی**\n\n"
                 f"**شناسه:** `{post_id}`\n"
                 f"**امتیاز کیفیت:** {translation.get('score', 0):.1f}/10\n\n"
                 f"**عنوان:** {translation.get('title_translated')}")

    summary_text = ""
    if translation.get('content_telegram'):
        summary_text += f"\n\n📝 **خلاصه تلگرام:**\n_{translation.get('content_telegram')}_"
    
    updated_text = base_text + summary_text

    tg_done = "✅ " if translation.get('content_telegram') else "💬 "
    ig_done = "✅ " if translation.get('content_instagram') else "📸 "
    tw_done = "✅ " if translation.get('content_twitter') else "🐦 "

    keyboard = [
        [InlineKeyboardButton("✅ تأیید کل (همه پلتفرم‌ها)", callback_data=f"process_all_{post_id}")],
        [
            InlineKeyboardButton(f"{tg_done}تلگرام", callback_data=f"process_telegram_{post_id}"),
            InlineKeyboardButton(f"{ig_done}اینستاگرام", callback_data=f"process_instagram_{post_id}"),
            InlineKeyboardButton(f"{tw_done}توییتر", callback_data=f"process_twitter_{post_id}"),
        ],
        [InlineKeyboardButton("🚀 تأیید نهایی و انتشار", callback_data=f"final_approve_{post_id}")],
        [InlineKeyboardButton("❌ رد کردن", callback_data=f"reject_{post_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for chat_id, message_id in admin_messages.items():
        try:
            if post_data.get('translations')[0].get('featured_image_url'):
                bot_instance.edit_message_caption(chat_id=chat_id, message_id=message_id,
                                                caption=updated_text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                bot_instance.edit_message_text(text=updated_text, chat_id=chat_id, message_id=message_id,
                                             parse_mode="Markdown", reply_markup=reply_markup)
        except telegram_error.BadRequest as e:
            if "message is not modified" in str(e):
                logger.warning(f"Message for post {post_id} in chat {chat_id} was already updated. Skipping.")
            else:
                logger.error(f"Failed to update message for post {post_id} in chat {chat_id}. Error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while updating message in chat {chat_id} for post {post_id}: {e}")

    logger.info(f"Finished updating messages for final approval for post_id: {post_id}")
    mark_as_pending_approval(post_id)

# --- RabbitMQ Listeners (با منطق جدید و مقاوم) ---
def on_review_notification(ch, method, properties, body):
    message = json.loads(body)
    post_id = message.get("post_id")
    logger.info(f"Received review notification for post_id: {post_id}")
    post_details = get_post_details(post_id)
    if post_details:
        send_initial_approval_request(bot, post_details)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def on_final_approval_notification(ch, method, properties, body):
    message = json.loads(body)
    post_id = message.get("post_id")
    logger.info(f"Received final approval notification for post_id: {post_id}")
    post_details = get_post_details(post_id)
    if post_details:
        update_message_for_final_approval(bot, post_details)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def on_post_rejected(ch, method, properties, body):
    try:
        message = json.loads(body)
        post_id = message.get("post_id")
        admin_messages_str = message.get("admin_message_id")
        
        if not all([post_id, admin_messages_str]):
            logger.warning("Received invalid 'post_rejected' message. Acking.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            admin_messages = json.loads(admin_messages_str)
        except json.JSONDecodeError:
            logger.error(f"Could not decode admin_messages JSON for post_id: {post_id} in rejection queue.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        logger.info(f"Received 'post_rejected' event for post_id: {post_id}. Deleting messages...")
        for chat_id, message_id in admin_messages.items():
            try:
                bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
            except Exception as e:
                logger.error(f"Failed to delete message for post_id: {post_id} in chat_id: {chat_id}. Error: {e}")
        
        logger.info(f"Successfully processed 'post_rejected' for post_id: {post_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Failed to process 'post_rejected' message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag)

def start_rabbitmq_listeners():
    def listen(queue_name, callback_func):
        # --- START: منطق جدید تلاش مجدد ---
        while True:
            try:
                with RabbitMQClient() as rmq:
                    rmq.channel.queue_declare(queue=queue_name, durable=True)
                    logger.info(f"Successfully connected. Listening on queue '{queue_name}'...")
                    rmq.start_consuming(queue_name=queue_name, callback=callback_func)
            except Exception as e:
                logger.error(f"Could not connect to RabbitMQ for queue '{queue_name}'. Retrying in 10 seconds... Error: {e}")
                time.sleep(10)
        # --- END: منطق جدید تلاش مجدد ---

    threading.Thread(target=listen, args=(REVIEW_QUEUE, on_review_notification), daemon=True).start()
    threading.Thread(target=listen, args=(FINAL_APPROVAL_QUEUE, on_final_approval_notification), daemon=True).start()
    threading.Thread(target=listen, args=(REJECTED_QUEUE, on_post_rejected), daemon=True).start()

# --- Telegram Callback Handler (بدون تغییر) ---
# FILE: ./services/telegram-manager/app/main.py

# --- Telegram Callback Handler (نسخه اصلاح شده) ---
# FILE: ./services/telegram-manager/app/main.py

# --- Telegram Callback Handler (نسخه اصلاح شده) ---
def button_callback(update, context):
    """تمام کلیک‌های روی دکمه‌ها از طرف مدیر را مدیریت می‌کند."""
    query = update.callback_query
    query.answer()
    
    parts = query.data.split("_")
    action = "_".join(parts[:-1])
    post_id_str = parts[-1]
    post_id = int(post_id_str)

    if action == "reject":
        try:
            requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/reject").raise_for_status()
            # پیام به صورت خودکار توسط listener حذف خواهد شد
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to reject post {post_id}. Error: {e}")

    elif action.startswith("process"):
        platforms = []
        if action == "process_all":
            platforms = ["telegram", "instagram", "twitter"]
        else:
            platforms.append(action.replace("process_", ""))
        
        try:
            requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/process-content", json={"platforms": platforms}).raise_for_status()
            text = query.message.caption or query.message.text
            
            # --- START: تغییر کلیدی ---
            # دیگر کیبورد را حذف نمی‌کنیم، فقط متن را آپدیت می‌کنیم
            # و reply_markup اصلی پیام را دوباره به آن پاس می‌دهیم تا باقی بماند.
            if query.message.caption:
                query.edit_message_caption(
                    caption=f"{text}\n\n⏳ *در حال پردازش برای: {', '.join(platforms)}...*",
                    reply_markup=query.message.reply_markup
                )
            else:
                query.edit_message_text(
                    text=f"{text}\n\n⏳ *در حال پردازش برای: {', '.join(platforms)}...*",
                    reply_markup=query.message.reply_markup
                )
            # --- END: پایان تغییر کلیدی ---

        except requests.exceptions.RequestException as e:
            context.bot.send_message(chat_id=query.message.chat_id, text=f"⚠️ خطا در درخواست پردازش برای پست {post_id}.")
            logger.error(f"Failed to request content processing for post_id {post_id}. Error: {e}")

    elif action == "final_approve":
        try:
            requests.post(f"{MANAGEMENT_API_URL}/posts/{post_id}/approve").raise_for_status()
            text = query.message.caption or query.message.text
            # پس از تایید نهایی، کیبورد را حذف می‌کنیم
            query.edit_message_reply_markup(reply_markup=None)
            if query.message.caption:
                query.edit_message_caption(caption=f"{text}\n\n✅ *تأیید نهایی شد. در صف انتشار قرار گرفت.*",)
            else:
                query.edit_message_text(text=f"{text}\n\n✅ *تأیید نهایی شد. در صف انتشار قرار گرفت.*")
        except requests.exceptions.RequestException as e:
            context.bot.send_message(chat_id=query.message.chat_id, text=f"⚠️ خطا در تأیید نهایی پست {post_id}.")
            logger.error(f"Failed to final approve post {post_id}. Error: {e}")

# --- FastAPI Webhook Endpoint (بدون تغییر) ---
@app.post("/telegram-webhook")
async def handle_telegram_updates(request: Request):
    update_data = await request.json()
    update = Update.de_json(update_data, bot)
    dispatcher.process_update(update)
    return Response(status_code=200)

@app.get("/healthz")
def health_check():
    return {"status": "OK"}

# --- Application Startup (حذف time.sleep) ---
@app.on_event("startup")
async def startup_event():
    logger.info("--- 🛂 Telegram Manager Service (Webhook Mode) Started ---")
    if not WEBHOOK_URL:
        logger.critical("❌ WEBHOOK_URL environment variable is not set.")
        return
    if not all([TELEGRAM_ADMIN_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_IDS]):
        logger.critical("❌ TELEGRAM_ADMIN_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID must be set.")
        return

    logger.info(f"Setting webhook to: {WEBHOOK_URL}")
    if not bot.set_webhook(url=WEBHOOK_URL):
        logger.error("Webhook setup failed!")
    else:
        logger.info("Webhook setup successful!")

    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    start_rabbitmq_listeners()
