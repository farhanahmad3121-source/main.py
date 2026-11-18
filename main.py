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
    return "Multi-Feed Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 60  
MAX_PRICE = 100      
MIN_DISCOUNT = 90    

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

# असली ब्राउज़र जैसा यूजर-एजेंट
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

# सभी काम करने वाली वेबसाइट्स के लिंक्स और फीड्स
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
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=10)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def parse_and_check_deal(text):
    clean_text = re.sub(r'\s+', ' ', text)
    
    matched_discount = 0
    matched_price = 999999

    # 0. फ्री या ₹0 / 100% कैशबैक चेक
    if "₹0" in clean_text or "rs.0" in clean_text.lower() or "100% cashback" in clean_text.lower():
        return True, "🎁 RS.0 / FREE 100% CASHBACK LOOT!"

    # 1. डिस्काउंट ढूँढना (90%, 95% या (90% off) आदि)
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

    # 2. कीमत ढूँढना
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

    # --- सख्त नियम (Strict Rules) ---
    if matched_discount >= MIN_DISCOUNT:
        return True, f"🔥 {matched_discount}% OFF MEGA LOOT!"

    if (0 <= matched_price <= MAX_PRICE) and (matched_discount >= MIN_DISCOUNT):
        return True, f"💥 Rs.{matched_price} & {matched_discount}% OFF LOOT!"

    return False, ""

def scrape_site(name, url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[{name}] Skipped, Status: {resp.status_code}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # हर संभव टैग से डील कार्ड्स उठाएं
        cards = soup.find_all(['div', 'article', 'li', 'tr', 'box', 'section', 'a'])
        
        for card in cards:
            card_text = card.get_text(" ", strip=True)
            
            if len(card_text) < 25 or len(card_text) > 700:
                continue

            link_tag = card if card.name == 'a' else card.find('a', href=True)
            if not link_tag or not link_tag.has_attr('href'):
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
    print("🚀 All-Site Loot Bot Started...")
    while True:
        for site_name, site_url in SITES.items():
            scrape_site(site_name, site_url)
            time.sleep(2)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    tracker_loop()
