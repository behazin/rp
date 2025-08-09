import mysql.connector
import time
import os
from dotenv import load_dotenv

# مقادیر پیش‌فرض از فایل .env.example خوانده می‌شود
load_dotenv()

DB_USER = os.getenv("MYSQL_USER", "robopost_user")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "strong_password")
DB_HOST = "127.0.0.1" # چون از خارج داکر وصل می‌شویم، از localhost استفاده می‌کنیم
DB_PORT = os.getenv("DB_PORT", 3306)
DB_NAME = os.getenv("MYSQL_DATABASE", "robopost_db")

def test_db_connection():
    """
    به دیتابیس MySQL که در داکر در حال اجراست متصل می‌شود و لاگ می‌اندازد.
    """
    print("--- 🚀 شروع تست اتصال به پایگاه داده ---")
    print(f"مقصد: {DB_HOST}:{DB_PORT}")
    print(f"کاربر: {DB_USER}")
    
    try:
        # تلاش برای برقراری اتصال
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connection_timeout=10 # 10 ثانیه برای اتصال منتظر می‌ماند
        )
        
        if connection.is_connected():
            print("✅ اتصال با موفقیت برقرار شد!")
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION();")
            db_version = cursor.fetchone()
            print(f"✅ نسخه پایگاه داده: {db_version[0]}")
            cursor.close()
            connection.close()
            print("--- ⏹️ تست با موفقیت به پایان رسید ---")
            
    except mysql.connector.Error as e:
        # در صورت بروز خطا، آن را چاپ می‌کند
        print("\n❌❌❌ اتصال با خطا مواجه شد! ❌❌❌")
        print(f"کد خطا: {e.errno}")
        print(f"پیام خطا: {e.msg}")
        print("\nدلایل احتمالی:")
        print("  - آیا کانتینر mysql با `docker-compose up` در حال اجراست؟")
        print("  - آیا پورت 3306 توسط برنامه دیگری اشغال نشده است؟")
        print("  - آیا نام کاربری و رمز عبور در فایل .env شما صحیح است؟")
        print("--- ⏹️ تست با خطا به پایان رسید ---")

if __name__ == "__main__":
    test_db_connection()