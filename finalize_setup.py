# FILE: ./finalize_setup.py

from pathlib import Path

# --- محتوای نهایی docker-compose.yml ---

FINAL_DOCKER_COMPOSE = """
# FILE: ./docker-compose.yml

networks:
  robopost_network:
    driver: bridge

volumes:
  mysql_data:
  rabbitmq_data:

services:
  mysql:
    image: mysql:8.0
    container_name: mysql
    restart: unless-stopped
    env_file: .env
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - robopost_network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u$${MYSQL_USER}", "-p$${MYSQL_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  rabbitmq:
    image: rabbitmq:3.11-management-alpine
    container_name: rabbitmq
    restart: unless-stopped
    env_file: .env
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq/
    networks:
      - robopost_network
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  management-api:
    build:
      context: ./services/management-api
      dockerfile: Dockerfile
    container_name: management-api
    env_file: .env
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./services/management-api:/usr/src/app
      - ./common:/usr/src/app/common
    networks:
      - robopost_network
    depends_on:
      mysql:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  fetcher-service:
    build:
      context: ./services/fetcher-service
      dockerfile: Dockerfile
    container_name: fetcher-service
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./services/fetcher-service/app:/usr/src/app/app
      - ./common:/usr/src/app/common
    environment:
      - PYTHONPATH=/usr/src/app
    networks:
      - robopost_network
    depends_on:
      management-api:
        condition: service_started

  publisher-service:
    build:
      context: ./services/publisher-service
      dockerfile: Dockerfile
    container_name: publisher-service
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./services/publisher-service/app:/usr/src/app/app
      - ./common:/usr/src/app/common
    environment:
      - PYTHONPATH=/usr/src/app
    networks:
      - robopost_network
    depends_on:
      management-api:
        condition: service_started
      rabbitmq:
        condition: service_healthy
"""

# --- محتوای نهایی common/rabbit.py ---

RESILIENT_RABBIT_PY = """
# FILE: ./common/rabbit.py
import pika
import os
import logging
import time
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        self.user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.connection = None
        self.channel = None

    def _connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(self.host, self.port, '/', credentials)
        
        max_retries = 10
        for i in range(max_retries):
            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                logger.info("✅ Successfully connected to RabbitMQ.")
                return
            except pika.exceptions.AMQPConnectionError as e:
                sleep_time = 2 ** i
                logger.warning(f"RabbitMQ connection failed. Retrying in {sleep_time} seconds... (Attempt {i+1}/{max_retries})")
                time.sleep(sleep_time)
        
        logger.critical("❌ Could not connect to RabbitMQ after several retries.")
        raise pika.exceptions.AMQPConnectionError("Failed to connect to RabbitMQ.")


    def publish(self, exchange_name: str, routing_key: str, body: str):
        if not self.channel or self.channel.is_closed:
            self._connect()
        
        self.channel.basic_publish(
            exchange=exchange_name,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logger.info(f"Message published to exchange '{exchange_name}' with key '{routing_key}'.")

    def start_consuming(self, queue_name: str, callback):
        if not self.channel or self.channel.is_closed:
            self._connect()
        
        self.channel.basic_qos(prefetch_count=1)
        
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback
        )
        
        logger.info(f"Waiting for messages in queue '{queue_name}'. To exit press CTRL+C")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.close()

    def close(self):
        if self.channel and self.channel.is_open:
            self.channel.close()
        if self.connection and self.connection.is_open:
            self.connection.close()
        logger.info("RabbitMQ connection closed.")

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
"""

def main():
    print("🚀 شروع به‌روزرسانی نهایی فایل‌های پروژه...")
    print("-" * 60)
    
    root_path = Path(".")
    
    # به‌روزرسانی docker-compose.yml
    (root_path / "docker-compose.yml").write_text(FINAL_DOCKER_COMPOSE.strip(), encoding='utf-8')
    print("📄 فایل به‌روزرسانی شد: docker-compose.yml")

    # به‌روزرسانی common/rabbit.py
    (root_path / "common" / "rabbit.py").write_text(RESILIENT_RABBIT_PY.strip(), encoding='utf-8')
    print("📄 فایل به‌روزرسانی شد: common/rabbit.py")

    print("-" * 60)
    print("✅ تمام فایل‌های پیکربندی با موفقیت اصلاح شدند!")
    print("ℹ️ اکنون می‌توانید با اطمینان کامل دستور `docker-compose up --build` را اجرا کنید.")

if __name__ == "__main__":
    main()