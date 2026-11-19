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
    return "Amazon 55-Keyword Loot Bot (Instant Error Alert + Strict Card/Link Check) Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

MIN_DISCOUNT = 90              # 90% या उससे ज़्यादा ऑफ
MAX_PRICE = 100                # ₹100 या उससे कम
LOOP_DELAY = 600               # राउंड पूरा होने के बाद 10 मिनट (600 सेकंड) का इंतज़ार
KEYWORD_DELAY = 4              # हर कीवर्ड सर्च के बाद 4 सेकंड का गैप
SEEN_EXPIRY_DAYS = 3           # 3 दिन बाद पुराने seen रिकॉर्ड अपने आप साफ/डिलीट हो जाएँगे
SEEN_EXPIRY_SECONDS = SEEN_EXPIRY_DAYS * 86400

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

seen_deals = {}

def cleanup_old_seen_deals():
    now = time.time()
    expired_keys = [k for k, ts in seen_deals.items() if (now - ts) >= SEEN_EXPIRY_SECONDS]
    for k in expired_keys:
        del seen_deals[k]
    if expired_keys:
        print(f"[Cleanup] {len(expired_keys)} पुराने seen आइटम ({SEEN_EXPIRY_DAYS} दिन पुराने) हटा दिए गए।")

def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Error] BOT_TOKEN या CHAT_ID सेट नहीं है।")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4000], "disable_web_page_preview": False},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[Telegram Error]: {r.text}")
    except Exception as e:
        print(f"[Telegram Exception]: {e}")

def send_instant_error(kw: str, err_type: str, reason: str):
    msg = (
        f"🚨 INSTANT ERROR ALERT\n"
        f"🔍 कीवर्ड/कपड़ा: {kw}\n"
        f"⚠️ एरर प्रकार: {err_type}\n"
        f"📌 वजह: {reason}"
    )
    send_telegram(msg)
    time.sleep(0.3)

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

def extract_strict_product_info(item, base_url: str):
    # 1. असली टाइटल चेक
    title_el = item.select_one("h2 span")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    if not title or len(title) < 4:
        return None, None

    # 2. असली प्रोडक्ट लिंक (/dp/ या /gp/) चेक
    product_link = None
    for a_el in item.select("a[href]"):
        href = a_el.get("href", "").strip()
        if "/dp/" in href or "/gp/product/" in href:
            if href.startswith("/"):
                clean = "https://www.amazon.in" + href.split("?")[0]
            elif href.startswith("http"):
                clean = href.split("?")[0]
            else:
                clean = ""
            if clean and ("/s?" not in clean):
                product_link = clean
                break

    if not product_link:
        return None, None

    return title, product_link

def scan_once():
    cleanup_old_seen_deals()

    count_200 = 0
    err_403_keywords = []
    err_503_keywords = []
    other_err_keywords = []
    blocked_keywords = []
    empty_keywords = []
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
                err_403_keywords.append(kw)
                send_instant_error(kw, "HTTP 403", "Amazon ने एक्सेस 403 दिया")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code == 503:
                err_503_keywords.append(kw)
                send_instant_error(kw, "HTTP 503", "Amazon ने 503 सर्विस अनअवेलेबल दिया")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code != 200:
                other_err_keywords.append(f"{kw} (HTTP {code})")
                send_instant_error(kw, f"HTTP {code}", f"अपेक्षित 200 के बजाय {code} आया")
                time.sleep(KEYWORD_DELAY)
                continue

            if is_captcha_or_block_page(resp.text):
                blocked_keywords.append(kw)
                send_instant_error(kw, "Captcha/Block", "HTTP 200 आया पर अंदर कैप्चा/रोबोट ब्लॉक पेज मिला")
                time.sleep(KEYWORD_DELAY)
                continue

            count_200 += 1
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div[data-component-type='s-search-result']")

            if len(items) == 0:
                empty_keywords.append(kw)
                send_instant_error(kw, "0 Items", "पेज 200 खुला पर कोई प्रोडक्ट कार्ड नहीं मिला")
                time.sleep(KEYWORD_DELAY)
                continue

            for item in items:
                text = item.get_text(" ", strip=True)
                if not text:
                    continue

                lower_text = text.lower()
                if "currently unavailable" in lower_text or "page not found" in lower_text:
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

                title, link = extract_strict_product_info(item, base_url)
                if not title or not link:
                    continue

                sig = f"{link.lower()}|{title.lower()[:70]}"
                if sig in seen_deals:
                    continue
                seen_deals[sig] = time.time()

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
            err_label = f"{kw} ({type(e).__name__})"
            other_err_keywords.append(err_label)
            send_instant_error(kw, type(e).__name__, str(e)[:180])

        time.sleep(KEYWORD_DELAY)

    count_403 = len(err_403_keywords)
    count_503 = len(err_503_keywords)
    count_other_err = len(other_err_keywords)
    count_captcha_block = len(blocked_keywords)

    total_issues = count_403 + count_503 + count_other_err + count_captcha_block
    if total_issues == 0:
        health_line = "✅ सब एकदम सही चल रहा है, कोई 403 / 503 / कैप्चा या एरर नहीं आया है!"
    else:
        health_line = (
            f"⚠️ ध्यान दें: कुछ दिक्कतें आईं "
            f"(Captcha/Block: {count_captcha_block}, 403: {count_403}, 503: {count_503}, अन्य एरर: {count_other_err})"
        )

    detail_lines = []
    if err_503_keywords:
        detail_lines.append(f"• 503 एरर वाले कीवर्ड्स ({count_503}): {', '.join(err_503_keywords)}")
    if err_403_keywords:
        detail_lines.append(f"• 403 एरर वाले कीवर्ड्स ({count_403}): {', '.join(err_403_keywords)}")
    if other_err_keywords:
        detail_lines.append(f"• अन्य एरर वाले कीवर्ड्स ({count_other_err}): {', '.join(other_err_keywords)}")
    if blocked_keywords:
        detail_lines.append(f"• ब्लॉक/कैप्चा वाले कीवर्ड्स ({count_captcha_block}): {', '.join(blocked_keywords)}")
    if empty_keywords:
        detail_lines.append(f"• 0 आइटम वाले कीवर्ड्स ({len(empty_keywords)}): {', '.join(empty_keywords)}")

    details_text = ("\n" + "\n".join(detail_lines)) if detail_lines else ""

    report_msg = (
        f"🕒 10-Min Bot Status Report\n"
        f"{health_line}\n"
        f"• Clean 200 OK Pages: {count_200}/{len(KEYWORDS)} | Captcha/Block: {count_captcha_block}\n"
        f"• 403: {count_403} | 503: {count_503} | अन्य एरर: {count_other_err}{details_text}\n"
        f"• नई लूट भेजी गई: {deals_sent}"
    )

    if len(report_msg) <= 4000:
        send_telegram(report_msg)
    else:
        send_telegram(report_msg[:3950] + "\n... (रिपोर्ट लंबी होने पर आगे का हिस्सा कटा)")

def background_worker():
    print("🚀 Render 55-Keyword Loot Bot Started (Instant Error Alert + Strict Check)...")
    send_telegram(
        f"🚀 सर्चिंग चालू हो गई है!\n"
        f"• कुल कीवर्ड्स: {len(KEYWORDS)}\n"
        f"• फ़िल्टर: 90%+ ऑफ + ₹100 या उससे कम (असली प्राइस) + फ्री डिलीवरी + साफ टाइटल व /dp/ लिंक\n"
        f"• कोई भी एरर आते ही तुरंत अलर्ट, {KEYWORD_DELAY}s गैप, {SEEN_EXPIRY_DAYS} दिन में पुराना डेटा साफ, और राउंड के बाद रिपोर्ट।"
    )
    while True:
        scan_once()
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    run_flask()
