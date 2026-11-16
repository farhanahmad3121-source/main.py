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
import telebot

# ==========================================
# 1. CONFIGURATION & TELEGRAM INITIALIZATION
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
current_query = "Initializing..."

# ==========================================
# 2. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Loot Deal Scraper Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 3. TELEGRAM /START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global current_query
    status_msg = (
        "🔥 **Loot Scraper Bot is Active & Hunting!**\n\n"
        f"🔍 **Currently Checking:** `{current_query}`\n\n"
        "⚡ **Target:** 70%+ OFF OR Under ₹500 Testing Deals!\n"
        "सारे सिस्टम चालू हैं भाई, अब चेक करते हैं क्या माल मिलता है। 🚀"
    )
    bot.reply_to(message, status_msg, parse_mode="Markdown")

def send_alert_to_telegram(error_message):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": f"🚨 **BOT ALERT** 🚨\n\n{error_message}"}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Alert Error: {e}")

# ==========================================
# 4. USER AGENTS & SEARCH QUERIES
# ==========================================
CHROME_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/125.0.6422.80 Mobile/15E148 Safari/604.1"
]

CLOTHING_NAMES = [
    "mens sports shoes", "casual shoes for men", "running shoes under 500", "mens walking shoes", 
    "canvas shoes for men", "gym shoes men lightweight", "mens sandals and floaters", "mens slippers flip flops", 
    "mens cotton t shirt combo", "mens polo collar t shirt", "oversized graphic t shirt men", "gym vest for men pack of 3", 
    "mens track pants cotton", "mens lower gym running", "stretchable jeans for men", "mens casual cotton shirt",
    "mens analog watch leather strap", "digital sports watch for men", "smartwatch bluetooth calling", 
    "uv protected sunglasses men", "wayfarer stylish sunglasses", "mens leather wallet genuine", "slim card holder wallet",
    "silicone mobile back cover", "transparent clear case phone", "armor shockproof back cover", "tempered glass screen protector", 
    "bluetooth wireless neckband", "tws wireless earbuds bluetooth", "wired earphones with mic", "type c fast charging cable", 
    "stainless steel water bottle 1l", "insulated flask water bottle", "lunch box for office insulated", 
    "plastic container set for kitchen", "airtight food storage jars", "spice box masala dabba steel", "wall clock for home decor",
    "wall plug and screw set plastic", "hammer small iron with wooden handle", "measuring tape flexible 5m", "torch light led small torch"
]

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

def run_scraper():
    global current_query
    print(f"🔥 Loot Deal Bot Active with {len(CLOTHING_NAMES)} Queries...")
    
    while True:
        queries_pool = CLOTHING_NAMES.copy()
        random.shuffle(queries_pool)
        session, headers = get_fresh_session()

        for query in queries_pool:
            current_query = query
            url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
            print(f"\n🔍 Searching Query: {query}")

            try:
                response = session.get(url, headers=headers, impersonate="chrome", timeout=20)
                print(f"📡 Response Status Code: {response.status_code}")

                if response.status_code == 503:
                    print("❌ 503 Blocked! Sending Telegram Alert...")
                    send_alert_to_telegram(f"🚨 Amazon ने IP ब्लॉक कर दी है (503 Error)!\n🔍 आखिरी चेक किया गया आइटम: {query}\nबॉट नया सेशन ले रहा है...")
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

                if len(valid_products) == 0:
                    print("⚠️ 0 Products Found (Soft Block).")
                    time.sleep(5)
                    continue

                for product in valid_products:
                    full_text = product.get_text()
                    
                    price_tag = product.select_one("span.a-price span.a-offscreen") or product.select_one("span.a-price-whole")
                    actual_price = None

                    if price_tag:
                        price_str = price_tag.get_text(strip=True).replace("₹", "").replace(",", "")
                        price_match = re.search(r"\d+", price_str)
                        if price_match:
                            actual_price = int(price_match.group())

                    match = re.search(r"(\d+)%\s+off", full_text, flags=re.IGNORECASE)
                    discount_val = int(match.group(1)) if match else 0

                    is_under_500 = actual_price is not None and actual_price <= 500
                    is_good_discount = discount_val >= 70

                    if is_under_500 or is_good_discount:
                        title_tag = product.select_one("h2 a span") or product.select_one("h2 span") or product.select_one("span.a-text-normal")
                        title = title_tag.get_text(strip=True) if title_tag else "Item"

                        asin_val = product.get("data-asin")
                        link = f"https://www.amazon.in/dp/{asin_val}"
                        price_display = f"₹{actual_price}" if actual_price is not None else "Check Link"
                        
                        if is_under_500 and is_good_discount:
                            deal_type = f"🔥 UNDER-₹500 & {discount_val}% OFF DEAL!"
                        elif is_under_500:
                            deal_type = "🔥 UNDER-₹500 BUDGET DEAL!"
                        else:
                            deal_type = f"💥 MASSIVE {discount_val}% OFF DEAL!"

                        msg = (
                            f"{deal_type}\n\n"
                            f"🛍 Product: {title}\n"
                            f"💰 Price: {price_display}\n"
                            f"📉 Discount: {discount_val}%\n"
                            f"🔗 Link: {link}"
                        )

                        print(f"✅ DEAL MATCHED! Sending to Telegram...")
                        urllib.request.urlopen(urllib.request.Request(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            data=urllib.parse.urlencode({"chat_id": CHAT_ID, "text": msg}).encode("utf-8"),
                            method="POST"
                        ), timeout=10)
                        time.sleep(0.5)

            except Exception as e:
                print(f"⚠️ Exception Error: {e}")

            time.sleep(random.uniform(10.0, 20.0))

# ==========================================
# 5. MAIN EXECUTION (Flask + Scraper + Bot)
# ==========================================
if __name__ == "__main__":
    # Flask को बैकग्राउंड में चालू करेंगे
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # स्क्रैपर को बैकग्राउंड में चालू करेंगे
    scraper_thread = threading.Thread(target=run_scraper)
    scraper_thread.daemon = True
    scraper_thread.start()

    print("Bot is starting Telegram Polling...")
    # मुख्य थ्रेड पर टेलीग्राम पोलिंग चलेगी ताकि ऐप बंद न हो
    bot.infinity_polling(none_stop=True)
