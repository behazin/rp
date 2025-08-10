# FILE: ./seed_sources.py

import requests
from urllib.parse import urlparse

# لیست کامل فیدهای خبری شما
SOURCES = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "Wired": "https://www.wired.com/feed/rss",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Engadget": "https://www.engadget.com/rss.xml",
    "Gizmodo": "https://gizmodo.com/feed",
    "CNET": "https://www.cnet.com/rss/news/",
    "Mashable": "https://mashable.com/feeds/rss/tech",
    "ZDNet": "https://www.zdnet.com/rss.xml",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "VentureBeat": "https://feeds.feedburner.com/venturebeat/SZYF",
    "The Next Web": "https://thenextweb.com/rss.xml",
    "IEEE Spectrum": "https://spectrum.ieee.org/feeds/feed.rss",
    "How-To Geek": "https://www.howtogeek.com/feed/",
    "Business Insider": "https://feeds.businessinsider.com/custom/all",
    "Vox": "https://www.vox.com/rss/index.xml",
    "PCWorld": "https://www.pcworld.com/feed",
    "Android Central": "https://www.androidcentral.com/feeds.xml",
    "GSMArena": "https://www.gsmarena.com/rss-news-reviews.php3",
    "Macworld": "https://www.macworld.com/en-us/feed",
    "MacRumors": "https://feeds.macrumors.com/MacRumors-All",
    "AppleInsider": "https://appleinsider.com/rss/news",
    "9to5Mac": "https://9to5mac.com/feed/",
    "Slashdot": "https://rss.slashdot.org/Slashdot/slashdotMain",
    "Tom's Hardware": "https://www.tomshardware.com/feeds.xml",
    "GeekWire": "https://www.geekwire.com/feed/",
    "Product Hunt": "https://www.producthunt.com/feed",
    "SlashGear": "https://www.slashgear.com/category/news/feed/",
    "TechSpot": "https://www.techspot.com/backend.xml",
    "Bleeping Computer": "https://www.bleepingcomputer.com/feed/",
    "Tom's Guide": "https://www.tomsguide.com/feeds.xml",
    "MakeUseOf": "https://www.makeuseof.com/feed/",
    "Ubergizmo": "https://www.ubergizmo.com/rss/",
    "Pocket-lint": "https://www.pocket-lint.com/feed/",
    "BGR": "https://www.bgr.com/category/tech/feed/",
    "Gizchina": "https://www.gizchina.com/feed/",
    "New Atlas": "https://newatlas.com/index.rss",
    "Futurism": "https://futurism.com/feed",
    "Yanko Design": "https://www.yankodesign.com/feed/",
    "Singularity Hub": "https://singularityhub.com/feed/",
    "Next Big Future": "https://www.nextbigfuture.com/feed/",
    "Popular Science": "https://www.popsci.com/feed/",
    "ReadWrite": "https://readwrite.com/feed/",
    "Inverse": "https://www.inverse.com/rss",
    "Silicon Republic": "https://www.siliconrepublic.com/category/gear/feed/",
    "TechHive": "https://www.techhive.com/feed",
    "Fossbytes": "https://fossbytes.com/feed/",
    "Android Police": "https://www.androidpolice.com/feed/",
    "Droid Life": "https://www.droid-life.com/feed",
    "Hackaday": "https://hackaday.com/feed/",
    "EdSurge": "https://www.edsurge.com/articles_rss",
    "Electrek": "https://electrek.co/feed/",
    "Designboom": "https://www.designboom.com/technology/feed/",
    "Popular Mechanics": "https://www.popularmechanics.com/rss/all.xml",
    "Techmeme": "https://www.techmeme.com/feed.xml",
    "The Register": "https://www.theregister.com/headlines.atom",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "O'Reilly Radar": "https://www.oreilly.com/radar/feed/index.xml",
    "UploadVR": "https://www.uploadvr.com/rss/",
    "Robohub": "https://robohub.org/feed?cat=-473",
    "Windows Central": "https://www.windowscentral.com/feeds.xml",
    "Geeky Gadgets": "https://www.geeky-gadgets.com/feed/",
    "The Gadgeteer": "https://the-gadgeteer.com/feed/",
    "BetaNews": "https://betanews.com/feed/",
    "SiliconANGLE": "https://siliconangle.com/feed/",
    "Daring Fireball": "https://daringfireball.net/feeds/main",
    "Trusted Reviews": "https://www.trustedreviews.com/feed",
    "PhoneArena": "https://www.phonearena.com/feed/reviews",
    "XDA-Developers": "https://www.xda-developers.com/feed/",
    "Lifehacker": "https://lifehacker.com/feed/rss",
    "Ausdroid": "https://ausdroid.net/feed/",
    "Redmond Pie": "https://www.redmondpie.com/comments/feed/",
    "Wccftech": "https://wccftech.com/feed/",
    "Cult of Mac": "https://www.cultofmac.com/feed/",
    "Hacker News": "https://news.ycombinator.com/rss",
    "T3": "https://www.t3.com/feeds.xml",
    "The Gadgetflow": "https://thegadgetflow.com/blog/?feed=gfl_google_news",
    "Walyou": "https://walyou.com/feed/",
    "MacStories": "https://www.macstories.net/?feed=articles-only",
    "Technode": "https://technode.com/feed/",
    "Lifewire": "https://feeds-api.dotdashmeredith.com/v1/rss/google/e4127c67-f649-4b92-9ad2-ea112f7e33ae"
}

API_URL = "http://localhost:8000/sources"

def add_sources():
    """
    لیست منابع را به دیتابیس اضافه می‌کند.
    """
    print(f"🚀 شروع اضافه کردن {len(SOURCES)} منبع به دیتابیس...")
    print("-" * 50)
    
    success_count = 0
    fail_count = 0
    
    for name, url in SOURCES.items():
        payload = {
            "name": name,
            "url": url
        }
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            if response.status_code == 201:
                print(f"✅  موفق: '{name}' اضافه شد.")
                success_count += 1
            elif response.status_code == 400:
                print(f"🟡  تکراری: '{name}' از قبل وجود داشت.")
            else:
                print(f"❌  خطا: '{name}' اضافه نشد. وضعیت: {response.status_code}, پیام: {response.text}")
                fail_count += 1
        except requests.exceptions.RequestException as e:
            print(f"❌  خطای اتصال برای '{name}': {e}")
            fail_count += 1

    print("-" * 50)
    print(f"✅ عملیات با {success_count} موفقیت و {fail_count} خطا به پایان رسید.")

if __name__ == "__main__":
    add_sources()