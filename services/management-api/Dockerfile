# FILE: ./services/management-api/Dockerfile
FROM python:3.9-slim

WORKDIR /usr/src/app

# --- بهینه سازی لایه کش ---
# 1. ابتدا فقط فایل‌های مورد نیاز برای نصب پکیج‌ها را کپی می‌کنیم.
# این لایه فقط زمانی بازسازی می‌شود که این فایل‌ها تغییر کنند.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2. حالا تمام کدهای منبع پروژه را کپی می‌کنیم.
# این شامل setup.py و پوشه app می‌شود.
COPY . .

# 3. اکنون که setup.py در دسترس است، پروژه را نصب می‌کنیم.
# این لایه فقط زمانی بازسازی می‌شود که کد شما تغییر کند.
RUN pip install -e .

# پورت پیش‌فرض برای FastAPI
EXPOSE 8000