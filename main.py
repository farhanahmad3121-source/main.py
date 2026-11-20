import gc
import os
import re
import json
import time
import random
import threading
import traceback
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def home():
    return "Multi-Site Loot Bot (Per-Site Error Breakdown + Isolated Sessions) Running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)


TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

KEYWORDS_FILE_PATH = os.environ.get("KEYWORDS_FILE", "keywords/keywords.txt")
SEEN_DEALS_FILE_PATH = os.environ.get("SEEN_DEALS_FILE", "data/seen_deals.json")

MIN_DISCOUNT = 90              # 90% या उससे ज़्यादा ऑफ़
MAX_PRICE = 100                # ₹100 या उससे कम
BATCH_SIZE = 50                # हर 50 कीवर्ड के बाद बैच रिपोर्ट
LOOP_DELAY = 600               # पूरा साइकिल खत्म होने के बाद 10 मिनट का इंतज़ार
KEYWORD_DELAY = 0.15           # हर कीवर्ड के बाद बेस गैप
SITE_STEP_DELAY = 0.15         # साइट्स के बीच गैप
SEEN_EXPIRY_DAYS = 20          # 20 दिन तक वही डील दोबारा नहीं आएगी
SEEN_EXPIRY_SECONDS = SEEN_EXPIRY_DAYS * 86400
TELEGRAM_RETRY_DELAY = 2       # Telegram एरर आने पर 2 सेकंड में री-ट्राई
MAX_CONSECUTIVE_BAD = 5        # लगातार 5 ब्लॉक/एरर पर स्मार्ट ब्रेक
COOLDOWN_SECONDS = 900         # 15 मिनट का कूल-डाउन ब्रेक

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

file_io_lock = threading.Lock()
worker_lock = threading.Lock()
worker_started = False


def make_headers(referer: str) -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer,
    }


def load_keywords_from_file(filepath: str = KEYWORDS_FILE_PATH) -> list:
    if not os.path.exists(filepath):
        print(f"[Keywords] फ़ाइल नहीं मिली: {filepath}")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.read().strip()

        if not raw_content:
            return []

        if filepath.lower().endswith(".json"):
            data = json.loads(raw_content)
            items = [str(x).strip() for x in data if str(x).strip()] if isinstance(data, list) else []
        else:
            cleaned_lines = []
            for line in raw_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for part in line.split(","):
                    kw = part.strip().strip('"').strip("'")
                    if kw:
                        cleaned_lines.append(kw)
            items = cleaned_lines

        return list(dict.fromkeys(items))
    except Exception as e:
        print(f"[Keywords Load Error] {e}")
        return []


def load_seen_deals() -> dict:
    with file_io_lock:
        if not os.path.exists(SEEN_DEALS_FILE_PATH):
            return {}
        try:
            with open(SEEN_DEALS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
            return {}
        except Exception as e:
            print(f"[Seen Load Error] {e}")
            return {}


def save_seen_deals(deals_dict: dict):
    with file_io_lock:
        try:
            parent_dir = os.path.dirname(SEEN_DEALS_FILE_PATH)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            tmp_path = f"{SEEN_DEALS_FILE_PATH}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(deals_dict, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, SEEN_DEALS_FILE_PATH)
        except Exception as e:
            print(f"[Seen Save Error] {e}")


seen_deals = load_seen_deals()


def cleanup_old_seen_deals():
    now = time.time()
    expired_keys = [k for k, ts in seen_deals.items() if (now - ts) >= SEEN_EXPIRY_SECONDS]
    for k in expired_keys:
        del seen_deals[k]
    if expired_keys:
        save_seen_deals(seen_deals)
        print(f"[Cleanup] {len(expired_keys)} पुराने seen आइटम ({SEEN_EXPIRY_DAYS} दिन पुराने) हटा दिए गए।")


def send_telegram(msg: str, retry_forever: bool = False) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Error] BOT_TOKEN या CHAT_ID सेट नहीं है।")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    attempt = 0

    while True:
        attempt += 1
        try:
            r = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4000], "disable_web_page_preview": False},
                timeout=10,
            )
            if r.status_code == 200:
                return True

            retry_after = TELEGRAM_RETRY_DELAY
            try:
                resp_json = r.json()
                ra = resp_json.get("parameters", {}).get("retry_after")
                if isinstance(ra, (int, float)) and ra > 0:
                    retry_after = float(ra)
            except Exception:
                pass

            print(f"[Telegram Error - Attempt {attempt}]: {r.status_code} {r.text}")
            if not retry_forever:
                return False
            time.sleep(retry_after)
        except Exception as e:
            print(f"[Telegram Exception - Attempt {attempt}]: {e}")
            if not retry_forever:
                return False
            time.sleep(TELEGRAM_RETRY_DELAY)


def send_alert_safe(msg: str):
    if not send_telegram(msg, retry_forever=False):
        send_telegram(msg, retry_forever=True)


def is_captcha_or_block_page(html_text: str) -> bool:
    t = html_text.lower()
    block_phrases = [
        "enter the characters you see below",
        "type the characters you see in this image",
        "sorry, we just need to make sure you're not a robot",
        "automated access to amazon data",
        "api-services-support@amazon.com",
        "request was blocked",
        "access denied",
    ]
    return any(p in t for p in block_phrases)


def classify_zero_items_reason(html_text: str) -> str:
    t = html_text.lower()
    no_res_phrases = [
        "no results for",
        "0 results for",
        "did not match any products",
        "try checking your spelling",
        "no products found",
    ]
    if any(p in t for p in no_res_phrases):
        return "कोई रिजल्ट नहीं"
    if "something went wrong" in t or "sorry!" in t:
        return "एरर पेज"
    return "खाली/अलग लेआउट"


def parse_price_int(raw_str: str):
    m = re.findall(r"₹\s*[\d,]+(?:\.\d+)?", raw_str)
    for num_str in m:
        try:
            val = int(float(num_str.replace("₹", "").replace(",", "").strip()))
            if val > 0:
                return val
        except ValueError:
            pass
    return None


def extract_discount_percent(full_text: str) -> int:
    discounts = []
    for d in re.findall(r"\(?\s*(\d{1,3})\s*%\s*off\s*\)?", full_text, flags=re.IGNORECASE):
        try:
            d_val = int(d)
            if 1 <= d_val <= 99:
                discounts.append(d_val)
        except ValueError:
            pass
    return max(discounts) if discounts else 0


def has_free_delivery(text: str) -> bool:
    t = text.lower()
    return ("free delivery" in t) or ("free shipping" in t)


def extract_asin_from_link(link: str) -> str:
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", link, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_amazon_price_and_discount(card_element, full_text: str):
    main_prices = []
    for el in card_element.select('.a-price:not([data-a-strike="true"]) .a-offscreen'):
        raw = el.get_text(" ", strip=True)
        parent_ctx = el.parent.parent.get_text(" ", strip=True).lower() if el.parent and el.parent.parent else ""
        if any(unit in parent_ctx for unit in ["/ count", "/count", "/ pair", "/pair", "/ pack", "/pack", "/ piece"]):
            continue
        val = parse_price_int(raw)
        if val is not None:
            main_prices.append(val)

    if not main_prices:
        cleaned_for_price = re.sub(
            r"₹\s*[\d,]+\s*/\s*(count|pair|pack|piece|pc|item)",
            "",
            full_text,
            flags=re.IGNORECASE,
        )
        for num_str in re.findall(r"₹\s*[\d,]+", cleaned_for_price):
            val = parse_price_int(num_str)
            if val is not None:
                main_prices.append(val)

    real_price = main_prices[0] if main_prices else None
    max_discount = extract_discount_percent(full_text)
    return real_price, max_discount


def extract_amazon_product_info(item):
    title_el = item.select_one("h2 span")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    if not title or len(title) < 4:
        return None, None, ""

    product_link = None
    asin = ""
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
                asin = extract_asin_from_link(clean)
                product_link = f"https://www.amazon.in/dp/{asin}" if asin else clean
                break

    if not product_link:
        return None, None, ""

    return title, product_link, asin


def scrape_amazon_kw(session: requests.Session, kw: str):
    query = kw.strip().replace(" ", "+")
    url = f"https://www.amazon.in/s?k={query}"
    resp = session.get(url, headers=make_headers("https://www.amazon.in/"), timeout=10)
    code = resp.status_code

    if code != 200 or is_captcha_or_block_page(resp.text):
        err_tag = f"HTTP_{code}" if code != 200 else "BLOCK_CAPTCHA"
        return {"status": "bad", "err_tag": err_tag, "count": 0, "deals": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('div[data-component-type="s-search-result"]')
    count = len(items)
    if count == 0:
        del soup
        return {"status": "empty", "err_tag": "", "count": 0, "deals": []}

    deals = []
    for item in items:
        text = item.get_text(" ", strip=True)
        if not text:
            continue
        lower_text = text.lower()
        if "currently unavailable" in lower_text or "page not found" in lower_text:
            continue

        price, discount = extract_amazon_price_and_discount(item, text)
        free_del = has_free_delivery(text)
        if not ((discount >= MIN_DISCOUNT) and (price is not None) and (0 < price <= MAX_PRICE) and free_del):
            continue

        title, link, asin = extract_amazon_product_info(item)
        if not title or not link:
            continue

        sig = f"amz:asin:{asin}" if asin else f"amz:{link.lower()}|{title.lower()[:70]}"
        legacy_sig = f"{link.lower()}|{title.lower()[:70]}"
        deals.append({"sig": sig, "legacy_sig": legacy_sig, "title": title, "price": price, "discount": discount, "link": link})

    del soup
    return {"status": "ok", "err_tag": "", "count": count, "deals": deals}


def scrape_flipkart_kw(session: requests.Session, kw: str):
    query = requests.utils.quote(kw.strip())
    url = f"https://www.flipkart.com/search?q={query}"
    resp = session.get(url, headers=make_headers("https://www.flipkart.com/"), timeout=10)
    code = resp.status_code

    if code != 200 or is_captcha_or_block_page(resp.text):
        err_tag = f"HTTP_{code}" if code != 200 else "BLOCK_CAPTCHA"
        return {"status": "bad", "err_tag": err_tag, "count": 0, "deals": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("div[data-id]")
    if not cards:
        raw_parents = [a.parent for a in soup.select("a[href*='/p/']") if a.parent and len(a.parent.get_text(strip=True)) > 15]
        seen_ids = set()
        cards = []
        for c in raw_parents:
            if id(c) not in seen_ids:
                seen_ids.add(id(c))
                cards.append(c)

    count = len(cards)
    if count == 0:
        del soup
        return {"status": "empty", "err_tag": "", "count": 0, "deals": []}

    deals = []
    for card in cards:
        text = card.get_text(" ", strip=True)
        if not text:
            continue

        discount = extract_discount_percent(text)
        free_del = has_free_delivery(text)
        prices = [v for m_str in re.findall(r"₹\s*[\d,]+", text) if (v := parse_price_int(m_str)) is not None and 0 < v <= MAX_PRICE]
        price = min(prices) if prices else None
        if not ((discount >= MIN_DISCOUNT) and (price is not None) and free_del):
            continue

        link = None
        title = ""
        for a_el in card.select("a[href]"):
            href = a_el.get("href", "").strip()
            if "/p/" in href:
                link = ("https://www.flipkart.com" + href.split("?")[0]) if href.startswith("/") else href.split("?")[0]
                t_txt = a_el.get("title") or a_el.get_text(" ", strip=True)
                if t_txt and len(t_txt.strip()) >= 4:
                    title = t_txt.strip()
                break

        if not title:
            for tag in card.select("div, a, span"):
                t = tag.get_text(" ", strip=True)
                if 6 <= len(t) <= 140 and "₹" not in t and "% off" not in t.lower():
                    title = t
                    break

        if not title or not link or len(title) < 4:
            continue

        sig = f"fk:{link.lower()}|{title.lower()[:70]}"
        deals.append({"sig": sig, "legacy_sig": "", "title": title, "price": price, "discount": discount, "link": link})

    del soup
    return {"status": "ok", "err_tag": "", "count": count, "deals": deals}


def scrape_meesho_kw(session: requests.Session, kw: str):
    query = requests.utils.quote(kw.strip())
    url = f"https://www.meesho.com/search?q={query}"
    resp = session.get(url, headers=make_headers("https://www.meesho.com/"), timeout=10)
    code = resp.status_code

    if code != 200 or is_captcha_or_block_page(resp.text):
        err_tag = f"HTTP_{code}" if code != 200 else "BLOCK_CAPTCHA"
        return {"status": "bad", "err_tag": err_tag, "count": 0, "deals": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("a[href*='/p/']")
    if not cards:
        cards = soup.select("div[class*='ProductCard'], div[class*='NewProductCard']")

    count = len(cards)
    if count == 0:
        del soup
        return {"status": "empty", "err_tag": "", "count": 0, "deals": []}

    deals = []
    for card in cards:
        container = card if card.name == "div" else (card.parent or card)
        text = container.get_text(" ", strip=True)
        if not text:
            continue

        discount = extract_discount_percent(text)
        free_del = has_free_delivery(text)
        prices = [v for m_str in re.findall(r"₹\s*[\d,]+", text) if (v := parse_price_int(m_str)) is not None and 0 < v <= MAX_PRICE]
        price = min(prices) if prices else None
        if not ((discount >= MIN_DISCOUNT) and (price is not None) and free_del):
            continue

        href = card.get("href", "").strip() if card.name == "a" else ""
        if not href:
            a_el = container.select_one("a[href*='/p/']")
            href = a_el.get("href", "").strip() if a_el else ""
        if not href:
            continue

        link = ("https://www.meesho.com" + href.split("?")[0]) if href.startswith("/") else href.split("?")[0]
        title = ""
        for tag in container.select("p, span, div"):
            t = tag.get_text(" ", strip=True)
            if 5 <= len(t) <= 140 and "₹" not in t and "% off" not in t.lower() and "free delivery" not in t.lower():
                title = t
                break

        if not title or not link:
            continue

        sig = f"meesho:{link.lower()}|{title.lower()[:70]}"
        deals.append({"sig": sig, "legacy_sig": "", "title": title, "price": price, "discount": discount, "link": link})

    del soup
    return {"status": "ok", "err_tag": "", "count": count, "deals": deals}


def format_bad_streak_breakdown(bad_events: list) -> str:
    """लगातार खराब रिक्वेस्ट्स में किस साइट में कितने एरर आए, उसका हिसाब बनाता है।"""
    counts = {"Amazon": 0, "Flipkart": 0, "Meesho": 0}
    details = []
    for ev in bad_events:
        site = ev["site"]
        tag = ev["tag"]
        kw = ev["kw"]
        counts[site] = counts.get(site, 0) + 1
        details.append(f"• {site} ({tag}) — {kw}")

    summary = f"AMZ: {counts['Amazon']} | FK: {counts['Flipkart']} | Meesho: {counts['Meesho']}"
    return summary, "\n".join(details[-8:])


def build_batch_report(
    batch_num: int,
    total_batches: int,
    start_idx: int,
    end_idx: int,
    batch_stats: dict,
    batch_deals: int,
    batch_kw_rows: list,
) -> str:
    batch_len = end_idx - start_idx
    total_amz_items = sum(r["amz"] for r in batch_kw_rows)
    total_fk_items = sum(r["fk"] for r in batch_kw_rows)
    total_meesho_items = sum(r["meesho"] for r in batch_kw_rows)

    lines = [
        f"📦 Batch Report ({batch_num}/{total_batches}) — Keywords #{start_idx+1} to {end_idx}",
        f"• आइटम काउंट: AMZ {total_amz_items} | FK {total_fk_items} | Meesho {total_meesho_items} | नई लूट: {batch_deals}",
        f"• एरर/ब्लॉक ब्रेकडाउन -> AMZ: {batch_stats['amz_bad']} | FK: {batch_stats['fk_bad']} | Meesho: {batch_stats['meesho_bad']}",
        f"• 0 आइटम -> AMZ: {batch_stats['amz_empty']} | FK: {batch_stats['fk_empty']} | Meesho: {batch_stats['meesho_empty']}",
        "\n📋 हर नाम पर पेज आइटम (AMZ / FK / Meesho):",
    ]

    for r in batch_kw_rows:
        row_txt = f"• {r['kw']}: A:{r['amz']} | F:{r['fk']} | M:{r['meesho']}" + (f" (🔥{r['deals']})" if r["deals"] > 0 else "")
        current_len = sum(len(x) + 1 for x in lines)
        if current_len + len(row_txt) > 3880:
            lines.append("... (मैसेज लिमिट के कारण बाकी नाम कटे)")
            break
        lines.append(row_txt)

    report = "\n".join(lines)
    return report[:3940] + "\n... (कटी)" if len(report) > 3950 else report


def scan_once():
    global seen_deals
    if not seen_deals:
        seen_deals = load_seen_deals()
    cleanup_old_seen_deals()

    keywords = load_keywords_from_file(KEYWORDS_FILE_PATH)
    total_kw = len(keywords)
    if total_kw == 0:
        send_alert_safe(f"⚠️ '{KEYWORDS_FILE_PATH}' में कोई कीवर्ड नहीं मिला!")
        return

    total_batches = (total_kw + BATCH_SIZE - 1) // BATCH_SIZE
    overall_deals = 0
    bad_events_streak = []
    slowdown_remaining = 0

    sessions = {
        "amz": requests.Session(),
        "fk": requests.Session(),
        "meesho": requests.Session(),
    }
    sites = [
        ("amz", "Amazon", scrape_amazon_kw),
        ("fk", "Flipkart", scrape_flipkart_kw),
        ("meesho", "Meesho", scrape_meesho_kw),
    ]

    try:
        for batch_idx in range(total_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_kw)
            batch_kws = keywords[start_idx:end_idx]

            b_deals = 0
            b_kw_rows = []
            b_stats = {
                "amz_ok": 0, "amz_empty": 0, "amz_bad": 0,
                "fk_ok": 0, "fk_empty": 0, "fk_bad": 0,
                "meesho_ok": 0, "meesho_empty": 0, "meesho_bad": 0,
            }

            for kw in batch_kws:
                row = {"kw": kw, "amz": 0, "fk": 0, "meesho": 0, "deals": 0}
                kw_bad_list = []

                for code_key, site_label, scraper_fn in sites:
                    try:
                        res = scraper_fn(sessions[code_key], kw)
                        status = res["status"]
                        cnt = res["count"]
                        row[code_key] = cnt

                        if status == "ok":
                            b_stats[f"{code_key}_ok"] += 1
                            for d in res["deals"]:
                                sig = d["sig"]
                                legacy_sig = d["legacy_sig"]
                                if (sig in seen_deals) or (legacy_sig and legacy_sig in seen_deals):
                                    continue

                                msg = (
                                    f"🔥 TRIPLE LOOT ({site_label} | 90%+ OFF | <=₹100 | FREE DELIVERY)\n\n"
                                    f"🔎 Keyword: {kw} (पेज आइटम: {cnt})\n"
                                    f"🛍️ {d['title'][:160]}\n"
                                    f"💰 Price: ₹{d['price']} | 🏷️ Discount: {d['discount']}% | 🚚 Free Delivery: Yes\n"
                                    f"🔗 {d['link']}"
                                )
                                if send_telegram(msg, retry_forever=True):
                                    seen_deals[sig] = time.time()
                                    save_seen_deals(seen_deals)
                                    b_deals += 1
                                    row["deals"] += 1
                                    time.sleep(0.2)
                        elif status == "empty":
                            b_stats[f"{code_key}_ok"] += 1
                            b_stats[f"{code_key}_empty"] += 1
                        else:
                            b_stats[f"{code_key}_bad"] += 1
                            kw_bad_list.append({"site": site_label, "tag": res["err_tag"], "kw": kw})
                            print(f"[{site_label} {res['err_tag']}] {kw}")
                    except Exception as e:
                        b_stats[f"{code_key}_bad"] += 1
                        err_name = type(e).__name__
                        kw_bad_list.append({"site": site_label, "tag": err_name, "kw": kw})
                        print(f"[{site_label} {err_name} {kw}]: {e}")

                    step_gap = SITE_STEP_DELAY * (3.0 if slowdown_remaining > 0 else 1.0)
                    if step_gap > 0:
                        time.sleep(step_gap)

                b_kw_rows.append(row)
                print(f"[KW Done] {kw} -> AMZ:{row['amz']} | FK:{row['fk']} | Meesho:{row['meesho']}")

                if kw_bad_list:
                    bad_events_streak.extend(kw_bad_list)
                    if len(bad_events_streak) >= MAX_CONSECUTIVE_BAD:
                        site_summary, recent_lines = format_bad_streak_breakdown(bad_events_streak)
                        send_alert_safe(
                            f"⏸️ स्मार्ट ब्रेक सक्रिय!\n"
                            f"• लगातार {len(bad_events_streak)} ब्लॉक/एरर आए।\n"
                            f"• किस साइट में कितने एरर: {site_summary}\n"
                            f"• हाल के एरर:\n{recent_lines}\n"
                            f"• बॉट {COOLDOWN_SECONDS // 60} मिनट रुकेगा, फिर धीमी रफ़्तार से शुरू होगा।"
                        )
                        time.sleep(COOLDOWN_SECONDS)
                        bad_events_streak = []
                        slowdown_remaining = 25
                else:
                    bad_events_streak = []
                    if slowdown_remaining > 0:
                        slowdown_remaining -= 1

                kw_gap = KEYWORD_DELAY * (3.0 if slowdown_remaining > 0 else 1.0)
                if kw_gap > 0:
                    time.sleep(kw_gap)

            overall_deals += b_deals
            batch_msg = build_batch_report(
                batch_num=batch_idx + 1,
                total_batches=total_batches,
                start_idx=start_idx,
                end_idx=end_idx,
                batch_stats=b_stats,
                batch_deals=b_deals,
                batch_kw_rows=b_kw_rows,
            )
            send_alert_safe(batch_msg)
            gc.collect()

    finally:
        for s in sessions.values():
            s.close()
        gc.collect()

    send_alert_safe(
        f"🏁 Full Multi-Site Cycle Complete ({total_kw} Keywords across Amazon, Flipkart & Meesho)\n"
        f"• कुल नई लूट भेजी गई: {overall_deals}\n"
        f"• अब {LOOP_DELAY // 60} मिनट बाद अगला राउंड होगा।"
    )


def background_worker():
    global worker_started
    with worker_lock:
        if worker_started:
            return
        worker_started = True

    try:
        initial_kws = load_keywords_from_file(KEYWORDS_FILE_PATH)
        print(f"Multi-Site Loot Bot Started ({len(initial_kws)} Keywords)...")
        send_alert_safe(
            f"🤖 Multi-Site बॉट चालू हो गया!\n"
            f"• क्रम: Amazon → Flipkart → Meesho (अलग-अलग Session)\n"
            f"• कीवर्ड्स: {len(initial_kws)} ({KEYWORDS_FILE_PATH})"
        )

        cycle_no = 0
        while True:
            cycle_no += 1
            try:
                scan_once()
            except Exception as cycle_err:
                tb_short = traceback.format_exc()[-900:]
                send_alert_safe(
                    f"⚠️ रन #{cycle_no} में एरर:\n"
                    f"• {type(cycle_err).__name__}: {cycle_err}\n"
                    f"• Trace:\n{tb_short}"
                )
                time.sleep(10)
                continue

            time.sleep(LOOP_DELAY)

    except Exception as fatal_err:
        tb_fatal = traceback.format_exc()[-900:]
        send_alert_safe(
            f"🛑 बॉट वर्कर डेड हो गया:\n"
            f"• {type(fatal_err).__name__}: {fatal_err}\n"
            f"• Trace:\n{tb_fatal}"
        )
    finally:
        with worker_lock:
            worker_started = False


if __name__ == "__main__":
    t = threading.Thread(target=background_worker, name="LootWorkerThread")
    t.daemon = True
    t.start()
    run_flask()
