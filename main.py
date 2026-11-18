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
    return "Visual-Matched Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 60  
MAX_PRICE = 100      # केवल ₹100 या उससे कम का सामान
MIN_DISCOUNT = 90    # केवल 90% या उससे ऊपर का डिस्काउंट (90%+)

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
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=10)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def parse_and_check_deal(text):
    # टेक्स्ट को साफ करें
    clean_text = re.sub(r'\s+', ' ', text)
    
    matched_discount = 0
    matched_price = 999999

    # 1. स्क्रीनशॉट के हिसाब से डिस्काउंट ढूँढना (जैसे "91%", "90% off", "(91%)")
    disc_patterns = [
        r'(\d{2,3})\s*%\s*off',
        r'\(?\s*(\d{2,3})\s*%\s*\)?',
        r'flat\s*(\d{2,3})\s*%'
    ]
    for pat in disc_patterns:
        match = re.search(pat, clean_text, re.IGNORECASE)
        if match:
            val = int(match.group(1))
            if val > matched_discount:
                matched_discount = val

    # 2. स्क्रीनशॉट के हिसाब से ऑफर प्राइस ढूँढना (जैसे "₹189", "Rs. 9", "₹ 49")
    price_patterns = [
        r'(?:₹|rs\.?)\s*(\d+(?:,\d+)*)',
    ]
    
    # पहली कीमत आमतौर पर Current/Offer Price होती है (जैसा स्क्रीनशॉट में ₹158, ₹189, ₹9 दिया है)
    all_prices = []
    for pat in price_patterns:
        found = re.findall(pat, clean_text, re.IGNORECASE)
        for p in found:
            clean_p = int(p.replace(',', ''))
            all_prices.append(clean_p)

    if all_prices:
        # सबसे पहली मिलने वाली कीमत ही ऑफर प्राइस होती है
        matched_price = all_prices[0]

    # --- फाइनल स्ट्रिक्ट फिल्टर लॉजिक ---
    # शर्त A: डिस्काउंट 90% या उससे ज्यादा हो
    if matched_discount >= MIN_DISCOUNT:
        return True, f"🔥 {matched_discount}% OFF MEGA LOOT!"

    # शर्त B: कीमत ₹100 या उससे कम हो (और 0 न हो)
    if 0 < matched_price <= MAX_PRICE:
        return True, f"💥 Rs.{matched_price} CHEAP LOOT!"

    return False, ""

def scrape_site(name, url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # हर एक प्रोडक्ट/डील कार्ड को टारगेट करें
        for card in soup.find_all(['div', 'article', 'li', 'tr']):
            card_text = card.get_text(" ", strip=True)
            
            # फालतू छोटे-मोटे टेक्स्ट ब्लॉक छोड़ दें
            if len(card_text) < 30 or len(card_text) > 500:
                continue

            # डील का लिंक ढूँढें
            link_tag = card.find('a', href=True)
            if not link_tag:
                continue
            
            link = link_tag['href']
            if not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")

            if link in seen_deals:
                continue

            # चेक करें कि क्या यह आपकी शर्तों पर खरा उतरता है
            is_loot, tag_msg = parse_and_check_deal(card_text)
            if is_loot:
                seen_deals.add(link)
                alert_msg = f"{tag_msg} ({name})\n\n📦 {card_text[:180]}...\n🔗 {link}"
                print(alert_msg)
                send_telegram(alert_msg)

    except Exception as e:
        print(f"[{name}] Error: {e}")

def tracker_loop():
    print("🚀 Visual-Matched Loot Bot Started...")
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
