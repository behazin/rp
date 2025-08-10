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