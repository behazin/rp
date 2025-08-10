# FILE: ./services/fetcher-service/app/main.py

import schedule
import time
import logging
import os
import requests
import feedparser
from dotenv import load_dotenv

from common.logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

def get_all_sources():
    """از management-api لیست تمام منابع را دریافت می‌کند."""
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/sources")
        response.raise_for_status()
        sources = response.json()
        logger.info(f"Successfully fetched {len(sources)} sources.")
        return sources
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch sources from management-api. Error: {e}")
        return []

def is_post_new(post_url: str):
    """بررسی می‌کند که آیا پستی با این URL قبلاً در دیتابیس ثبت شده است یا خیر."""
    try:
        # این API را در management-api ایجاد کرده‌ایم
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/exists", params={"url_original": post_url})
        response.raise_for_status()
        return not response.json().get("exists", True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not check post existence. URL: {post_url}. Error: {e}")
        # برای جلوگیری از ایجاد پست تکراری، در صورت خطا فرض می‌کنیم وجود دارد
        return False

def create_post(post_data: dict):
    """یک رکورد پست جدید از طریق management-api ایجاد می‌کند."""
    try:
        # این API را نیز در management-api ساخته‌ایم
        response = requests.post(f"{MANAGEMENT_API_URL}/posts", json=post_data)
        response.raise_for_status()
        logger.info(f"Successfully created post: {post_data.get('title_original')}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not create post. Data: {post_data}. Error: {e}")
        return None

def fetch_job():
    """
    وظیفه اصلی که به صورت زمان‌بندی شده اجرا می‌شود.
    """
    logger.info("🚀 Fetcher job started. Looking for new posts...")
    
    sources = get_all_sources()
    if not sources:
        logger.info("No sources found to fetch.")
        return

    for source in sources:
        source_id = source.get("id")
        source_url = source.get("url")
        logger.info(f"Fetching source: {source.get('name')} ({source_url})")
        
        # با feedparser فید را می‌خوانیم
        feed = feedparser.parse(source_url)
        
        for entry in feed.entries:
            post_url = entry.get("link")
            
            # اگر URL وجود نداشت یا پست تکراری بود، از آن عبور می‌کنیم
            if not post_url or not is_post_new(post_url):
                continue

            # استخراج اطلاعات پست
            post_data = {
                "source_id": source_id,
                "title_original": entry.get("title", "No Title"),
                "content_original": entry.get("summary", ""),
                "url_original": post_url,
                # استخراج URL تصاویر از فید (اگر وجود داشته باشد)
                "image_urls_original": [img['href'] for img in entry.get('media_content', []) if 'href' in img]
            }
            create_post(post_data)
            
    logger.info("✅ Fetcher job finished.")


def main():
    logger.info("--- 🤖 Fetcher Service Started ---")
    
    # برای تست، وظیفه را هر 5 دقیقه اجرا می‌کنیم. در محیط عملیاتی می‌توانید این عدد را بیشتر کنید.
    schedule.every(5).minutes.do(fetch_job)
    
    logger.info("Initial fetch run...")
    fetch_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()