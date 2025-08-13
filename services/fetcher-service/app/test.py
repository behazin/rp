import requests
from trafilatura import extract_metadata, extract

# آدرس صفحه وب
url = "https://www.zdnet.com/article/waze-vs-google-maps-i-compared-two-of-the-best-navigation-apps-and-heres-the-clear-winner/"

try:
    # ارسال درخواست به صفحه وب
    response = requests.get(url)

    if response.status_code == 200:
        # استخراج متن اصلی مقاله
        article_text = extract(response.text, output_format="json", with_metadata=True, include_links=False)
        
        # استخراج متادیتا (شامل عنوان)
        metadata = extract_metadata(response.text)

        if metadata and article_text:
            print("عنوان مقاله:", metadata.title)
            print("-" * 50) # خط جداکننده
            print("متن مقاله:")
            print(article_text)
        else:
            print("خطا: اطلاعاتی برای استخراج یافت نشد.")
    else:
        print(f"خطا در دریافت صفحه وب. کد وضعیت: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"خطا در اتصال: {e}")