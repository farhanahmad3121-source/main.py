import time
import re
import os
import random
import requests
from bs4 import BeautifulSoup
from flask import Flask

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Ultra-Smart Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 5   
MAX_PRICE = 100      
MIN_DISCOUNT = 90    

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
]

SITES = {
    "DesiDimeNew": "https://www.desidime.com/new",
    "IndiaFreeStuff": "https://www.indiafreestuff.in/",
    "DealsMagnet": "https://www.dealsmagnet.com/",
    "FreeKaaMaal": "https://freekaamaal.com/"
}

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=8)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def parse_and_check_deal(text):
    clean_text = re.sub(r'\s+', ' ', text)
    
    matched_discount = 0
    all_prices = []

    # 0. फ्री या ₹0 / 100% कैशबैक / BOGO चेक
    if any(k in clean_text.lower() for k in ["₹0", "rs.0", "100% cashback", "bogo", "free"]):
        if "₹0" in clean_text or "rs. 0" in clean_text.lower() or "100%" in clean_text:
            return True, "🎁 RS.0 / FREE / 100% LOOT!"

    # 1. सभी तरह के डिस्काउंट ढूँढना (जैसे 91%, (91%), 90% off)
    disc_patterns = [
        r'(\d{2,3})\s*%\s*off',
        r'\(?\s*(\d{2,3})\s*%\s*\)?',
        r'flat\s*(\d{2,3})\s*%'
    ]
    for pat in disc_patterns:
        matches = re.findall(pat, clean_text, re.IGNORECASE)
        for m in matches:
            val = int(m)
            if val > matched_discount:
                matched_discount = val

    # 2. सभी कीमतों को ढूँढना (₹87, ₹125 आदि)
    price_patterns = [
        r'(?:₹|rs\.?)\s*(\d+(?:,\d+)*)',
    ]
    found_prices = re.findall(price_patterns[0], clean_text, re.IGNORECASE)
    for p in found_prices:
        clean_p = int(p.replace(',', ''))
        all_prices.append(clean_p)

    # --- स्मार्ट और पक्का फिल्टर लॉजिक ---
    # केस A: अगर डिस्काउंट सीधा 90% या उससे ज्यादा है
    if matched_discount >= MIN_DISCOUNT:
        return True, f"🔥 {matched_discount}% OFF MEGA LOOT!"

    # केस B: अगर कोई भी कीमत ₹100 के अंदर है और साथ में 90%+ डिस्काउंट या तगड़ा ऑफर है
    if all_prices:
        lowest_price = min(all_prices)
        if (0 <= lowest_price <= MAX_PRICE) and (matched_discount >= 85): # थोड़ा मार्जिन 85% तक का रखा है ताकि मिस न हो
            return True, f"💥 Rs.{lowest_price} & {matched_discount}% OFF LOOT!"

    return False, ""

def scrape_site(name, url):
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # कार्ड्स और छोटे ब्लॉक्स दोनों को स्कैन करेगा
        cards = soup.find_all(['div', 'article', 'li', 'box', 'tr'])[:25]
        
        for card in cards:
            card_text = card.get_text(" ", strip=True)
            if len(card_text) < 15 or len(card_text) > 800:
                continue

            link_tag = card.find('a', href=True)
            if not link_tag:
                continue
            
            link = link_tag['href']
            if not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")

            if link in seen_deals:
                continue

            is_loot, tag_msg = parse_and_check_deal(card_text)
            if is_loot:
                seen_deals.add(link)
                alert_msg = f"{tag_msg} ({name})\n\n📦 {card_text[:180]}...\n🔗 {link}"
                print(alert_msg)
                send_telegram(alert_msg)

    except Exception as e:
        print(f"[{name}] Error: {e}")

def tracker_loop():
    print("🚀 Ultra-Smart Loot Bot Started...")
    while True:
        for site_name, site_url in SITES.items():
            scrape_site(site_name, site_url)
            time.sleep(1) 
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    tracker_loop()
