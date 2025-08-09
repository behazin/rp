# FILE: ./common/logging_config.py
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """
    لاگر اصلی را برای خروجی لاگ‌های JSON به stdout پیکربندی می‌کند.
    این تابع باید یک بار در هنگام شروع به کار هر سرویس فراخوانی شود.
    """
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()
        
    log_handler = logging.StreamHandler(sys.stdout)
    
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    
    logging.info("JSON logging configured successfully.")