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

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 3. TELEGRAM /START COMMAND
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    global current_query
    status_msg = (
        "🔥 **Loot Scraper Bot is Active & Hunting!**\n\n"
        f"🔍 **Currently Checking:** `{current_query}`\n\n"
        "⚡ **Target:** 90%+ OFF OR Under ₹100 Glitch Deals!\n"
        "सारे सिस्टम चालू हैं भाई, नजर पूरी गड़ी हुई है। 🚀"
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
# 4. SCRAPER LOGIC & USER AGENTS
# ==========================================
CHROME_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]

CLOTHING_NAMES = [
    # --- TOP APPAREL & BRANDED JEANS (जींस और कपड़े) ---
    "levis mens slim fit jeans",
    "wrangler cotton stretch jeans",
    "lee cooper casual denim jeans",
    "pepe jeans london slim fit",
    "jack and jones stylish jeans",
    "zara men casual trousers",
    "h and m mens cotton shirt",
    "allen solly formal shirt men",
    "van heusen casual printed shirt",
    "peter england party wear shirt",
    "louis philippe premium shirt",
    "puma athletic hoodie men",
    "nike sportswear sweatshirt",
    "adidas originals cotton tee",
    "zara mens winter jacket",
    "killer stretchable denim jeans",
    "mufti casual checked shirt",
    "spykar fashion slim jeans",
    "flying machine cotton jacket",
    "roadster hooded sweatshirt",
    "snitch oversized stylish shirt",
    "blackberrys casual blazer men",
    "raymond unstitched suit fabric",

    # --- CAPS & HATS (टोपी) ---
    "nike sportswear baseball cap",
    "adidas training running cap",
    "puma motorsport snapback cap",
    "under armour golf cap",
    "reebok classic cotton cap",
    "wildcraft sun protection cap",
    "columbia outdoor hiking hat",
    "fastrack stylish snapback cap",
    "hrx gym training cap",
    "roadster casual trucker cap",

    # --- SUNGLASSES & EYEWEAR (चश्मे) ---
    "ray-ban aviator classic sunglasses",
    "oakley sports cycling sunglasses",
    "fastrack uv protected sunglasses",
    "vincent chase wayfarer sunglasses",
    "john jacobs titanium eyeglasses",
    "idee stylish sunglasses for men",
    "polaroid polarized driving sunglasses",
    "carrera premium fashion sunglasses",
    "fastrack pilot sunglasses",
    "royal son retro square sunglasses",

    # --- KITCHEN: COOKER & KADHAI (कुकर और कड़ाही) ---
    "prestige svachh pressure cooker 5l",
    "hawkins classic aluminium pressure cooker",
    "hawkins futura hard anodized kadhai",
    "pigeon non-stick aluminium kadhai",
    "butterfly induction base pressure cooker",
    "vinod stainless steel deep kadhai",
    "stahl triply engineered kadhai",
    "prestige omega deluxe granite kadhai",
    "milton insulated steel casserole",
    "pigeon heavy duty pressure cooker 3l",
    "wonderchef granite non-stick kadhai",
    "cello stainless steel pressure cooker",
    "bergner triply stainless steel kadhai",
    "lifelong aluminium pressure cooker",
    "hazel non stick kadhai with lid",

    # --- FOOTWEAR & SNEAKERS (जूते) ---
    "nike air max sports shoes",
    "adidas ultraboost running shoes",
    "puma nitro running shoes",
    "skechers slip-ins walking shoes",
    "asics gt running shoes",
    "red tape leather formal shoes",
    "woodland leather outdoor boots", 
    "nike sports shoes men",
    "adidas originals sneakers",
    "puma motorsport shoes",
    "reebok classic sneakers",
    "skechers memory foam shoes",
    "asics gel running shoes",
    "under armour sports shoes",
    "hrx running shoes men",
    "campus activewear shoes men",
    "sparx running sandals men",
    "bata formal shoes men",
    "red tape casual leather shoes",
    "woodland waterproof boots",
    "crocs classic clogs unisex",
    "fila sports shoes clearance",
    "lotto running shoes men",
    "paragon sports sandals",
    "relaxo slippers men",
    "hush puppies formal shoes",
    "metro shoes sale",
    "asian running shoes light",
    "liberty formal shoes men",
    "clarks leather shoes",
    "mochi casual shoes men",
    "vkc pride sandals",
    "action school shoes",
    "parx casual sneakers",
    "killer mens shoes",
    "provogue leather shoes",
    "red chief safety boots",

    # --- APPAREL & JEANS (टी-शर्ट, जींस, शर्ट) ---
    "nike dry-fit t shirt",
    "adidas cotton t shirt",
    "puma graphic tee men",
    "levis mens regular fit jeans",
    "wrangler denim jeans men",
    "lee cooper casual shirts",
    "pepe jeans london men",
    "u.s. polo assn cotton shirt",
    "allen solly formal trousers",
    "van heusen corporate shirt",
    "peter england formal suit",
    "louis philippe blazers men",
    "arrow formal shirt men",
    "park avenue formal wear",
    "blackberrys wedding blazer",
    "raymond formal suit fabric",
    "killer stylish jeans men",
    "mufti cotton casual shirt",
    "spykar stretchable jeans",
    "flying machine denim jacket",
    "zara men stylish jacket",
    "jack and jones jeans men",
    "snitch oversized t shirt men",
    "bewakoof printed graphic t shirt",
    "souled store superhero t shirt",
    "beyoung casual cotton shirt",
    "roadster denim jacket men",
    "lymio casual stylish shirt",
    "urbano fashion slim jeans",
    "campus sutra oversized tee",
    "veirdo cotton printed t shirt",
    "zivame women innerwear",
    "jockey gym vest for men",
    "van heusen innerwear trunk",
    "biba ethnic suit set women",
    "aurelia printed kurti set",
    "w for woman fusion wear",
    "fabindia cotton kurta men",
    "manyavar ethnic wear men",
    "rangriti kurti set",
    "global desi ethnic dress",

    # --- WATCHES, BELTS & ACCESSORIES (घड़ी, बेल्ट, कवर) ---
    "fastrack stylish wrist watch",
    "titan neo analog watch men",
    "casio vintage gold watch",
    "fossil chronograph watch men",
    "sonata gold dial watch",
    "timex classic leather watch",
    "boat smartwatch bluetooth",
    "fire-boltt smart watch call",
    "noise colorfit pulse watch",
    "fastrack reflex smartwatch",
    "titan smart watch men",
    "amazefit active smartwatch",
    "realme techlife watch",
    "dzoopo smart watch",
    "fire-boltt ninja call pro",
    "levi's leather belt for men",
    "wildcraft reversible belt",
    "allen solly formal leather belt",
    "peter england leather belt",
    "blackberrys leather belt",
    "wildcraft laptop backpack",
    "skybags trolley bag sale",
    "american tourister rucksack",
    "safari anti theft backpack",
    "uppercase anti-water backpack",
    "aristocrat travel duffel bag",
    "killer stylish backpack",
    "puma training gym bag",
    "nike sportswear backpack",
    "wildcraft rucksack 55l",

    # --- HEADPHONES & EARBUDS (हेडफोन, ईयरबड्स) ---
    "boat rockerz neckband bluetooth",
    "jbl wireless speaker waterproof",
    "boult audio tws earbuds",
    "oneplus bullet wireless z2",
    "realme buds wireless",
    "ptron bassbuds tws",
    "truke fitbuds earbuds",
    "ambrane bassband earphones",
    "sony wireless over-ear headphones",
    "bose quietcomfort headphones",
    "jbl tune active noise cancelling",
    "sennheiser hd series headphone",
    "boat immortal gaming earphone",
    "zebronics bluetooth soundbar",
    "portronics portable speaker",
    "marshall bluetooth speaker",
    "pigeon portable speaker",
    "infinity jbl club speaker",
    "philips bass wireless headset",
    "panasonic ergonomic earphones",

    # --- MOBILE COVERS & ACCESSORIES (मोबाइल कवर) ---
    "spigen rugged armor case iphone",
    "ringke fusion shockproof cover",
    "nilkin textured slim case",
    "dailyobjects designer phone cover",
    "zapcase liquid silicone case",
    "kavالب protective back cover",
    "the flap house leather case",
    "solvo armor kickstand cover",
    "wapcase clear transparent case",
    "caseology parallax sleek cover",
    "supcase heavy duty beetle case",
    "urban armor gear uag case",
    "otterbox defender series case",
    "mofi flip leather wallet case",
    "beyours magnetic magsafe cover",
    "realme gt neo back cover",
    "redmi note pro armor case",
    "samsung galaxy ultra glass case",
    "oneplus nord rugged back cover",
    "iphone silicone soft case",

    # --- MIXIE & KITCHEN APPLIANCES (मिक्सर ग्राइंडर) ---
    "prestige mixer grinder 750w",
    "butterfly smart mixer grinder",
    "pigeon special mixer grinder",
    "bosch true mixx mixer grinder",
    "sujata dynamix mixer grinder",
    "philips hl series mixer grinder",
    "lifelong power pro mixer grinder",
    "bajaj rex mixer grinder 500w",
    "maharaja whiteline turbo mix",
    "havells maxia mixer grinder",
    "crompton ozone mixer grinder",
    "wonderchef regalia mixer grinder",
    "boss classic mixer grinder",
    "panasonic heavy duty mixer",
    "kenstar cognito mixer grinder",
    "morphy richards icon super",
    "usha mg-2053 mixer grinder",
    "black+decker mixer grinder",
    "solaris mixer grinder 3 jar",
    "electrohelp juicer mixer grinder",

    # --- WASHING MACHINES (वाशिंग मशीन) ---
    "samsung 7kg fully automatic washing machine",
    "lg 8kg front load washing machine",
    "whirlpool 7.5kg semi automatic machine",
    "godrej 6.2kg top load washing machine",
    "bosch 7kg front load washer",
    "ifb 6.5kg smart washing machine",
    "panasonic 8kg wifi washing machine",
    "haier 6kg top load machine",
    "voltas beko 7kg semi automatic",
    "motorola 7kg front load washer",
    "sansui 6.5kg top load machine",
    "mitashi semi automatic washer",
    "blue star top load washing machine",
    "videocon 7kg washing machine",
    "amazonbasics 6.5kg top load machine",
    "realme techlife washing machine",
    "marQ by flipkart washing machine",
    "onida royal 7kg washing machine",
    "kelvinator semi automatic washer",
    "orient electric washing machine",

    # --- AIR CONDITIONERS - AC (एसी) ---
    "voltas 1.5 ton 3 star inverter ac",
    "lg dual inverter split ac 1.5 ton",
    "daikin 1.5 ton 5 star inverter ac",
    "samsung windfree split ac 1.5 ton",
    "blue star 1.5 ton 3 star ac",
    "carrier 1.5 ton inverter split ac",
    "godrej 1.5 ton 3 star split ac",
    "hitachi 1.5 ton 5 star inverter ac",
    "panasonic wi-fi inverter smart ac",
    "whirlpool 1.5 ton magiccool ac",
    "haier 1.5 ton frost-free inverter ac",
    "lloyd 1.5 ton 3 star wi-fi ac",
    "toshiba 1.5 ton split inverter ac",
    "ifb fast-cool inverter split ac",
    "lg window ac 1.5 ton 3 star",
    "voltas window ac 1 ton 5 star",
    "blue star window ac 1.5 ton",
    "samsung window air conditioner",
    "carrier window ac 1.5 ton",
    "orient electric split inverter", 
    "nike sports shoes men",
    "adidas originals sneakers",
    "puma motorsport shoes",
    "skechers memory foam shoes",
    "levis mens regular fit jeans",
    "wrangler denim jeans men",
    "snitch oversized t shirt men",
    "fastrack stylish wrist watch",
    "boat smartwatch bluetooth",
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
                    send_alert_to_telegram(f"🚨 Amazon ने IP ब्लॉक कर दी है (503 Error)!\n🔍 आखिरी चेक किया गया कपड़ा: {query}\nबॉट नया सेशन ले रहा है...")
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
                    
                    # दाम (Price) ढूंढने का सिस्टम
                    price_tag = product.select_one("span.a-price span.a-offscreen") or product.select_one("span.a-price-whole")
                    actual_price = None

                    if price_tag:
                        price_str = price_tag.get_text(strip=True).replace("₹", "").replace(",", "")
                        price_match = re.search(r"\d+", price_str)
                        if price_match:
                            actual_price = int(price_match.group())

                    # डिस्काउंट (%) ढूंढने का सिस्टम
                    match = re.search(r"(\d+)%\s+off", full_text, flags=re.IGNORECASE)
                    discount_val = int(match.group(1)) if match else 0

                    # --- 🎯 कड़क लूट फ़िल्टर लॉजिक ---
                    # 1. या तो दाम ₹100 से कम हो (₹5, ₹10, ₹50... कुछ भी)
                    is_under_100 = actual_price is not None and actual_price <= 100
                    # 2. या फिर डिस्काउंट 90% या उससे ज्यादा हो (चाहे दाम कुछ भी हो)
                    is_mega_discount = discount_val >= 90

                    if is_under_100 or is_mega_discount:
                        title_tag = product.select_one("h2 a span") or product.select_one("h2 span") or product.select_one("span.a-text-normal")
                        title = title_tag.get_text(strip=True) if title_tag else "Clothing Item"

                        asin_val = product.get("data-asin")
                        link = f"https://www.amazon.in/dp/{asin_val}"
                        price_display = f"₹{actual_price}" if actual_price is not None else "Check Link"
                        
                        if is_under_100 and is_mega_discount:
                            deal_type = f"🔥 MEGA GLITCH & {discount_val}% OFF LOOT!"
                        elif is_under_100:
                            deal_type = "🔥 UNDER-₹100 PRICE GLITCH!"
                        else:
                            deal_type = f"💥 MASSIVE {discount_val}% OFF LOOT!"

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
# 5. BACKGROUND THREADING
# ==========================================
if __name__ == "__main__":
    keep_alive()
    
    scraper_thread = threading.Thread(target=run_scraper)
    scraper_thread.daemon = True
    scraper_thread.start()

    print("Bot is starting Telegram Polling...")
    bot.infinity_polling()
