import schedule
import time
import logging
import os
import requests
import feedparser
import json
from urllib.parse import urlparse
import trafilatura
from newspaper import Article
from dotenv import load_dotenv
from common.logging_config import setup_logging
from common.rabbit import RabbitMQClient

# ---------------------------
# Bootstrap
# ---------------------------
load_dotenv()
setup_logging()
logger = logging.getLogger("fetcher-service")

MANAGEMENT_API_URL = os.getenv("MANAGEMENT_API_URL", "http://management-api:8000")

# ---------------------------
# Helpers
# ---------------------------
def is_http_url(u: str) -> bool:
    """Return True only for valid http/https URLs with a netloc."""
    if not u or not isinstance(u, str):
        return False
    try:
        p = urlparse(u.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def get_all_sources():
    """Fetches all sources from the management-api with a retry logic."""
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{MANAGEMENT_API_URL}/sources", timeout=15)
            response.raise_for_status()
            sources = response.json()
            logger.info(f"Successfully fetched {len(sources)} sources.")
            return sources
        except requests.exceptions.RequestException as e:
            sleep_time = 2 ** i
            logger.warning(
                f"Could not fetch sources from management-api. Retrying in {sleep_time} seconds... "
                f"(Attempt {i+1}/{max_retries}) | Error: {e}"
            )
            time.sleep(sleep_time)
    logger.error("Could not connect to management-api after several retries.")
    return []

def is_post_new(post_url: str):
    """Checks if a post with the given URL already exists."""
    try:
        response = requests.get(f"{MANAGEMENT_API_URL}/posts/exists", params={"url_original": post_url}, timeout=15)
        response.raise_for_status()
        return not response.json().get("exists", True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not check post existence. URL: {post_url}. Error: {e}")
        return False

def create_post(post_data: dict):
    """Creates a new post record and sends a message to RabbitMQ on success."""
    # Final safety: ensure URL fields are valid before POST
    post_url = post_data.get("url_original")
    if not is_http_url(post_url):
        logger.warning(f"Skipping post with invalid url_original: {post_url}")
        return None

    images = post_data.get("image_urls_original") or []
    images = [u for u in images if is_http_url(u)]
    post_data["image_urls_original"] = images

    try:
        response = requests.post(f"{MANAGEMENT_API_URL}/posts", json=post_data, timeout=20)
        response.raise_for_status()
        new_post = response.json()
        logger.info(f"✅ Created post: {new_post.get('title_original')} (id={new_post.get('id')})")
        try:
            with RabbitMQClient() as client:
                message_body = json.dumps({"post_id": new_post.get("id")})
                client.channel.queue_declare(queue='post_created_queue', durable=True)
                client.publish(exchange_name="", routing_key="post_created_queue", body=message_body)
                logger.info(f"📤 Notified post_created for post_id={new_post.get('id')}")
        except Exception as e:
            logger.error(f"Failed to send creation notification for post_id: {new_post.get('id')}. Error: {e}")
        return new_post
    except requests.exceptions.HTTPError as e:
        # Log response body for 4xx/5xx diagnostics
        body = ""
        try:
            body = response.text[:2000]
        except Exception:
            pass
        logger.error(f"Could not create post. Data: {post_data}. Error: {e}. Body: {body}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not create post. Data: {post_data}. Error: {e}")
        return None

# ---------------------------
# Fetch job
# ---------------------------
def fetch_job():
    logger.info("🚀 Fetcher job started. Looking for new posts...")
    sources = get_all_sources()
    if not sources:
        logger.info("No sources found to fetch. Job finished.")
        return

    for source in sources:
        source_id = source.get("id")
        source_url = source.get("url")
        source_name = source.get("name", "Unnamed Source")
        logger.info(f"Fetching source: {source_name} ({source_url})")

        try:
            feed = feedparser.parse(source_url)
        except Exception as e:
            logger.error(f"Failed to parse feed: {source_url}. Error: {e}")
            continue

        new_posts_found = 0

        for entry in feed.entries[:1]:
            post_url = entry.get("link")
            if not is_http_url(post_url):
                logger.debug(f"Skipping entry with invalid link: {post_url}")
                continue

            try:
                # Skip if already exists
                if not is_post_new(post_url):
                    logger.debug(f"Already exists (skipping): {post_url}")
                    continue

                # Title (fallback to feed title if needed)
                title = entry.get("title") or "No Title"

                # Use newspaper3k to fetch full article & images
                article = Article(post_url)
                article.download()
                article.parse()

                content = (article.text or "").strip()
                if not content:
                    logger.warning(f"Newspaper3k could not extract main content from {post_url}. Skipping.")
                    continue

                image_url = None
                
                # مرحله ۱: تلاش با trafilatura (روش دقیق‌تر)
                metadata = trafilatura.extract_metadata(article.html)
                if metadata and metadata.image:
                    image_url = metadata.image

                # مرحله ۲: اگر روش اول ناموفق بود، از newspaper3k استفاده می‌کنیم
                if not image_url:
                    image_url = article.top_image

                # اعتبارسنجی نهایی URL و آماده‌سازی لیست برای ارسال
                images = []
                if image_url and is_http_url(image_url):
                    images.append(image_url)
                # --- END: پایان بخش اصلاح شده ---
                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

                post_data = {
                    "source_id": source_id,
                    "title_original": title,
                    "content_original": content,
                    "url_original": post_url,
                    "image_urls_original": images,
                }

                if create_post(post_data):
                    new_posts_found += 1

            except Exception as e:
                logger.error(f"Failed to process article {post_url}. Error: {e}", exc_info=True)

        logger.info(f"Found {new_posts_found} new posts for source '{source_name}'.")

    logger.info("✅ Fetcher job finished.")

# ---------------------------
# Main loop
# ---------------------------
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
