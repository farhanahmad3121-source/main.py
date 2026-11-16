import os
import random
import re
import time
import urllib.parse
import urllib.request
import threading
from bs4 import BeautifulSoup
from curl_cffi import requests
from flask import Flask

# ==========================================
# 1. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Loot Deal Scraper Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. CONFIGURATION & USER AGENTS
# ==========================================
# रेंडर के Environment Variables से ऑटोमैटिक टोकन और चैट आईडी उठाएगा
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

CHROME_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; M2101K7AG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.5 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Redmi Note 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]

CLOTHING_NAMES = [
    "nike sports shoes men",
    "adidas originals sneakers",
    "puma motorsport shoes",
    "reebok classic sneakers",
    "skechers memory foam shoes",
    "asics gel running shoes",
    "under armour sports t shirt",
    "hrx by hrithik roshan shoes",
    "campus activewear shoes men",
    "sparx running sandals men",
    "bata official store shoes",
    "red tape casual leather shoes",
    "woodland waterproof boots",
    "crocs classic clogs unisex",
    "levis mens regular fit jeans",
    "wrangler denim jeans men",
    "lee cooper casual shirts",
    "pepe jeans london men",
    "u.s. polo assn cotton shirt",
    "allen solly formal trousers",
    "snitch oversized t shirt men",
    "bewakoof printed graphic t shirt",
    "souled store superhero t shirt",
    "fastrack stylish wrist watch",
    "titan neo analog watch men",
    "casio vintage gold watch",
    "fossil chronograph watch men",
    "boat smartwatch bluetooth",
    "fire-boltt smart watch call",
    "noise colorfit pulse watch",
    "wildcraft laptop backpack",
    "skybags trolley bag sale",
]

def send_to_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        print("❌ Telegram Token or Chat ID missing in environment variables!")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

def get_fresh_session():
    session = requests.Session()
    ua = random.choice(CHROME_USER_AGENTS)
    base_headers = {
        "Host": "www.amazon.in",
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        session.get("https://www.amazon.in/", headers=base_headers, impersonate="chrome", timeout=15)
        time.sleep(2)
    except Exception as e:
        print(f"⚠️ Session Refresh Notice: {e}")
    return session, base_headers

def run_bot():
    print(f"🔥 Loot Deal Bot Active with {len(CLOTHING_NAMES)} Queries (Randomized Search Order)...")
    
    while True:
        queries_pool = CLOTHING_NAMES.copy()
        random.shuffle(queries_pool)
        session, headers = get_fresh_session()

        for query in queries_pool:
            url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
            print(f"\n🔍 Searching Query: {query}")

            try:
                response = session.get(url, headers=headers, impersonate="chrome", timeout=20)
                print(f"📡 Response Status Code: {response.status_code}")

                if response.status_code == 503:
                    print("❌ 503 Blocked! Refreshing Session & Skipping to next...")
                    time.sleep(15)
                    session, headers = get_fresh_session()
                    continue

                if response.status_code != 200:
                    print(f"❌ Error Status: {response.status_code}")
                    time.sleep(5)
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                products = soup.select("[data-asin]")

                valid_products = []
                seen_asins = set()
                for p in products:
                    asin = p.get("data-asin")
                    if asin and len(asin) == 10 and asin not in seen_asins:
                        seen_asins.add(asin)
                        valid_products.append(p)

                print(f"📦 Total Valid Products Found on Page: {len(valid_products)}")

                if len(valid_products) == 0:
                    print("⚠️ 0 Products Found (Soft Block). Refreshing Session for next query...")
                    session, headers = get_fresh_session()
                    time.sleep(5)
                    continue

                for product in valid_products:
                    full_text = product.get_text()
                    match = re.search(r"(\d+)%\s+off", full_text, flags=re.IGNORECASE)

                    if match:
                        discount_val = int(match.group(1))
                        price_tag = product.select_one("span.a-price span.a-offscreen") or product.select_one("span.a-price-whole")
                        actual_price = None

                        if price_tag:
                            price_str = price_tag.get_text(strip=True).replace("₹", "").replace(",", "")
                            price_match = re.search(r"\d+", price_str)
                            if price_match:
                                actual_price = int(price_match.group())

                        is_under_100 = actual_price is not None and actual_price <= 100
                        is_mega_discount = discount_val >= 90

                        if is_under_100 or is_mega_discount:
                            title_tag = product.select_one("h2 a span") or product.select_one("h2 span") or product.select_one("span.a-text-normal")
                            title = title_tag.get_text(strip=True) if title_tag else "Clothing Item"

                            is_free_delivery = "FREE Delivery" in full_text or "Free Delivery" in full_text
                            delivery_status = "✅ Free Delivery" if is_free_delivery else "📦 Standard"

                            asin_val = product.get("data-asin")
                            link = f"https://www.amazon.in/dp/{asin_val}"

                            price_display = f"₹{actual_price}" if actual_price is not None else "Check Link"
                            deal_type = "🔥 REAL UNDER-₹100 LOOT!" if is_under_100 else "💥 BRANDED 90%+ OFF LOOT!"

                            msg = (
                                f"{deal_type} ({discount_val}% OFF)\n\n"
                                f"🛍 Product: {title}\n"
                                f"💰 Price: {price_display}\n"
                                f"📉 Discount: {discount_val}%\n"
                                f"🚚 Delivery: {delivery_status}\n"
                                f"🔗 Link: {link}"
                            )

                            print(f"✅ DEAL MATCHED! [{deal_type}] {discount_val}% off | Price: {price_display} -> {title[:25]}...")
                            send_to_telegram(msg)
                            time.sleep(0.5)

            except Exception as e:
                print(f"⚠️ Exception Error: {e}")

            time.sleep(random.uniform(8.0, 15.0))

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    keep_alive()  # Flask सर्वर को बैकग्राउंड में चालू रखेगा
    run_bot()     # लूट स्क्रैपर बॉट को चलाएगा
