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
    return "Amazon 55-Keyword Loot Bot (Reliable Telegram Loot Retry + End-of-Cycle Report) Running!"

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
TELEGRAM_RETRY_DELAY = 2       # Telegram भेजने में एरर आए तो हर 2 सेकंड में दोबारा ट्राई

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/604.1",
]

RAW_KEYWORDS = [
    "steel glass", "steel plate", "steel bowl", "measuring spoon", "tea strainer",
    "kitchen towel", "dishwashing sponge", "scrubber pad", "bowl cover", "food cover",
    "fridge organizer", "fridge mat", "egg tray", "bottle brush", "sink brush",

    # Bijli, Phone & Rozmarra Ke Kaam
    "mobile holder", "charging cable", "earphone pouch", "cable clip", "switchboard sticker",
    "bulb holder", "two pin plug", "three pin plug", "fuse wire", "insulation tape",
    "led night bulb", "book light", "pocket torch", "velcro cable tie", "sim card tray pin",

    # Safai, Kapde & Personal Kaam
    "cloth clips", "laundry net bag", "shoe bag cover", "comb", "hair brush",
    "face tissue", "wet wipes", "hand wash refill", "soap case", "toothbrush stand",
    "cotton buds", "band aid", "safety pins", "sewing kit", "measuring tape pocket"
    
    "mobile phone", "smartphone", "keypad mobile", "headphones", "wireless headphones",
    "gaming headset", "bluetooth speaker", "mini speaker", "smartwatch", "fitness band",
    "charging dock", "wireless charger", "otg adapter", "type c cable", "aux cable",

    # Home & Kitchen Useful Items (नए वाले)
    "tiffin box", "steel tiffin", "insulated lunch box", "water dispenser", "tea kettle",
    "milk boiler", "dosa tawa", "chapati maker", "rotary chopper", "garlic chopper",
    "spice rack", "cutlery stand", "dish drying rack", "sink strainer", "sink mat",
    "bin bag", "dustbin", "pedal dustbin", "tissue holder", "paper roll holder",

    # Home Comfort, Lighting & Daily Utility
    "table lamp", "night lamp", "reading light", "emergency light", "rechargeable torch",
    "extension cord", "spike guard", "power strip", "wall hook", "adhesive hooks",
    "coat hanger", "pants hanger", "laundry basket", "foldable basket", "storage box",
    "plastic container set", "glass jar set", "airtight container", "ice tray", "water jug",

    # Grooming, Health & Personal Useful
    "trimmer", "beard trimmer", "nose trimmer", "epilator", "nail clipper",
    "foot scrubber", "pumice stone", "face roller", "gua sha", "lip balm",
    "sunscreen stick", "deodorant", "perfume", "body mist", "sanitizer"
    
    "tawa", "kadai", "frying pan", "saucepan", "grater",
    "peeler", "strainer", "rolling pin", "chopping board", "measuring cup",
    "spice box", "oil dispenser", "garlic press", "lemon squeezer", "egg beater",
    "whisk", "tongs", "spatula", "ladle", "colander",

    # Gardening & Outdoor Care
    "plant pot", "grow bag", "watering can", "garden hose", "pruning shears",
    "garden gloves", "fertilizer", "seeds pack", "coco peat", "sprinkler",
    "bird feeder", "outdoor light", "solar light", "pathway light", "insect trap",

    # Fitness, Sports & Active Gear
    "yoga mat", "resistance band", "skipping rope", "gym gloves", "hand gripper",
    "shaker bottle", "foam roller", "knee sleeve", "ankle support", "wrist wrap",
    "badminton shuttlecock", "table tennis balls", "football", "cricket ball", "swimming goggles",

    # Home Safety, Security & Utility
    "door lock", "padlock", "door stopper", "window lock", "safety latch",
    "smoke detector", "first aid kit", "digital thermometer", "bp monitor", "weighing scale",
    "digital scale", "magnifying glass", "battery charger", "aa batteries", "aaa batteries",

    # Storage, Organizers & Everyday Misc
    "wardrobe organizer", "drawer organizer", "under bed storage", "cloth cover", "saree cover",
    "jewellery box", "watch box", "sunglasses case", "glasses case", "cable organizer",
    "cord protector", "double sided tape", "duct tape", "zip ties", "velcro straps",

    # Auto, Bike & Utility Accessories
    "bike gloves", "seat cushion", "car sunshade", "car duster", "tire inflator",
    "jumper cable", "car tissue box", "keychain", "lanyard", "id card holder",

    # Pet Care & Misc Lifestyle
    "pet bowl", "dog leash", "pet collar", "pet grooming brush", "cat litter scoop",
    "earplugs", "eye mask", "neck pillow", "heating pad", "hot water bag",
    "ice pack", "shoe polish", "shoe brush", "lint remover", "clothes brush"
    
    "notebook", "diary", "pen set", "gel pens", "highlighter",
    "marker pens", "stapler", "calculator", "desk organizer", "study lamp",
    "whiteboard", "sticky notes", "file folder", "geometry box", "drawing book",

    # Tools, Hardware & Car/Bike Care
    "screwdriver set", "drill machine", "measuring tape", "allen key set", "glue gun",
    "soldering iron", "pliers", "hammer", "wrench set", "car phone holder",
    "car vacuum cleaner", "microfiber cloth", "bike cover", "helmet", "bike lock",

    # Bathroom & Cleaning
    "toilet brush", "bathroom mat", "shower curtain", "liquid detergent", "dishwash liquid",
    "floor cleaner", "glass cleaner", "garbage bags", "air freshener", "bath mat",

    # Travel, Bags & Storage
    "travel pouch", "toiletries bag", "duffle trolley", "passport holder", "luggage tags",
    "vacuum storage bags", "shoe rack", "shoe bag", "key holder", "hanger set",

    # Kids, Gifts & Home Decor
    "remote control car", "building blocks", "board game", "water gun", "piggy bank",
    "photo frame", "showpiece", "artificial plants", "candles", "table runner", 
    "mixer grinder", "hand blender", "electric kettle", "induction cooktop", "toaster",
    "sandwich maker", "air fryer", "microwave oven", "water purifier", "pressure cooker",
    "gas stove", "rice cooker", "chopper", "juicer mixer grinder", "coffee maker",

    # Home Appliances (Washing Machine, Cooler, etc.)
    "washing machine", "semi automatic washing machine", "fully automatic washing machine",
    "air cooler", "ceiling fan", "table fan", "pedestal fan", "room heater",
    "iron press", "steam iron", "vacuum cleaner", "led bulb", "extension board",

    # Home & Living / Daily Essentials
    "bedsheet", "double bedsheet", "pillow", "pillow cover", "curtains",
    "door mat", "bath towel", "blanket", "comforter", "mattress protector",
    "storage containers", "lunch box", "water bottle", "flask bottle", "soap dispenser",
    "laundry bag", "wall clock", "led strip light", "mosquito net", "mop",

    # Electronics & Gadgets
    "earbuds", "bluetooth earphones", "neckband", "power bank", "usb cable",
    "fast charger", "mobile stand", "mouse", "keyboard", "pendrive",
    "memory card", "ring light", "tripod", "smart bulb", "torch light",

    # Grooming, Health & Misc Utility
    "hair dryer", "hair straightener", "shaving kit", "razor blades", "body lotion",
    "hair oil", "shampoo", "conditioner", "toothpaste", "toothbrush",
    "umbrella", "raincoat", "backpack", "laptop bag", "tool kit", 
    "mens tshirts", "tshirt", "polo tshirt", "oversized tshirt", "compression tshirt",
    "henley tshirt", "round neck tshirt", "v neck tshirt", "full sleeve tshirt", "sleeveless tshirt",
    "gym tshirt men", "cotton tshirt men", "graphic tshirt men", "plain tshirt men", "striped tshirt men",
    "mens shirts", "formal shirt", "casual shirt", "linen shirt men", "denim shirt men",
    "checked shirt men", "flannel shirt men", "joggers for men", "track pants for men", "mens jeans",
    "slim fit jeans men", "cargo pants men", "chinos for men", "mens shorts", "denim shorts men",
    "cotton shorts men", "hoodies for men", "sweatshirts for men", "mens jackets", "bomber jacket men",
    "windcheater men", "kurta for men", "mens ethnic wear", "pathani kurta men", "nehru jacket men",
    "boxers for men", "briefs for men", "mens vest", "thermal wear men", "night suit men",
    "pajama for men", "dhoti kurta men", "tracksuit for men", "sweater for men", "cardigan men",
    "shoes for men", "running shoes men", "casual shoes men", "sneakers for men", "loafers men",
    "formal shoes men", "sports shoes men", "sandals for men", "slippers for men", "flip flops men",
    "clogs for men", "socks for men", "ankle socks", "crew socks men", "no show socks men",
    "belts for men", "leather belt men", "wallets for men", "leather wallet men", "caps for men",
    "baseball cap men", "beanie cap", "sunglasses for men", "watch for men", "smartwatch men",
    "backpack for men", "messenger bag men", "duffel bag men", "gym bag men", "tie for men",
    "handkerchief men", "muffler for men", "gloves for men", "earphones men", "trimmer for men",
    "face wash", "mens face wash", "womens face wash", "salicylic acid face wash", "niacinamide face wash",
    "vitamin c face wash", "charcoal face wash", "neem face wash", "foaming face wash", "gel face wash",
    "acne face wash", "oil control face wash", "brightening face wash", "gentle face wash", "face cleanser",
    "face scrub", "lip balm", "moisturizer face", "sunscreen lotion", "toner face",
    "womens clothing", "womens tops", "crop tops women", "womens tshirts", "oversized tshirt women",
    "womens shirts", "tunics for women", "kurtis for women", "kurti set women", "anarkali kurti",
    "straight kurti", "leggings for women", "jeggings for women", "womens jeans", "wide leg jeans women",
    "palazzo for women", "womens joggers", "womens track pants", "womens shorts", "skirts for women",
    "womens hoodies", "womens sweatshirts", "womens jackets", "cardigan for women", "sweater for women",
    "dresses for women", "maxi dress women", "midi dress women", "bodycon dress women", "sarees for women",
    "lehenga for women", "dupatta for women", "nightwear for women", "co ord set women", "shrug for women",
    "shoes for women", "running shoes women", "casual shoes women", "sneakers women", "walking shoes women",
    "heels for women", "block heels women", "flats for women", "bellies for women", "sandals for women",
    "slippers women", "flip flops women", "socks for women", "ankle socks women", "handbags for women",
    "sling bags women", "tote bag women", "backpack for women", "clutch bag women", "wallets for women",
    "sunglasses for women", "watch for women", "jewellery set women", "earrings for women", "necklaces women",
    "bangles for women", "hair clips women", "scrunchies women", "scarf for women", "dupatta set"
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
KEYWORDS = list(dict.fromkeys(RAW_KEYWORDS))
seen_deals = {}

def cleanup_old_seen_deals():
    now = time.time()
    expired_keys = [k for k, ts in seen_deals.items() if (now - ts) >= SEEN_EXPIRY_SECONDS]
    for k in expired_keys:
        del seen_deals[k]
    if expired_keys:
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

            # Telegram ने 429 (Too Many Requests) दिया हो तो retry_after सम्मान करें
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

def extract_strict_product_info(item):
    title_el = item.select_one("h2 span")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    if not title or len(title) < 4:
        return None, None

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
                print(f"[Status 403] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code == 503:
                err_503_keywords.append(kw)
                print(f"[Status 503] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue
            elif code != 200:
                other_err_keywords.append(f"{kw} (HTTP {code})")
                print(f"[Status {code}] {kw}")
                time.sleep(KEYWORD_DELAY)
                continue

            if is_captcha_or_block_page(resp.text):
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

                title, link = extract_strict_product_info(item)
                if not title or not link:
                    continue

                sig = f"{link.lower()}|{title.lower()[:70]}"
                if sig in seen_deals:
                    continue

                msg = (
                    f"👕👟 TRIPLE LOOT (90%+ OFF | <=₹100 | FREE DELIVERY)\n\n"
                    f"🔍 Keyword: {kw}\n"
                    f"📦 {title[:160]}\n"
                    f"💰 Price: ₹{price} | 🏷️ Discount: {discount}% | 🚚 Free Delivery: Yes\n"
                    f"🔗 {link}"
                )

                # Telegram भेजने में कोई भी एरर आए तो सफल होने तक दोबारा ट्राई करेगा
                sent_ok = send_telegram(msg, retry_forever=True)
                if sent_ok:
                    seen_deals[sig] = time.time()
                    deals_sent += 1
                time.sleep(0.4)

        except Exception as e:
            other_err_keywords.append(f"{kw} ({type(e).__name__})")
            print(f"[Error {kw}]: {e}")

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
        send_telegram(report_msg, retry_forever=False)
    else:
        send_telegram(report_msg[:3950] + "\n... (रिपोर्ट लंबी होने पर आगे का हिस्सा कटा)", retry_forever=False)

def background_worker():
    print("🚀 Render 55-Keyword Loot Bot Started (Telegram Loot Retry + End-of-Cycle Report)...")
    send_telegram(
        f"🚀 सर्चिंग चालू हो गई है!\n"
        f"• कुल कीवर्ड्स: {len(KEYWORDS)}\n"
        f"• फ़िल्टर: 90%+ ऑफ + ₹100 या उससे कम (असली प्राइस) + फ्री डिलीवरी + साफ टाइटल व /dp/ लिंक\n"
        f"• लूट भेजते वक्त Telegram में कोई भी एरर आए तो सफल होने तक दोबारा ट्राई होगा, {KEYWORD_DELAY}s गैप रहेगा, और 55 कीवर्ड्स/चक्र पूरा होने पर रिपोर्ट आएगी।"
    )
    while True:
        scan_once()
        time.sleep(LOOP_DELAY)

if __name__ == "__main__":
    t = threading.Thread(target=background_worker)
    t.daemon = True
    t.start()
    run_flask()
