# FILE: ./services/fetcher-service/app/main.py

import schedule
import time
import logging
import os
import requests
import feedparser
from dotenv import load_dotenv
from common.rabbit import RabbitMQClient 
from common.logging_config import setup_logging

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")
MAX_CONTENT_LENGTH = 10000 # حداکثر طول مجاز برای محتوای اصلی

def get_all_sources():
    """از management-api لیست تمام منابع را با منطق تلاش مجدد دریافت می‌کند."""
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{MANAGEMENT_API_URL}/sources")
            response.raise_for_status()
            sources = response.json()
            logger.info(f"Successfully fetched {len(sources)} sources.")
            return sources
        except requests.exceptions.RequestException as e:
            sleep_time = 2 ** i
            logger.warning(f"Could not fetch sources from management-api. Retrying in {sleep_time} seconds... (Attempt {i+1}/{max_retries})")
            time.sleep(sleep_time)
    
    logger.error("Could not connect to management-api after several retries.")
    return []

def is_post_new(post_url: str):
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/exists", params={"url_original": post_url})
        response.raise_for_status()
        return not response.json().get("exists", True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not check post existence. URL: {post_url}. Error: {e}")
        return False

def create_post(post_data: dict):
    """یک رکورد پست جدید ایجاد کرده و در صورت موفقیت، پیامی به RabbitMQ ارسال می‌کند."""
    try:
        response = requests.post(f"{MANAGEMENT_API_URL}/posts", json=post_data)
        response.raise_for_status()
        new_post = response.json()
        logger.info(f"Successfully created post: {new_post.get('title_original')}")
        
        try:
            with RabbitMQClient() as client:
                message_body = json.dumps({"post_id": new_post.get("id")})
                client.channel.queue_declare(queue='post_created_queue', durable=True)
                client.publish(exchange_name="", routing_key="post_created_queue", body=message_body)
                logger.info(f"Successfully sent creation notification for post_id: {new_post.get('id')}")
        except Exception as e:
            logger.error(f"Failed to send creation notification for post_id: {new_post.get('id')}. Error: {e}")
            
        return new_post
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not create post. Data: {post_data}. Error: {e}")
        return None

def fetch_job():
    logger.info("🚀 Fetcher job started. Looking for new posts...")
    
    sources = get_all_sources()
    if not sources:
        logger.info("No sources found to fetch. Job finished.")
        return

    for source in sources:
        source_id = source.get("id")
        source_url = source.get("url")
        logger.info(f"Fetching source: {source.get('name')} ({source_url})")
        
        feed = feedparser.parse(source_url)
        
        new_posts_found = 0
        for entry in feed.entries:
            post_url = entry.get("link")
            
            if not post_url or not is_post_new(post_url):
                continue

            # --- START: پاکسازی و کوتاه‌سازی محتوا ---
            content = entry.get("summary", "")
            if len(content) > MAX_CONTENT_LENGTH:
                logger.warning(f"Content from {post_url} is too long ({len(content)} chars). Truncating to {MAX_CONTENT_LENGTH}.")
                content = content[:MAX_CONTENT_LENGTH]
            # --- END: بخش اضافه شده ---

            post_data = {
                "source_id": source_id,
                "title_original": entry.get("title", "No Title"),
                "content_original": content, # <-- استفاده از محتوای پاکسازی شده
                "url_original": post_url,
                "image_urls_original": [img.get('href') for img in entry.get('media_content', []) if img.get('href')]
            }
            if create_post(post_data):
                new_posts_found += 1
        
        logger.info(f"Found {new_posts_found} new posts for source '{source.get('name')}'.")
            
    logger.info("✅ Fetcher job finished.")


def main():
    logger.info("--- 🤖 Fetcher Service Started ---")
    
    schedule.every(5).minutes.do(fetch_job)
    
    logger.info("Initial fetch run will start after a short delay...")
    time.sleep(15)
    fetch_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()