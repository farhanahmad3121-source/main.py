import time
import re
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Loot Tracker Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- SCRAPER CONFIGURATION ---
CHECK_INTERVAL = 60  
MAX_PRICE = 50       # ₹1 से ₹50 तक का कोई भी सामान
MIN_DISCOUNT = 90    # सिर्फ 90% या उससे ऊपर का डिस्काउंट

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

SITES = {
    "DesiDime": "https://www.desidime.com/new",
    "IndiaFreeStuff": "https://www.indiafreestuff.in/",
    "FreeKaaMaal": "https://freekaamaal.com/",
    "DealsMagnet": "https://www.dealsmagnet.com/",
    "PriceHistory": "https://pricehistory.app/deals",
    "Smartprix": "https://www.smartprix.com/deals",
}

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Warning] Telegram Token या Chat ID सेट नहीं है!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=10)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def is_loot_deal(title, price_text=""):
    text = f"{title} {price_text}".lower()
    
    # 1. कीमत चेक (₹1 से ₹50 तक)
    price_match = re.search(r'(?:₹|rs\.?)\s*(\d+)', text)
    if price_match:
        price = int(price_match.group(1))
        if 0 < price <= MAX_PRICE:
            return True 

    # 2. डिस्काउंट चेक (90% या उससे ऊपर)
    disc_match = re.search(r'(\d{2,3})\s*%\s*off', text)
    if disc_match:
        discount_val = int(disc_match.group(1))
        if discount_val >= MIN_DISCOUNT:
            return True 

    # 3. कीवर्ड्स
    loot_keywords = ["loot", "freebie", "100% off", "99% off", "95% off", "90% off", "rs.1", "rs 1", "₹1", "₹9", "₹10"]
    if any(kw in text for kw in loot_keywords):
        return True

    return False

def scrape_site(name, url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        for a_tag in soup.find_all("a", href=True):
            title = a_tag.get_text(" ", strip=True)
            link = a_tag["href"]

            if len(title) < 15 or len(title) > 150:
                continue

            if not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")

            if link in seen_deals:
                continue

            if is_loot_deal(title):
                seen_deals.add(link)
                alert_msg = f"🔥 STRICT LOOT FOUND ({name}) 🔥\n\n📦 {title}\n🔗 {link}"
                print(alert_msg)
                send_telegram(alert_msg)

    except Exception as e:
        print(f"[{name}] Error: {e}")

def tracker_loop():
    print("🚀 Super Loot Filter Started on Render...")
    while True:
        for site_name, site_url in SITES.items():
            scrape_site(site_name, site_url)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    # Flask को बैकग्राउंड थ्रेड में चलाएंगे ताकि Render का पोर्ट बिजी न रहे
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # मुख्य स्क्रैपर लूप
    tracker_loop()
