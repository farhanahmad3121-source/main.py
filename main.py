import gc
import os
import re
import json
import time
import random
import threading
import traceback
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def home():
    return "Amazon 80-100% Free Delivery Loot Bot Running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)


TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

KEYWORDS_FILE_PATH = os.environ.get("KEYWORDS_FILE", "keywords/keywords.txt")
SEEN_DEALS_FILE_PATH = os.environ.get("SEEN_DEALS_FILE", "data/seen_deals.json")

MIN_DISCOUNT = 80
MAX_DISCOUNT = 100
MAX_PAGES = 2
BATCH_SIZE = 50
LOOP_DELAY = 600
KEYWORD_DELAY = 0.05
PAGE_DELAY = 0.2
SEEN_EXPIRY_DAYS = 20
SEEN_EXPIRY_SECONDS = SEEN_EXPIRY_DAYS * 86400
TELEGRAM_RETRY_DELAY = 2
MAX_CONSECUTIVE_BAD = 5
COOLDOWN_SECONDS = 900

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6367.82 Mobile Safari/604.1",
]

file_io_lock = threading.Lock()
worker_lock = threading.Lock()
worker_started = False


def build_amazon_session() -> requests.Session:
    sess = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.25,
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def make_amazon_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.amazon.in/",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


def load_keywords_from_file(filepath: str = KEYWORDS_FILE_PATH) -> list:
    if not os.path.exists(filepath):
        return ["tshirt", "shirt", "socks", "kurti", "cap"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.read().strip()

        if not raw_content:
            return ["tshirt", "shirt", "socks", "kurti", "cap"]

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

            if not retry_forever:
                return False
            time.sleep(retry_after)
        except Exception:
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
            if 1 <= d_val <= 100:
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


def extract_price_and_discount(card_element, full_text: str):
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


def extract_product_info(item):
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


def build_loot_search_url(kw: str, page_no: int = 1) -> str:
    query = kw.strip().replace(" ", "+")
    url = (
        f"https://www.amazon.in/s?k={query}"
        f"&rh=p_n_free_shipping_eligible%3A1"
        f"&pct-off={MIN_DISCOUNT}-{MAX_DISCOUNT}"
    )
    if page_no > 1:
        url += f"&page={page_no}"
    return url


def scrape_amazon_page(session: requests.Session, kw: str, page_no: int = 1):
    url = build_loot_search_url(kw, page_no=page_no)
    resp = session.get(url, headers=make_amazon_headers(), timeout=12)
    code = resp.status_code

    if code != 200 or is_captcha_or_block_page(resp.text):
        err_tag = f"HTTP_{code}" if code != 200 else "BLOCK_CAPTCHA"
        return {"status": "bad", "err_tag": err_tag, "count": 0, "reason": "", "deals": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select('div[data-component-type="s-search-result"]')
    count = len(items)
    if count == 0:
        reason = classify_zero_items_reason(resp.text)
        del soup
        return {"status": "empty", "err_tag": "", "count": 0, "reason": reason, "deals": []}

    deals = []
    for item in items:
        text = item.get_text(" ", strip=True)
        if not text:
            continue
        lower_text = text.lower()
        if "currently unavailable" in lower_text or "page not found" in lower_text:
            continue

        title, link, asin = extract_product_info(item)
        if not title or not link:
            continue

        price, discount = extract_price_and_discount(item, text)
        free_del = has_free_delivery(text)

        # कीमत की कोई सीमा नहीं — बस 80% से 100% ऑफ और Free Delivery
        if not ((MIN_DISCOUNT <= discount <= MAX_DISCOUNT) and free_del):
            continue

        sig = f"asin:{asin}" if asin else f"{link.lower()}|{title.lower()[:70]}"
        legacy_sig = f"{link.lower()}|{title.lower()[:70]}"
        deals.append({
            "sig": sig,
            "legacy_sig": legacy_sig,
            "title": title,
            "price": price,
            "discount": discount,
            "link": link,
        })

    del soup
    return {"status": "ok", "err_tag": "", "count": count, "reason": "", "deals": deals}


def build_batch_report(
    batch_num: int,
    total_batches: int,
    start_idx: int,
    end_idx: int,
    ok_count: int,
    zero_count: int,
    bad_count: int,
    total_page_items: int,
    batch_deals: int,
    zero_items_detail: list,
    bad_items_detail: list,
    batch_kw_counts: list,
) -> str:
    batch_len = end_idx - start_idx
    lines = [
        f"📦 Batch Report ({batch_num}/{total_batches}) — Keywords #{start_idx+1} to {end_idx}",
        f"ℹ️ बैच {batch_num}/{total_batches} (#{start_idx+1}-{end_idx}): {ok_count}/{batch_len} नाम 200 OK गए, {zero_count} में 0 आइटम दिखे, {bad_count} में एरर।",
        f"• सही गए (200 OK): {ok_count}/{batch_len} | 0 आइटम: {zero_count} | एरर: {bad_count} | कुल पेज आइटम: {total_page_items} | नई लूट: {batch_deals}",
    ]

    if bad_items_detail:
        lines.append(f"• ❌ एरर वाले नाम [{len(bad_items_detail)}]: " + ", ".join(bad_items_detail[:12]))

    if zero_items_detail:
        lines.append(f"• ⚪ 0 आइटम वाले नाम [{len(zero_items_detail)}]: " + ", ".join(zero_items_detail[:8]))

    lines.append("\n📋 इस बैच के हर नाम पर चेक हुए आइटम:")
    for kw, cnt, d_cnt in batch_kw_counts:
        row_txt = f"• {kw}: {cnt} पेज आइटम" + (f" (🔥{d_cnt} लूट)" if d_cnt > 0 else " (0 लूट)")
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
    consecutive_bad = 0
    slowdown_remaining = 0
    session = build_amazon_session()

    try:
        for batch_idx in range(total_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_kw)
            batch_kws = keywords[start_idx:end_idx]

            ok_count = 0
            zero_count = 0
            bad_count = 0
            total_page_items = 0
            b_deals = 0
            zero_items_detail = []
            bad_items_detail = []
            batch_kw_counts = []

            for kw in batch_kws:
                kw_total_items = 0
                kw_deals_found = 0
                kw_had_bad = False
                kw_bad_tag = ""
                kw_had_ok = False
                kw_zero_reason = ""

                for page_no in range(1, max(1, MAX_PAGES) + 1):
                    try:
                        res = scrape_amazon_page(session, kw, page_no=page_no)
                        status = res["status"]
                        cnt = res["count"]

                        if status == "ok":
                            consecutive_bad = 0
                            kw_had_ok = True
                            kw_total_items += cnt

                            for d in res["deals"]:
                                sig = d["sig"]
                                legacy_sig = d["legacy_sig"]
                                if (sig in seen_deals) or (legacy_sig and legacy_sig in seen_deals):
                                    continue

                                price_txt = f"₹{d['price']}" if d["price"] is not None else "N/A"
                                msg = (
                                    f"🔥 AMAZON LOOT ({MIN_DISCOUNT}-{MAX_DISCOUNT}% OFF | ANY PRICE | FREE DELIVERY)\n\n"
                                    f"🔎 Keyword: {kw} (Page {page_no})\n"
                                    f"🛍️ {d['title'][:160]}\n"
                                    f"💰 Price: {price_txt} | 🏷️ Discount: {d['discount']}% | 🚚 Free Delivery: Yes\n"
                                    f"🔗 {d['link']}"
                                )
                                if send_telegram(msg, retry_forever=True):
                                    seen_deals[sig] = time.time()
                                    save_seen_deals(seen_deals)
                                    b_deals += 1
                                    kw_deals_found += 1
                                    time.sleep(0.2)

                            if page_no < MAX_PAGES:
                                time.sleep(PAGE_DELAY)

                        elif status == "empty":
                            consecutive_bad = 0
                            kw_had_ok = True
                            kw_zero_reason = res["reason"]
                            break

                        else:
                            kw_had_bad = True
                            kw_bad_tag = res["err_tag"]
                            consecutive_bad += 1
                            print(f"[Amazon {kw_bad_tag}] {kw} (page {page_no})")
                            session.close()
                            session = build_amazon_session()
                            break

                    except Exception as e:
                        kw_had_bad = True
                        kw_bad_tag = type(e).__name__
                        consecutive_bad += 1
                        print(f"[Amazon Error {kw} page {page_no}]: {e}")
                        session.close()
                        session = build_amazon_session()
                        break

                if kw_had_ok and kw_total_items == 0 and not kw_had_bad:
                    ok_count += 1
                    zero_count += 1
                    zero_items_detail.append(f"{kw} ({kw_zero_reason})")
                elif kw_had_ok:
                    ok_count += 1
                    total_page_items += kw_total_items
                elif kw_had_bad:
                    bad_count += 1
                    bad_items_detail.append(f"{kw} ({kw_bad_tag})")

                batch_kw_counts.append((kw, kw_total_items, kw_deals_found))

                if consecutive_bad >= MAX_CONSECUTIVE_BAD:
                    send_alert_safe(
                        f"⏸️ स्मार्ट ब्रेक सक्रिय!\n"
                        f"• Amazon पर लगातार {consecutive_bad} ब्लॉक/एरर आए (आखिरी: {kw_bad_tag})।\n"
                        f"• बॉट {COOLDOWN_SECONDS // 60} मिनट रुकेगा, फिर संभलकर चलेगा।"
                    )
                    time.sleep(COOLDOWN_SECONDS)
                    consecutive_bad = 0
                    slowdown_remaining = 30

                if slowdown_remaining > 0:
                    slowdown_remaining -= 1
                    time.sleep(0.25)
                elif KEYWORD_DELAY > 0:
                    time.sleep(KEYWORD_DELAY)

            overall_deals += b_deals
            batch_msg = build_batch_report(
                batch_num=batch_idx + 1,
                total_batches=total_batches,
                start_idx=start_idx,
                end_idx=end_idx,
                ok_count=ok_count,
                zero_count=zero_count,
                bad_count=bad_count,
                total_page_items=total_page_items,
                batch_deals=b_deals,
                zero_items_detail=zero_items_detail,
                bad_items_detail=bad_items_detail,
                batch_kw_counts=batch_kw_counts,
            )
            send_alert_safe(batch_msg)
            gc.collect()

    finally:
        session.close()
        gc.collect()

    send_alert_safe(
        f"🏁 Full Cycle Complete ({total_kw} Keywords)\n"
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
        send_alert_safe(
            f"🔥 Amazon Loot बॉट चालू हो गया!\n"
            f"• फ़िल्टर: {MIN_DISCOUNT}-{MAX_DISCOUNT}% OFF + ANY PRICE + Free Delivery\n"
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
    t = threading.Thread(target=background_worker, name="AmazonLootWorker")
    t.daemon = True
    t.start()
    run_flask()
