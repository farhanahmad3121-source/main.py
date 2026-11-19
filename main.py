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
    return "Amazon 55-Keyword Loot Bot (10s Gap, No Retry, Strict Filter) Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

MIN_DISCOUNT = 90          # 90% या उससे ज़्यादा ऑफ
MAX_PRICE = 100            # ₹100 या उससे कम
LOOP_DELAY = 600           # राउंड पूरा होने के बाद 10 मिनट (600 सेकंड) का इंतज़ार
KEYWORD_DELAY = 10         # हर कीवर्ड सर्च के बाद 10 सेकंड का गैप

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/604.1",
]

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

def is_captcha_or_block_page(html_text: str) -> bool:
    t = html_text.lower()
    block_phrases = [
        "enter the characters you see below",
        "type the characters you see in this image",
        "sorry, we just need to make sure you're not a robot",
        "automated access to amazon data",
        "api-services-support@amazon.com",
        "request was blocked",
    ]
    return any(p in t for p in block_phrases)

def extract_real_price_and_discount(card_element, full_text: str):
    main_prices = []
    for el in card_element.select(".a-price .a-offscreen"):
        raw = el.get_text(" ", strip=True)
        parent_ctx = el.parent.parent.get_text(" ", strip=True).lower() if el.parent and el.parent.parent else ""
        if any(unit in parent_ctx for unit in ["/ count", "/count", "/ pair", "/pair", "/ pack", "/pack", "/ piece", "/piece", "per pair", "per count"]):
            continue
        m = re.findall(r"₹\s*([\d,]+)", raw)
        for num_str in m:
            try:
                val = int(num_str.replace(",", ""))
                if val > 0:
                    main_prices.append(val)
            except ValueError:
                pass

    if not main_prices:
        cleaned_for_price = re.sub(
            r"₹\s*[\d,]+\s*/\s*(count|pair|pack|piece|pc|item)",
            "",
            full_text,
            flags=re.IGNORECASE,
        )
        for num_str in re.findall(r"₹\s*([\d,]+)", cleaned_for_price):
            try:
                val = int(num_str.replace(",", ""))
                if val > 0:
                    main_prices.append(val)
            except ValueError:
                pass

    real_price = main_prices[0] if main_prices else None

    discounts = []
    for d in re.findall(r"(\d{1,3})\s*%\s*off", full_text, flags=re.IGNORECASE):
        try:
            discounts.append(int(d))
        except ValueError:
            pass

    max_discount = max(discounts) if discounts else 0
    return real_price, max_discount

def has_free_delivery(text: str) -> bool:
    t = text.lower()
    return ("free delivery" in t) or ("free shipping" in t)

def scan_once():
    count_200 = 0
    count_403 = 0
    count_503 = 0
    count_other_err = 0
    count_captcha_block = 0
    empty_keywords = []
    blocked_keywords = []
    deals_sent = 0

    for kw in KEYWORDS:
        query = kw.strip().replace(" ", "+")
        base_url = f"https://www.amazon.in/s?k={query}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.amazon.in/",
        }
        try:
            resp = requests.get(base_url, headers=headers, timeout=12)
            code = resp.status_code

            if code == 403:
                count_403 += 1
                print(f"[Status 403] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code == 503:
                count_503 += 1
                print(f"[Status 503] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code != 200:
                count_other_err += 1
                print(f"[Status {code}] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue

            if is_captcha_or_block_page(resp.text):
                count_captcha_block += 1
                blocked_keywords.append(kw)
                print(f"[Captcha/Blocked on 200] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue

            count_200 += 1
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div[data-component-type='s-search-result']")

            if len(items) == 0:
                empty_keywords.append(kw)
                print(f"[0 Items on 200] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue

            for item in items:
                text = item.get_text(" ", strip=True)
                if not text:
                    continue

                price, discount = extract_real_price_and_discount(item, text)
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
            count_other_err += 1
            print(f"[Error {kw}]: {e}")

        time.sleep(KEYWORD_DELAY)

    total_issues = count_403 + count_503 + count_other_err + count_captcha_block
    if total_issues == 0:
        health_line = "✅ सब एकदम सही चल रहा है, कोई 403 / 503 / कैप्चा या एरर नहीं आया है!"
    else:
        health_line = (
            f"⚠️ ध्यान दें: कुछ दिक्कतें आईं "
            f"(Captcha/Block: {count_captcha_block}, 403: {count_403}, 503: {count_503}, अन्य एरर: {count_other_err})"
        )

    extra_lines = []
    if blocked_keywords:
        extra_lines.append(f"• ब्लॉक/कैप्चा वाले कीवर्ड्स ({len(blocked_keywords)}): {', '.join(blocked_keywords[:8])}")
    if empty_keywords:
        extra_lines.append(f"• 0 आइटम वाले कीवर्ड्स ({len(empty_keywords)}): {', '.join(empty_keywords[:10])}")

    extra_text = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

    send_telegram(
        f"🕒 10-Min Bot Status Report\n"
        f"{health_line}\n"
        f"• Clean 200 OK Pages: {count_200}/{len(KEYWORDS)} | Captcha/Block: {count_captcha_block}\n"
        f"• 403: {count_403} | 503: {count_503} | अन्य एरर: {count_other_err}{extra_text}\n"
        f"• नई लूट भेजी गई: {deals_sent}"
    )

def background_worker():
    print("🚀 Render 55-Keyword Loot Bot Started (10s Gap, No Retry)...")
    send_telegram(
        f"🚀 सर्चिंग चालू हो गई है!\n"
        f"• कुल कीवर्ड्स: {len(KEYWORDS)}\n"
        f"• फ़िल्टर: 90%+ ऑफ + ₹100 या उससे कम (असली प्राइस, प्रति-यूनिट नहीं) + फ्री डिलीवरी\n"
        f"• हर कीवर्ड के बाद {KEYWORD_DELAY} सेकंड का गैप (बिना retry के) और राउंड के बाद 10 मिनट की रिपोर्ट।"
    )
    while True:
        scan_once()
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    run_flask()
