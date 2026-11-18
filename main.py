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
    return "Multi-Device Rotating Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 5   
MAX_PRICE = 100      
MIN_DISCOUNT = 90    

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

# 15 अलग-अलग ब्राउज़र और मोबाइल डिवाइसेस के User-Agents की लिस्ट (ताकि हर बार नया डिवाइस बनकर रिक्वेस्ट जाए)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/124.0.6367.83 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.2478.51",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/115.0.5790.166 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.94 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 11; Redmi Note 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
]

# 8 टॉप डील वेबसाइट्स
SITES = {
    "DesiDimeNew": "https://www.desidime.com/new",
    "IndiaFreeStuff": "https://www.indiafreestuff.in/",
    "DealsMagnet": "https://www.dealsmagnet.com/",
    "FreeKaaMaal": "https://freekaamaal.com/",
    "Smartprix": "https://www.smartprix.com/deals",
    "PriceHistory": "https://pricehistory.app/",
    "MySmartPrice": "https://www.mysmartprice.com/deals/",
    "DealNTech": "https://dealntech.com/"
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
    matched_price = 999999

    if "₹0" in clean_text or "rs.0" in clean_text.lower() or "100% cashback" in clean_text.lower():
        return True, "🎁 RS.0 / FREE 100% CASHBACK LOOT!"

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

    if matched_discount >= MIN_DISCOUNT:
        return True, f"🔥 {matched_discount}% OFF MEGA LOOT!"

    if (0 <= matched_price <= MAX_PRICE) and (matched_discount >= MIN_DISCOUNT):
        return True, f"💥 Rs.{matched_price} & {matched_discount}% OFF LOOT!"

    return False, ""

def scrape_site(name, url):
    try:
        # हर बार लिस्ट में से कोई एक रैंडम यूजर-एजेंट चुनेगा ताकि वेबसाइट को नया डिवाइस लगे
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all(['div', 'article', 'li', 'box'])[:15]
        
        for card in cards:
            card_text = card.get_text(" ", strip=True)
            if len(card_text) < 20 or len(card_text) > 500:
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
    print("🚀 Rotating Device Multi-Site Loot Bot Started...")
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
