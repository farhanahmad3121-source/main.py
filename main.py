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
    return "Strict 90%+ Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 60  
MAX_PRICE = 100      # सामान ₹100 के अंदर होना चाहिए
MIN_DISCOUNT = 90    # और डिस्काउंट कम्‍पल्‍सरी 90% या उससे ऊपर होना चाहिए!

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

SITES = {
    "IndiaFreeStuff": "https://www.indiafreestuff.in/",
    "FreeKaaMaal": "https://freekaamaal.com/",
    "DealsMagnet": "https://www.dealsmagnet.com/",
    "Smartprix": "https://www.smartprix.com/deals",
    "DesiDimeNew": "https://www.desidime.com/new",
}

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=10)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def parse_and_check_deal(text):
    clean_text = re.sub(r'\s+', ' ', text)
    
    matched_discount = 0
    matched_price = 999999

    # 0. अगर बिल्कुल फ्री या ₹0 वाला है (100% कैशबैक / Free)
    if "₹0" in clean_text or "rs.0" in clean_text.lower() or "100% cashback" in clean_text.lower():
        return True, "🎁 RS.0 / FREE 100% CASHBACK LOOT!"

    # 1. असली डिस्काउंट ढूँढना (जैसे 90%, 95%, 99% off)
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

    # 2. कीमत ढूँढना (जैसे ₹10, ₹50, ₹99)
    price_patterns = [
        r'(?:₹|rs\.?)\s*(\d+(?:,\d+)*)',
    ]
    all_prices = []
    for pat in price_patterns:
        found = re.findall(pat, clean_text, re.IGNORECASE)
        for p in found:
            clean_p = int(p.replace(',', ''))
            all_prices.append(clean_p)

    if all_prices:
        matched_price = all_prices[0]

    # --- नया और सख्त नियम (Strict Rule) ---
    # नियम 1: डिस्काउंट कम से कम 90% या उससे ऊपर होना ही चाहिए!
    if matched_discount >= MIN_DISCOUNT:
        return True, f"🔥 {matched_discount}% OFF STRICT LOOT!"

    # नियम 2: अगर कीमत ₹100 के अंदर है, तो साथ में उस पर 90% या उससे ऊपर का डिस्काउंट होना जरूरी है (ताकि कम डिस्काउंट वाले सस्ते कवर्स या फालतू सामान छट जाएं)
    if (0 <= matched_price <= MAX_PRICE) and (matched_discount >= MIN_DISCOUNT):
        return True, f"💥 Rs.{matched_price} & {matched_discount}% OFF LOOT!"

    return False, ""

def scrape_site(name, url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        for card in soup.find_all(['div', 'article', 'li', 'tr', 'box']):
            card_text = card.get_text(" ", strip=True)
            
            if len(card_text) < 20 or len(card_text) > 600:
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
    print("🚀 Strict 90%+ Filter Loot Bot Started...")
    while True:
        for site_name, site_url in SITES.items():
            scrape_site(site_name, site_url)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    tracker_loop()
