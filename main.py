import os
import time
import json
import base64
import hashlib
import requests
import urllib3
import threading
from flask import Flask
from Crypto.Cipher import AES
import telebot

# SSL वार्निंग हटाने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. TELEGRAM BOT & SAMAGRA LOGIC SETUP
# ==========================================
PHOTO_DIR = "samagra_intel_photos"
CACHE_FILE = "samagra_keys.json"
KEY_TTL = 6 * 3600

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

def log(tag, msg):
    prefix = {"info": "[I]", "ok": "[+]", "err": "[-]", "sec": "[#]", "warn": "[!]"}
    print(f"{prefix.get(tag, '(*)')} {msg}")

def _aes_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()

def decrypt_data(b64_wire: str, secret: str) -> str:
    blob = base64.b64decode(b64_wire)
    iv, body = blob[:12], blob[12:]
    ct, tag = body[:-16], body[-16:]
    cipher = AES.new(_aes_key(secret), AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ct, tag).decode("utf-8")

class SamagraIntel:
    def __init__(self):
        self.base = "https://samagra.gov.in/Services/"
        self.version_url = self.base + "CommonWebApi.svc/GetAppVersion"
        self.details_url = self.base + "CommonWebApi.svc/GetDetailsBySamagra"
        self.headers = {
            "User-Agent": "okhttp/4.12.0",
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": "Basic c2FyYWRhY3RpaXZudWluWHdQZWVWTh3JHDE5="
        }
        self.ettpe = None
        self._load_keys()

    def _load_keys(self):
        try:
            with open(CACHE_FILE) as f:
                d = json.load(f)
            if time.time() - d.get("ts", 0) < KEY_TTL:
                self.ettpe = d.get("ettpe")
                return
        except Exception:
            pass
        self.fetch_keys()

    def fetch_keys(self, force=False):
        if self.ettpe and not force:
            return
        try:
            r = requests.post(self.version_url, headers=self.headers, json={}, timeout=20, verify=False)
            text = r.content.decode("utf-8-sig", errors="ignore").strip()
            j = json.loads(text)
            self.ettpe = j["d"]["ettpe"]
            with open(CACHE_FILE, "w") as f:
                json.dump({"ts": time.time(), "ettpe": self.ettpe}, f)
        except Exception as e:
            log("err", f"Key fetch failed: {e}")

    def lookup(self, samagra_id: str):
        self._load_keys()
        if not self.ettpe:
            return {"error": "Keys unavailable"}
        payload = {"samagraId": samagra_id}
        try:
            r = requests.post(self.details_url, headers=self.headers, json=payload, timeout=25, verify=False)
            text = r.content.decode("utf-8-sig", errors="ignore").strip()
            j = json.loads(text)
            if "d" in j and isinstance(j["d"], str):
                decrypted_str = decrypt_data(j["d"], self.ettpe)
                return json.loads(decrypted_str)
            return j
        except Exception as e:
            log("err", f"Lookup error: {e}")
            return {"error": str(e)}

client = SamagraIntel()

# Telegram Bot Initialization using Render Environment Variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "नमस्ते! Samagra Lookup बॉट एक्टिव है। कृपया अपनी Samagra ID या नंबर भेजें।")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    query = message.text.strip()
    bot.reply_to(message, "डेटा खोजा जा रहा है, कृपया प्रतीक्षा करें...")
    result = client.lookup(query)
    bot.reply_to(message, f"result: \n{json.dumps(result, indent=2, ensure_ascii=False)}")

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    # Flask को बैकग्राउंड में चालू करें
    keep_alive()
    # Telegram Bot Polling शुरू करें
    print("Bot is starting polling...")
    bot.infinity_polling()import os
import time
import json
import base64
import hashlib
import requests
import urllib3
import threading
from flask import Flask
from Crypto.Cipher import AES
import telebot

# SSL वार्निंग हटाने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. TELEGRAM BOT & SAMAGRA LOGIC SETUP
# ==========================================
PHOTO_DIR = "samagra_intel_photos"
CACHE_FILE = "samagra_keys.json"
KEY_TTL = 6 * 3600

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

def log(tag, msg):
    prefix = {"info": "[I]", "ok": "[+]", "err": "[-]", "sec": "[#]", "warn": "[!]"}
    print(f"{prefix.get(tag, '(*)')} {msg}")

def _aes_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()

def decrypt_data(b64_wire: str, secret: str) -> str:
    blob = base64.b64decode(b64_wire)
    iv, body = blob[:12], blob[12:]
    ct, tag = body[:-16], body[-16:]
    cipher = AES.new(_aes_key(secret), AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ct, tag).decode("utf-8")

class SamagraIntel:
    def __init__(self):
        self.base = "https://samagra.gov.in/Services/"
        self.version_url = self.base + "CommonWebApi.svc/GetAppVersion"
        self.details_url = self.base + "CommonWebApi.svc/GetDetailsBySamagra"
        self.headers = {
            "User-Agent": "okhttp/4.12.0",
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": "Basic c2FyYWRhY3RpaXZudWluWHdQZWVWTh3JHDE5="
        }
        self.ettpe = None
        self._load_keys()

    def _load_keys(self):
        try:
            with open(CACHE_FILE) as f:
                d = json.load(f)
            if time.time() - d.get("ts", 0) < KEY_TTL:
                self.ettpe = d.get("ettpe")
                return
        except Exception:
            pass
        self.fetch_keys()

    def fetch_keys(self, force=False):
        if self.ettpe and not force:
            return
        try:
            r = requests.post(self.version_url, headers=self.headers, json={}, timeout=20, verify=False)
            text = r.content.decode("utf-8-sig", errors="ignore").strip()
            j = json.loads(text)
            self.ettpe = j["d"]["ettpe"]
            with open(CACHE_FILE, "w") as f:
                json.dump({"ts": time.time(), "ettpe": self.ettpe}, f)
        except Exception as e:
            log("err", f"Key fetch failed: {e}")

    def lookup(self, samagra_id: str):
        self._load_keys()
        if not self.ettpe:
            return {"error": "Keys unavailable"}
        payload = {"samagraId": samagra_id}
        try:
            r = requests.post(self.details_url, headers=self.headers, json=payload, timeout=25, verify=False)
            text = r.content.decode("utf-8-sig", errors="ignore").strip()
            j = json.loads(text)
            if "d" in j and isinstance(j["d"], str):
                decrypted_str = decrypt_data(j["d"], self.ettpe)
                return json.loads(decrypted_str)
            return j
        except Exception as e:
            log("err", f"Lookup error: {e}")
            return {"error": str(e)}

client = SamagraIntel()

# Telegram Bot Initialization using Render Environment Variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "नमस्ते! Samagra Lookup बॉट एक्टिव है। कृपया अपनी Samagra ID या नंबर भेजें।")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    query = message.text.strip()
    bot.reply_to(message, "डेटा खोजा जा रहा है, कृपया प्रतीक्षा करें...")
    result = client.lookup(query)
    bot.reply_to(message, f"result: \n{json.dumps(result, indent=2, ensure_ascii=False)}")

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    # Flask को बैकग्राउंड में चालू करें
    keep_alive()
    # Telegram Bot Polling शुरू करें
    print("Bot is starting polling...")
    bot.infinity_polling()
