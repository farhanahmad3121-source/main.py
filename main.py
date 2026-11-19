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
    return "Amazon Fashion Loot Bot (70%+ Off / Under ₹400) Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

MIN_DISCOUNT = 70   # 70% या उससे ज़्यादा ऑफ
MAX_PRICE = 400     # ₹400 से कम कीमत
LOOP_DELAY = 60     # हर साइकिल के बीच गैप (सेकंड में)
STATUS_REPORT_INTERVAL = 1800  # हर 30 मिनट में एक बार स्टेटस समरी (स्पैम रोकने के लिए)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/604.1",
]

AMAZON_URLS = [
    "https://www.amazon.in/s?k=mens+tshirts",
    "https://www.amazon.in/s?k=womens+clothing",
    "https://www.amazon.in/s?k=shoes+for+men",
    "https://www.amazon.in/s?k=shoes+for+women",
]

seen_deals = set()
last_status_by_url = {}
last_summary_time = 0

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

def scan_once():
    global last_summary_time
    cycle_statuses = []

    for base_url in AMAZON_URLS:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.amazon.in/",
        }
        try:
            resp = requests.get(base_url, headers=headers, timeout=12)
            code = resp.status_code
            cycle_statuses.append(f"{base_url.split('=')[-1]}: {code}")

            # अगर 200 नहीं है (जैसे 403, 503), तो तुरंत Telegram पर बताओ
            if code != 200:
                prev_code = last_status_by_url.get(base_url)
                if prev_code != code:
                    last_status_by_url[base_url] = code
                    send_telegram(
                        f"⚠️ HTTP Status Alert: {code}\n"
                        f"🔗 {base_url}\n"
                        f"📌 Amazon ने 200 के बजाय {code} रिस्पॉन्स दिया है।"
                    )
                print(f"[Status {code}]: {base_url}")
                time.sleep(random.uniform(3.0, 6.0))
                continue

            # अगर पहले एरर आ रहा था और अब 200 हो गया है, तो अपडेट दें
            if last_status_by_url.get(base_url) not in (None, 200):
                send_telegram(f"✅ Recovered: Status 200 OK\n🔗 {base_url}")
            last_status_by_url[base_url] = 200

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div[data-component-type='s-search-result']")

            for item in items:
                text = item.get_text(" ", strip=True)
                if not text:
                    continue

                price, discount = extract_price_and_discount(text)
                is_70_plus_off = discount >= MIN_DISCOUNT
                is_under_400 = (price is not None) and (0 < price < MAX_PRICE)

                if not (is_70_plus_off or is_under_400):
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

                price_str = f"₹{price}" if price is not None else "N/A"
                msg = (
                    f"👕👟 AMAZON FASHION LOOT (70%+ OFF / <₹400)\n\n"
                    f"📦 {title[:160]}\n"
                    f"💰 Price: {price_str} | 🏷️ Discount: {discount}%\n"
                    f"🔗 {link}"
                )
                send_telegram(msg)
                time.sleep(0.5)

        except Exception as e:
            err_msg = f"❌ Request Error: {str(e)[:140]}\n🔗 {base_url}"
            print(err_msg)
            send_telegram(err_msg)

        time.sleep(random.uniform(3.0, 6.0))

    now = time.time()
    if cycle_statuses and (now - last_summary_time >= STATUS_REPORT_INTERVAL):
        last_summary_time = now
        send_telegram("📊 Status Summary (200 / 403 / 503 Check):\n" + "\n".join(cycle_statuses))

def background_worker():
    print("🚀 Render Amazon Fashion Loot Worker Started (70%+ Off / <₹400)...")
    while True:
        scan_once()
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    run_flask()
