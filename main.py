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
    return "Amazon Loot Bot (5 Smart Upgrades + 50-KW Batch Item Counts) Running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)


TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID", "")

# GitHub रेपो के अंदर कीवर्ड्स फ़ाइल का रास्ता
KEYWORDS_FILE_PATH = os.environ.get("KEYWORDS_FILE", "keywords/keywords.txt")
# Telegram में आ चुकी डील्स सेव करने वाली फ़ाइल का रास्ता
SEEN_DEALS_FILE_PATH = os.environ.get("SEEN_DEALS_FILE", "data/seen_deals.json")

MIN_DISCOUNT = 90              # 90% या उससे ज़्यादा ऑफ़
MAX_PRICE = 100                # ₹100 या उससे कम
BATCH_SIZE = 50                # हर 50 कीवर्ड के बाद बैच रिपोर्ट
LOOP_DELAY = 600               # पूरा साइकिल खत्म होने के बाद 10 मिनट (600 सेकंड) का इंतज़ार
KEYWORD_DELAY = 1              # हर कीवर्ड सर्च के बाद 4 सेकंड का गैप
SEEN_EXPIRY_DAYS = 20          # 20 दिन तक वही डील दोबारा नहीं आएगी
SEEN_EXPIRY_SECONDS = SEEN_EXPIRY_DAYS * 86400
TELEGRAM_RETRY_DELAY = 2       # Telegram भेजने में एरर आए तो 2 सेकंड में दोबारा ट्राई
MAX_CONSECUTIVE_BAD = 5        # लगातार 5 ब्लॉक/एरर पर स्मार्ट ब्रेक
COOLDOWN_SECONDS = 900         # 15 मिनट (900 सेकंड) का कूल-डाउन ब्रेक

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

file_io_lock = threading.Lock()
worker_lock = threading.Lock()
worker_started = False


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
            if isinstance(data, list):
                items = [str(x).strip() for x in data if str(x).strip()]
            else:
                items = []
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
    ]
    return any(p in t for p in block_phrases)


def classify_zero_items_reason(html_text: str) -> str:
    """बदलाव #1: 200 OK आने के बाद भी 0 आइटम दिखने की असली वजह बताता है।"""
    t = html_text.lower()
    no_res_phrases = [
        "no results for",
        "0 results for",
        "did not match any products",
        "try checking your spelling",
    ]
    if any(p in t for p in no_res_phrases):
        return "कोई रिजल्ट नहीं"
    if "something went wrong" in t or "sorry!" in t:
        return "Amazon एरर पेज"
    return "अलग लेआउट/खाली पेज"


def extract_real_price_and_discount(card_element, full_text: str):
    """बदलाव #4: स्ट्राइक-थ्रू MRP और /count को छोड़कर असली सेल प्राइस निकालता है।"""
    main_prices = []
    for el in card_element.select('.a-price:not([data-a-strike="true"]) .a-offscreen'):
        raw = el.get_text(" ", strip=True)
        parent_ctx = el.parent.parent.get_text(" ", strip=True).lower() if el.parent and el.parent.parent else ""
        if any(unit in parent_ctx for unit in ["/ count", "/count", "/ pair", "/pair", "/ pack", "/pack", "/ piece"]):
            continue
        m = re.findall(r"₹\s*[\d,]+(?:\.\d+)?", raw)
        for num_str in m:
            try:
                val = int(float(num_str.replace("₹", "").replace(",", "").strip()))
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
        for num_str in re.findall(r"₹\s*[\d,]+", cleaned_for_price):
            try:
                val = int(num_str.replace("₹", "").replace(",", "").strip())
                if val > 0:
                    main_prices.append(val)
            except ValueError:
                pass

    real_price = main_prices[0] if main_prices else None

    discounts = []
    for d in re.findall(r"\(?\s*(\d{1,3})\s*%\s*off\s*\)?", full_text, flags=re.IGNORECASE):
        try:
            d_val = int(d)
            if 1 <= d_val <= 99:
                discounts.append(d_val)
        except ValueError:
            pass

    max_discount = max(discounts) if discounts else 0
    return real_price, max_discount


def has_free_delivery(text: str) -> bool:
    t = text.lower()
    return ("free delivery" in t) or ("free shipping" in t)


def extract_asin_from_link(link: str) -> str:
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", link, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_strict_product_info(item):
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
                if asin:
                    product_link = f"https://www.amazon.in/dp/{asin}"
                else:
                    product_link = clean
                break

    if not product_link:
        return None, None, ""

    return title, product_link, asin


def build_batch_report(
    batch_num: int,
    total_batches: int,
    start_idx: int,
    end_idx: int,
    batch_ok: int,
    batch_403: list,
    batch_503: list,
    batch_blocked: list,
    batch_other_err: list,
    batch_empty: list,
    batch_deals: int,
    batch_kw_counts: list,
) -> str:
    """बदलाव #2: हर 50 कीवर्ड पूरे होने पर उसी बैच रिपोर्ट में हर कीवर्ड के पेज आइटम्स बताता है।"""
    batch_len = end_idx - start_idx
    err_403_n = len(batch_403)
    err_503_n = len(batch_503)
    blk_n = len(batch_blocked)
    oth_n = len(batch_other_err)
    emp_n = len(batch_empty)
    total_bad = err_403_n + err_503_n + blk_n + oth_n
    total_items_in_batch = sum(c for _, c, _ in batch_kw_counts)

    if total_bad == 0 and emp_n == 0:
        status_line = f"✅ बैच {batch_num}/{total_batches} (#{start_idx+1}-{end_idx}): सभी {batch_len} नाम एकदम सही (200 OK) गए!"
    elif total_bad == 0:
        status_line = f"ℹ️ बैच {batch_num}/{total_batches} (#{start_idx+1}-{end_idx}): {batch_ok}/{batch_len} नाम 200 OK गए, {emp_n} में 0 आइटम दिखे।"
    else:
        status_line = (
            f"🚨 बैच {batch_num}/{total_batches} (#{start_idx+1}-{end_idx}) में गड़बड़ी:\n"
            f"• 200 OK: {batch_ok}/{batch_len} | 403: {err_403_n} | 503: {err_503_n} | ब्लॉक/कैप्चा: {blk_n} | अन्य एरर: {oth_n}"
        )

    lines = [
        f"📦 Batch Report ({batch_num}/{total_batches}) — Keywords #{start_idx+1} to {end_idx}",
        status_line,
        f"• सही गए (200 OK): {batch_ok}/{batch_len} | 0 आइटम: {emp_n} | कुल पेज आइटम: {total_items_in_batch} | नई लूट: {batch_deals}",
    ]

    if batch_403:
        lines.append(f"• ❌ 403 (Amazon ब्लॉक) [{err_403_n}]: {', '.join(batch_403[:15])}")
    if batch_503:
        lines.append(f"• ❌ 503 (सर्वर बिज़ी) [{err_503_n}]: {', '.join(batch_503[:15])}")
    if batch_blocked:
        lines.append(f"• ❌ कैप्चा/रोबोट चेक [{blk_n}]: {', '.join(batch_blocked[:15])}")
    if batch_other_err:
        lines.append(f"• ❌ अन्य एरर [{oth_n}]: {', '.join(batch_other_err[:15])}")
    if batch_empty:
        lines.append(f"• ⚪ 0 आइटम वाले नाम [{emp_n}]: {', '.join(batch_empty[:20])}")

    if batch_kw_counts:
        lines.append(f"\n📋 इस बैच के हर नाम पर एक पेज में आए आइटम:")
        for kw, cnt, d_cnt in batch_kw_counts:
            item_line = f"• {kw}: {cnt} आइटम" + (f" (🔥 {d_cnt} लूट)" if d_cnt > 0 else "")
            current_len = sum(len(x) + 1 for x in lines)
            if current_len + len(item_line) > 3880:
                lines.append("... (टेलीग्राम लिमिट के कारण बाकी नाम कटे)")
                break
            lines.append(item_line)

    report = "\n".join(lines)
    if len(report) > 3950:
        report = report[:3940] + "\n... (लिमिट लंबी होने पर कटी)"
    return report


def scan_once():
    global seen_deals
    if not seen_deals:
        seen_deals = load_seen_deals()
    cleanup_old_seen_deals()

    keywords = load_keywords_from_file(KEYWORDS_FILE_PATH)
    total_kw = len(keywords)
    if total_kw == 0:
        send_alert_safe(
            f"⚠️ '{KEYWORDS_FILE_PATH}' में कोई कीवर्ड नहीं मिला!\n"
            f"• GitHub प्रोजेक्ट में फ़ाइल बनाकर कीवर्ड्स डालें।"
        )
        return

    total_batches = (total_kw + BATCH_SIZE - 1) // BATCH_SIZE

    overall_200 = 0
    overall_403 = 0
    overall_503 = 0
    overall_blocked = 0
    overall_other_err = 0
    overall_empty = 0
    overall_deals = 0
    overall_scanned_items = 0
    consecutive_bad = 0

    session = requests.Session()

    try:
        for batch_idx in range(total_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_kw)
            batch_kws = keywords[start_idx:end_idx]

            b_ok = 0
            b_403 = []
            b_503 = []
            b_blocked = []
            b_other = []
            b_empty = []
            b_deals = 0
            b_kw_counts = []

            for kw in batch_kws:
                query = kw.strip().replace(" ", "+")
                base_url = f"https://www.amazon.in/s?k={query}"
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.amazon.in/",
                }

                soup = None
                resp = None
                kw_item_count = 0
                kw_deals_count = 0
                is_bad_request = False

                try:
                    resp = session.get(base_url, headers=headers, timeout=12)
                    code = resp.status_code

                    if code == 403:
                        b_403.append(kw)
                        is_bad_request = True
                        print(f"[Status 403] {kw}")
                    elif code == 503:
                        b_503.append(kw)
                        is_bad_request = True
                        print(f"[Status 503] {kw}")
                    elif code != 200:
                        b_other.append(f"{kw} (HTTP {code})")
                        is_bad_request = True
                        print(f"[Status {code}] {kw}")
                    elif is_captcha_or_block_page(resp.text):
                        b_blocked.append(kw)
                        is_bad_request = True
                        print(f"[Captcha/Blocked on 200] {kw}")
                    else:
                        consecutive_bad = 0
                        b_ok += 1
                        soup = BeautifulSoup(resp.text, "html.parser")
                        items = soup.select('div[data-component-type="s-search-result"]')
                        kw_item_count = len(items)
                        overall_scanned_items += kw_item_count

                        if kw_item_count == 0:
                            reason = classify_zero_items_reason(resp.text)
                            b_empty.append(f"{kw} ({reason})")
                            print(f"[0 Items on 200] {kw} -> {reason}")
                        else:
                            print(f"[Items] {kw}: {kw_item_count} आइटम")
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

                                title, link, asin = extract_strict_product_info(item)
                                if not title or not link:
                                    continue

                                # बदलाव #5: ASIN + पुरानी signature दोनों से डुप्लीकेट जाँच
                                legacy_sig = f"{link.lower()}|{title.lower()[:70]}"
                                asin_sig = f"asin:{asin}" if asin else legacy_sig

                                if (asin_sig in seen_deals) or (legacy_sig in seen_deals):
                                    continue

                                msg = (
                                    f"🔥 TRIPLE LOOT (90%+ OFF | <=₹100 | FREE DELIVERY)\n\n"
                                    f"🔎 Keyword: {kw} (पेज आइटम: {kw_item_count})\n"
                                    f"🛍️ {title[:160]}\n"
                                    f"💰 Price: ₹{price} | 🏷️ Discount: {discount}% | 🚚 Free Delivery: Yes\n"
                                    f"🔗 {link}"
                                )

                                sent_ok = send_telegram(msg, retry_forever=True)
                                if sent_ok:
                                    seen_deals[asin_sig] = time.time()
                                    save_seen_deals(seen_deals)
                                    b_deals += 1
                                    kw_deals_count += 1
                                    time.sleep(0.4)

                except Exception as e:
                    b_other.append(f"{kw} ({type(e).__name__})")
                    is_bad_request = True
                    print(f"[Error {kw}]: {e}")
                finally:
                    del soup
                    del resp

                b_kw_counts.append((kw, kw_item_count, kw_deals_count))

                # बदलाव #3: लगातार 5 ब्लॉक/एरर पर 15 मिनट का स्मार्ट कूल-डाउन ब्रेक
                if is_bad_request:
                    consecutive_bad += 1
                    if consecutive_bad >= MAX_CONSECUTIVE_BAD:
                        send_alert_safe(
                            f"⏸️ स्मार्ट ब्रेक सक्रिय!\n"
                            f"• लगातार {consecutive_bad} रिक्वेस्ट में ब्लॉक/एरर आया।\n"
                            f"• IP बचाने के लिए बॉट अब {COOLDOWN_SECONDS // 60} मिनट रुकेगा, फिर आगे बढ़ेगा।"
                        )
                        time.sleep(COOLDOWN_SECONDS)
                        consecutive_bad = 0
                else:
                    consecutive_bad = 0

                time.sleep(KEYWORD_DELAY)

            overall_200 += b_ok
            overall_403 += len(b_403)
            overall_503 += len(b_503)
            overall_blocked += len(b_blocked)
            overall_other_err += len(b_other)
            overall_empty += len(b_empty)
            overall_deals += b_deals

            batch_msg = build_batch_report(
                batch_num=batch_idx + 1,
                total_batches=total_batches,
                start_idx=start_idx,
                end_idx=end_idx,
                batch_ok=b_ok,
                batch_403=b_403,
                batch_503=b_503,
                batch_blocked=b_blocked,
                batch_other_err=b_other,
                batch_empty=b_empty,
                batch_deals=b_deals,
                batch_kw_counts=b_kw_counts,
            )
            send_alert_safe(batch_msg)
            gc.collect()

    finally:
        session.close()
        gc.collect()

    total_issues = overall_403 + overall_503 + overall_blocked + overall_other_err
    if total_issues == 0:
        health_line = "✅ पूरा चक्र एकदम सही रहा, कोई 403 / 503 / कैप्चा या अन्य एरर नहीं आया।"
    else:
        health_line = (
            f"⚠️ पूरे चक्र में दिक्कतें रहीं:\n"
            f"• 403:{overall_403}, 503:{overall_503}, ब्लॉक/कैप्चा:{overall_blocked}, अन्य एरर:{overall_other_err}"
        )

    final_report = (
        f"🏁 Full Cycle Complete ({total_kw} Keywords in {total_batches} Batches)\n"
        f"{health_line}\n"
        f"• कुल 200 OK: {overall_200}/{total_kw} | 0 आइटम: {overall_empty}\n"
        f"• पूरे राउंड में कुल स्कैन आइटम: {overall_scanned_items}\n"
        f"• कुल नई लूट भेजी गई: {overall_deals}\n"
        f"• अब {LOOP_DELAY // 60} मिनट बाद अगला राउंड होगा।"
    )
    send_alert_safe(final_report)


def background_worker():
    global worker_started
    with worker_lock:
        if worker_started:
            return
        worker_started = True

    try:
        initial_kws = load_keywords_from_file(KEYWORDS_FILE_PATH)
        print(f"Render Loot Bot Started ({len(initial_kws)} Keywords from {KEYWORDS_FILE_PATH})...")
        send_alert_safe(
            f"🤖 बॉट चालू हो गया है!\n"
            f"• कीवर्ड फ़ाइल: {KEYWORDS_FILE_PATH} ({len(initial_kws)} कीवर्ड्स)\n"
            f"• Seen डील फ़ाइल: {SEEN_DEALS_FILE_PATH} ({SEEN_EXPIRY_DAYS} दिन तक दोबारा नहीं आएंगी)\n"
            f"• हर {BATCH_SIZE} कीवर्ड्स पर बैच रिपोर्ट में हर नाम के पेज आइटम्स की गिनती आएगी।"
        )

        cycle_no = 0
        while True:
            cycle_no += 1
            try:
                scan_once()
            except Exception as cycle_err:
                tb_short = traceback.format_exc()[-900:]
                send_alert_safe(
                    f"⚠️ रन #{cycle_no} में गड़बड़/एरर आया:\n"
                    f"• एरर: {type(cycle_err).__name__}: {cycle_err}\n"
                    f"• Trace:\n{tb_short}"
                )
                time.sleep(10)
                continue

            time.sleep(LOOP_DELAY)

    except Exception as fatal_err:
        tb_fatal = traceback.format_exc()[-900:]
        send_alert_safe(
            f"🛑 बॉट वर्कर डेड हो गया:\n"
            f"• एरर: {type(fatal_err).__name__}: {fatal_err}\n"
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
