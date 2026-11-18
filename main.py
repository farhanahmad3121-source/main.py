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
    return "PriceHistory All-Deals Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 5   # हर 5 सेकंड में सुपर-फास्ट चेकिंग

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
]

# अब सिर्फ और सिर्फ यही एक वेबसाइट रहेगी!
TARGET_URL = "https://pricehistory.app/deals"

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=8)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def scrape_pricehistory():
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        resp = requests.get(TARGET_URL, headers=headers, timeout=12)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # पेज के सभी डील्स वाले कार्ड्स को उठाएगा
        cards = soup.find_all(['div', 'article', 'li', 'box', 'tr', 'a'])[:30]
        
        for card in cards:
            card_text = card.get_text(" ", strip=True)
            if len(card_text) < 15 or len(card_text) > 800:
                continue

            link_tag = card if card.name == 'a' else card.find('a', href=True)
            if not link_tag or not link_tag.has_attr('href'):
                continue
            
            link = link_tag['href']
            if not link.startswith("http"):
                link = "https://pricehistory.app" + "/" + link.lstrip("/")

            # अगर यह डील पहले नहीं देखी है, तो बिना किसी डिस्काउंट कंडीशन के सीधा भेज दो!
            if link not in seen_deals:
                seen_deals.add(link)
                alert_msg = f"🔥 NEW DEAL (PriceHistory)\n\n📦 {card_text[:180]}...\n🔗 {link}"
                print(alert_msg)
                send_telegram(alert_msg)

    except Exception as e:
        print(f"[PriceHistory Error]: {e}")

def tracker_loop():
    print("🚀 PriceHistory All-Deals Bot Started...")
    while True:
        scrape_pricehistory()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    tracker_loop()
