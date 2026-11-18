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
    return "Direct Amazon Deals Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
CHECK_INTERVAL = 5   

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
]

# अब हम सीधे ऐसी वेबसाइट्स या पेजों को लेंगे जो डायरेक्ट अमेज़न/फ्लिपकार्ट के लिंक्स देते हैं
TARGET_URL = "https://www.dealsmagnet.com/"

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=8)
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def scrape_direct_deals():
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        resp = requests.get(TARGET_URL, headers=headers, timeout=12)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all(['div', 'article', 'li', 'box'])
        
        for card in cards:
            card_text = card.get_text(" ", strip=True)
            
            if len(card_text) < 25 or len(card_text) > 800:
                continue

            # चेक करें कि क्या यह अमेज़न या फ्लिपकार्ट से जुड़ी डील है
            if "amazon" not in card_text.lower() and "flipkart" not in card_text.lower():
                continue

            link_tag = card.find('a', href=True)
            if not link_tag:
                continue
            
            link = link_tag['href']
            if not link.startswith("http"):
                link = TARGET_URL.rstrip("/") + "/" + link.lstrip("/")

            deal_signature = card_text[:50]

            if deal_signature not in seen_deals:
                seen_deals.add(deal_signature)
                alert_msg = f"🔥 DIRECT STORE DEAL\n\n📦 {card_text[:180]}...\n🔗 {link}"
                print(alert_msg)
                send_telegram(alert_msg)

    except Exception as e:
        print(f"[Scraper Error]: {e}")

def tracker_loop():
    print("🚀 Direct Store Link Bot Started...")
    while True:
        scrape_direct_deals()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    tracker_loop()
