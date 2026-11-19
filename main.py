import time
import re
import os
import random
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Strict 90% Loot Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- RENDER ENVIRONMENT VARIABLES CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

CHECK_INTERVAL = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
]

TARGET_URLS = [
    "https://www.desidime.com/new",
    "https://www.indiafreestuff.in/",
    "https://freekaamaal.com/",
    "https://pricehistory.app/deals",
    "https://slickdeals.net/",
    "https://pricehistoryapp.com/",
    "https://www.smartprix.com/deals",
    "https://www.dealsmagnet.com/"
]

seen_deals = set()

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Error]: Telegram Bot Token or Chat ID not found!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, data=payload, timeout=8)
        if response.status_code != 200:
            print(f"[Telegram API Error]: {response.text}")
        else:
            print("[Telegram]: Alert sent successfully!")
    except Exception as e:
        print(f"[Telegram Error]: {e}")

def scrape_all_sources():
    for url in TARGET_URLS:
        try:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            }

            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[Status {resp.status_code}]: {url}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all(['div', 'article', 'li', 'box', 'tr'])

            for card in cards:
                card_text = card.get_text(" ", strip=True)

                if len(card_text) < 25 or len(card_text) > 1500:
                    continue

                if not any(k in card_text.lower() for k in ["get deal", "buy now", "₹", "$", "deal"]):
                    continue

                if any(bad in card_text.lower() for bad in ["telegram channel", "whatsapp group", "chrome extension", "android app", "ios app"]):
                    continue

                is_loot = False

                # 1. 90% से 100% तक डिस्काउंट चेक
                match_pct = re.findall(r'(\d{2,3})\s*%', card_text)
                for p_str in match_pct:
                    try:
                        p_val = int(p_str)
                        if 90 <= p_val <= 100:
                            is_loot = True
                            break
                    except ValueError:
                        pass

                # 2. ₹100 के अंदर की कीमत चेक
                if not is_loot:
                    inr_prices = re.findall(r'₹\s*([\d,]+)', card_text)
                    if inr_prices:
                        try:
                            cur_price = int(inr_prices[0].replace(',', ''))
                            if 0 <= cur_price <= 100:
                                is_loot = True
                        except ValueError:
                            pass

                if not is_loot:
                    continue

                link_tag = card.find('a', href=True)
                if not link_tag:
                    continue

                link = link_tag['href']
                if not link or link == "#" or link == "/":
                    link = url
                elif not link.startswith("http"):
                    base_domain = "/".join(url.split("/")[:3])
                    link = base_domain + ("/" if not link.startswith("/") else "") + link

                deal_signature = card_text[:60]

                if deal_signature not in seen_deals:
                    seen_deals.add(deal_signature)
                    alert_msg = f"🚨 🔥 STRICT 90%+ OR UNDER ₹100 LOOT\n\n📦 {card_text[:220]}...\n🔗 {link}"
                    print(alert_msg)
                    send_telegram(alert_msg)

        except Exception as e:
            print(f"[Scraper Error for {url}]: {e}")

def tracker_loop():
    print("🚀 Strict 90% Loot Bot Started...")
    while True:
        scrape_all_sources()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    tracker_loop()
