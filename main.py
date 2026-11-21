import os
import re
import json
import time
import random
import threading
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from flask import Flask

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "YOUR_CHAT_ID")
KEYWORDS_FILE = "keywords/keywords.txt"
SEEN_FILE = "seen_deals.json"

BATCH_SIZE = 50
KEYWORD_DELAY = 6.0          # Single worker safe delay (avoid 503)
MAX_PRICE = 100              # ₹100 या उससे कम
MIN_DISCOUNT = 90            # 90% या उससे ज़्यादा (90% से 100% तक)

# सस्ती फालतू एक्सेसरीज़ ब्लॉक करने के लिए
BAD_WORDS = [
    "otg", "cable", "adapter", "adaptor", "cover", "back cover",
    "tempered glass", "screen guard", "keychain", "sticker", "ear tips",
    "sim ejector", "cleaning cloth", "dust plug", "strap only", "case only"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

app = Flask(__name__)

@app.route("/")
def home():
    return "Amazon 90%+ Loot Bot Running (Single Worker + Direct Filter URL)"


# ================= HELPERS =================
def send_telegram(text, photo_url=None):
    try:
        if photo_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": text,
                "parse_mode": "HTML"
            }
            r = requests.post(url, data=payload, timeout=15)
            if r.status_code == 200:
                return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        requests.post(url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram Error: {e}")


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen_set):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f)
    except Exception as e:
        print(f"Save Seen Error: {e}")


def load_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        return []
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        raw = f.read()
    # "Brand 1", "Brand 2" या लाइन-बाय-लाइन दोनों फ़ॉर्मेट सपोर्ट
    quoted = re.findall(r'"([^"]+)"', raw)
    if quoted:
        kws = [k.strip() for k in quoted if k.strip() and not k.strip().startswith("#")]
    else:
        kws = [line.strip().strip(",").strip('"') for line in raw.splitlines()
               if line.strip() and not line.strip().startswith("#")]
    # डुप्लीकेट हटाएं, क्रम बनाए रखें
    seen = set()
    unique_kws = []
    for k in kws:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            unique_kws.append(k)
    return unique_kws


def build_filtered_amazon_url(keyword):
    """
    सीधा Amazon का फ़िल्टर वाला URL बनाता है:
    1. p_36:-10000 -> ₹100 या उससे कम
    2. p_n_pct-off-with-tax:2665401031 -> 70%-90%+ हाई डिस्काउंट बकेट
    3. p_n_free_shipping_eligible:20556369031 -> Free Delivery
    4. s=pct-off-desc-rank -> सबसे ज़्यादा डिस्काउंट (90% से 100%) सबसे ऊपर
    """
    q = quote_plus(keyword)
    rh = "p_36%3A-10000%2Cp_n_pct-off-with-tax%3A2665401031%2Cp_n_free_shipping_eligible%3A20556369031"
    return f"https://www.amazon.in/s?k={q}&rh={rh}&s=pct-off-desc-rank"


def create_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def parse_price(text):
    if not text:
        return None
    nums = re.sub(r"[^\d.]", "", text)
    try:
        return float(nums)
    except ValueError:
        return None


def is_brand_match(keyword, title):
    title_low = title.lower()
    for bad in BAD_WORDS:
        if bad in title_low:
            return False
    words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", keyword) if len(w) >= 2]
    if not words:
        return True
    # कम से कम मुख्य ब्रांड शब्द टाइटल में होना ज़रूरी है
    return words[0] in title_low


# ================= SCRAPER =================
def check_keyword(session, keyword, seen_asins):
    url = build_filtered_amazon_url(keyword)
    try:
        resp = session.get(url, timeout=20)
    except Exception:
        return "ERROR", 0, []

    if resp.status_code == 503:
        return "503", 0, []
    if resp.status_code == 403:
        return "403", 0, []
    if resp.status_code != 200:
        return "ERROR", 0, []

    html = resp.text
    if "api-services-support@amazon.com" in html or "Type the characters you see in this image" in html:
        return "CAPTCHA", 0, []

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select('div[data-component-type="s-search-result"]')
    if not items:
        return "OK", 0, []

    found_loots = []
    for item in items:
        asin = item.get("data-asin", "").strip()
        if not asin or asin in seen_asins:
            continue

        # टाइटल
        h2 = item.select_one("h2")
        title = h2.get_text(" ", strip=True) if h2 else ""
        if not title or not is_brand_match(keyword, title):
            continue

        # सेल प्राइस (₹100 या कम)
        price_el = item.select_one("span.a-price span.a-offscreen")
        price = parse_price(price_el.get_text(strip=True)) if price_el else None
        if price is None or price > MAX_PRICE:
            continue

        # MRP (असली कीमत)
        mrp_el = item.select_one("span.a-price.a-text-price span.a-offscreen")
        mrp = parse_price(mrp_el.get_text(strip=True)) if mrp_el else None

        # डिस्काउंट % निकालना (टेक्स्ट से या Price/MRP से)
        discount_pct = 0
        full_text = item.get_text(" ", strip=True)
        disc_match = re.search(r"\((\d{1,3})%\s*off\)", full_text, re.IGNORECASE)
        if disc_match:
            discount_pct = int(disc_match.group(1))
        elif mrp and mrp > price:
            discount_pct = round(((mrp - price) / mrp) * 100)

        # शर्त 1: 90% से 100% तक ऑफ़
        if discount_pct < MIN_DISCOUNT or discount_pct > 100:
            continue

        # शर्त 2: Free Delivery चेक
        if "free delivery" not in full_text.lower():
            continue

        # इमेज और लिंक
        img_el = item.select_one("img.s-image")
        img_url = img_el.get("src") if img_el else None
        product_link = f"https://www.amazon.in/dp/{asin}"

        seen_asins.add(asin)
        found_loots.append({
            "asin": asin,
            "keyword": keyword,
            "title": title,
            "price": price,
            "mrp": mrp if mrp else 0,
            "discount": discount_pct,
            "link": product_link,
            "image": img_url,
            "filter_url": url
        })

    return "OK", len(items), found_loots


# ================= MAIN WORKER LOOP =================
def worker_loop():
    seen_asins = load_seen()
    session = create_session()

    while True:
        keywords = load_keywords()
        if not keywords:
            print("No keywords found, waiting 30s...")
            time.sleep(30)
            continue

        total_batches = (len(keywords) + BATCH_SIZE - 1) // BATCH_SIZE

        for b_idx in range(total_batches):
            start = b_idx * BATCH_SIZE
            end = min(start + BATCH_SIZE, len(keywords))
            batch_kws = keywords[start:end]

            ok_count = 0
            err_503 = []
            err_403 = []
            err_captcha = []
            err_other = []
            zero_items = []
            new_loot_count = 0

            # हर बैच पर नया सेशन ताकि 503 न आए
            session = create_session()

            for kw in batch_kws:
                status, item_count, loots = check_keyword(session, kw, seen_asins)

                if status == "OK":
                    ok_count += 1
                    if item_count == 0:
                        zero_items.append(kw)
                    for loot in loots:
                        new_loot_count += 1
                        save_seen(seen_asins)
                        msg = (
                            f"🔥 <b>{loot['discount']}% OFF LOOT FOUND!</b>\n\n"
                            f"🏷 <b>Brand:</b> {loot['keyword']}\n"
                            f"📦 <b>Product:</b> {loot['title']}\n"
                            f"💰 <b>Deal Price:</b> ₹{loot['price']:.0f} (MRP: ₹{loot['mrp']:.0f})\n"
                            f"🚚 <b>Delivery:</b> FREE Delivery\n\n"
                            f"🔗 <a href='{loot['link']}'>Buy Now on Amazon</a>\n"
                            f"🔎 <a href='{loot['filter_url']}'>Check 90%+ Filter Page</a>"
                        )
                        send_telegram(msg, loot["image"])
                elif status == "503":
                    err_503.append(kw)
                elif status == "403":
                    err_403.append(kw)
                elif status == "CAPTCHA":
                    err_captcha.append(kw)
                else:
                    err_other.append(kw)

                time.sleep(KEYWORD_DELAY + random.uniform(0.5, 1.5))

            # बैच रिपोर्ट
            total_in_batch = len(batch_kws)
            report = (
                f"📦 <b>Batch Report ({b_idx + 1}/{total_batches}) — Keywords #{start + 1} to {end}</b>\n"
                f"ℹ️ बैच {b_idx + 1}/{total_batches} (#{start + 1}-{end}): {ok_count}/{total_in_batch} नाम 200 OK गए, "
                f"{len(zero_items)} में 0 आइटम दिखे।\n"
                f"• सही गए (200 OK): {ok_count}/{total_in_batch} | 0 आइटम: {len(zero_items)} | नई लूट: {new_loot_count}\n"
            )
            if err_503:
                report += f"• ❌ 503 [{len(err_503)}]: {', '.join(err_503)}\n"
            if zero_items:
                report += f"• ⚪ 0 आइटम वाले नाम [{len(zero_items)}]: {', '.join(zero_items)}\n"

            send_telegram(report)


# Start background thread
threading.Thread(target=worker_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
