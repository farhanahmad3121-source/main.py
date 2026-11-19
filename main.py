import os
import re
import time
import random
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Amazon 50-Keyword Loot Bot (10m Loop + Heartbeat) Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

MIN_DISCOUNT = 90          # 90% या उससे ज़्यादा ऑफ
MAX_PRICE = 100            # ₹100 या उससे कम
LOOP_DELAY = 600           # हर 10 मिनट (600 सेकंड) में दोबारा सर्च

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/604.1",
]

# 50 काम के कीवर्ड्स (बेल्ट, जूते, टी-शर्ट/टीसल, कपड़े और एक्सेसरीज़)
KEYWORDS = [
    "mens tshirts", "tshirt", "polo tshirt", "oversized tshirt", "mens shirts",
    "formal shirt", "casual shirt", "joggers for men", "track pants for men", "mens jeans",
    "mens shorts", "hoodies for men", "sweatshirts for men", "mens jackets", "kurta for men",
    "mens ethnic wear", "boxers for men", "briefs for men", "mens vest", "compression tshirt",
    "shoes for men", "running shoes men", "casual shoes men", "sneakers for men", "loafers men",
    "sandals for men", "slippers for men", "flip flops men", "socks for men", "ankle socks",
    "belts for men", "leather belt men", "wallets for men", "caps for men", "beanie cap",
    "sunglasses for men", "womens clothing", "womens tops", "womens tshirts", "kurtis for women",
    "leggings for women", "womens jeans", "womens joggers", "womens hoodies", "womens jackets",
    "dresses for women", "shoes for women", "running shoes women", "casual shoes women", "sneakers women",
    "heels for women", "sandals for women", "slippers women", "handbags for women", "sling bags women"
]

seen_deals = set()

def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Error] BOT_TOKEN या CHAT_ID सेट नहीं है।")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "disable_web_page_preview": False},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[Telegram Error]: {r.text}")
    except Exception as e:
        print(f"[Telegram Exception]: {e}")

def extract_price_and_discount(text: str):
    prices = []
    for p in re.findall(r"₹\s*([\d,]+)", text):
        try:
            prices.append(int(p.replace(",", "")))
        except ValueError:
            pass

    discounts = []
    for d in re.findall(r"(\d{1,3})\s*%\s*off", text, flags=re.IGNORECASE):
        try:
            discounts.append(int(d))
        except ValueError:
            pass

    min_price = min(prices) if prices else None
    max_discount = max(discounts) if discounts else 0
    return min_price, max_discount

def has_free_delivery(text: str) -> bool:
    t = text.lower()
    return ("free delivery" in t) or ("free shipping" in t)

def scan_once():
    status_200 = 0
    status_err = 0
    deals_sent = 0

    for kw in KEYWORDS:
        query = kw.strip().replace(" ", "+")
        base_url = f"https://www.amazon.in/s?k={query}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.amazon.in/",
        }
        try:
            resp = requests.get(base_url, headers=headers, timeout=12)
            code = resp.status_code

            if code != 200:
                status_err += 1
                print(f"[Status {code}] {kw}")
                time.sleep(random.uniform(2.0, 4.0))
                continue

            status_200 += 1
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div[data-component-type='s-search-result']")

            for item in items:
                text = item.get_text(" ", strip=True)
                if not text:
                    continue

                price, discount = extract_price_and_discount(text)
                free_del = has_free_delivery(text)

                is_valid = (
                    (discount >= MIN_DISCOUNT)
                    and (price is not None)
                    and (0 < price <= MAX_PRICE)
                    and free_del
                )
                if not is_valid:
                    continue

                title_el = item.select_one("h2 span")
                title = title_el.get_text(" ", strip=True) if title_el else text[:100]

                link_el = item.select_one("h2 a") or item.find("a", href=True)
                href = link_el["href"].strip() if link_el and link_el.has_attr("href") else ""
                if href.startswith("/"):
                    link = "https://www.amazon.in" + href.split("?")[0]
                elif href.startswith("http"):
                    link = href.split("?")[0]
                else:
                    link = base_url

                sig = f"{link.lower()}|{title.lower()[:70]}"
                if sig in seen_deals:
                    continue
                seen_deals.add(sig)

                msg = (
                    f"👕👟 TRIPLE LOOT (90%+ OFF | <=₹100 | FREE DELIVERY)\n\n"
                    f"🔍 Keyword: {kw}\n"
                    f"📦 {title[:160]}\n"
                    f"💰 Price: ₹{price} | 🏷️ Discount: {discount}% | 🚚 Free Delivery: Yes\n"
                    f"🔗 {link}"
                )
                send_telegram(msg)
                deals_sent += 1
                time.sleep(0.4)

        except Exception as e:
            status_err += 1
            print(f"[Error {kw}]: {e}")

        time.sleep(random.uniform(2.0, 4.0))

    # हर 10 मिनट वाले रन के आखिर में Telegram पर स्टेटस हार्टबीट भेजेगा
    send_telegram(
        f"✅ Bot Alive (10m Cycle Done)\n"
        f"• Keywords Checked: {len(KEYWORDS)}\n"
        f"• 200 OK Pages: {status_200} | Non-200/Errors: {status_err}\n"
        f"• New Loot Alerts Sent: {deals_sent}"
    )

def background_worker():
    print("🚀 Render 50-Keyword Loot Bot Started (10m Loop + Heartbeat)...")
    while True:
        scan_once()
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    run_flask()
