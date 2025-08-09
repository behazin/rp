# FILE: ./common/rabbit.py
import pika
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class RabbitMQClient:
    """
    یک کلاینت RabbitMQ برای مدیریت اتصال، انتشار و مصرف پیام‌ها.
    این کلاس به صورت Context Manager (`with`) قابل استفاده است.
    """
    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        self.user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.connection = None
        self.channel = None

    def _connect(self):
        """اتصال به RabbitMQ را برقرار می‌کند."""
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(self.host, self.port, '/', credentials)
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Successfully connected to RabbitMQ.")
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def publish(self, exchange_name: str, routing_key: str, body: str):
        """یک پیام را در یک exchange منتشر می‌کند."""
        if not self.channel or self.channel.is_closed:
            self._connect()
        
        self.channel.basic_publish(
            exchange=exchange_name,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        logger.info(f"Message published to exchange '{exchange_name}' with key '{routing_key}'.")

    def start_consuming(self, queue_name: str, callback):
        """شروع به مصرف پیام از یک صف مشخص می‌کند."""
        if not self.channel or self.channel.is_closed:
            self._connect()
        
        # Fair Dispatch: تضمین می‌کند که هر worker فقط یک پیام در لحظه پردازش می‌کند.
        self.channel.basic_qos(prefetch_count=1)
        
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback
            # auto_ack=False is handled in the consumer callback
        )
        
        logger.info(f"Waiting for messages in queue '{queue_name}'. To exit press CTRL+C")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.close()

    def close(self):
        """اتصال را می‌بندد."""
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