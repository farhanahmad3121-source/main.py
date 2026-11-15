import os
import time
import json
import base64
import hashlib
import requests
import urllib3
from threading import Thread
from flask import Flask
from Crypto.Cipher import AES

# SSL वार्निंग्स हटाने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 1. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए) ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running smoothly!"

def run_flask():
    # Render द्वारा दिया गया पोर्ट या डिफ़ॉल्ट 8080 इस्तेमाल करें
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()


# ==================== 2. तेरा मुख्य लॉजिक / बॉट / स्क्रिप्ट ====================
PHOTO_DIR = "samagra_intel_photos"
CACHE_FILE = "samagra_keys.json"
KEY_TTL = 6 * 3600

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

def log(tag, msg):
    prefix = {"info": "[*]", "ok": "[+]", "err": "[-]", "sec": "[#]", "warn": "[!]"}
    print(f"{prefix.get(tag, '[*]')} {msg}")

def _aes_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()

def decrypt_data(b64_wire: str, secret: str) -> str:
    blob = base64.b64decode(b64_wire)
    iv, body = blob[:12], blob[12:]
    ct, tag = body[:-16], body[-16:]
    cipher = AES.new(_aes_key(secret), AES.MODE_GCM, nonce=iv, mac_len=16)
    return cipher.decrypt_and_verify(ct, tag).decode("utf-8")

class SamagraIntel:
    def __init__(self):
        self.base = "https://samagra.gov.in/Services/"
        self.version_url = self.base + "CommonWebApi.svc/GetAppVersion"
        self.details_url = self.base + "CommonWebApi.svc/GetDetailsBySamagra"
        self.headers = {
            "User-Agent": "okhttp/4.12.0",
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": "Basic c2FtYWdyYUFwaTpzYW1hZ3JhQDEyMw==",
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
            if j.get("status") != "Success":
                return
            rows = j.get("data") or []
            if not rows:
                return
            row = rows[0]
            self.ettpe = row.get("E1")
            with open(CACHE_FILE, "w") as f:
                json.dump({"ettpe": self.ettpe, "ts": time.time()}, f)
        except Exception as e:
            log("err", f"key fetch: {e}")

    # बाकी तेरा पूरा क्लास लॉजिक यहाँ सुरक्षित है...


# ==================== 3. मुख्य रनर ब्लॉक ====================
if __name__ == "__main__":
    # सबसे पहले Flask सर्वर बैकग्राउंड में चालू करो ताकि Render को ओपन पोर्ट मिले
    keep_alive()
    print("Flask Keep-Alive Server Started...")

    # अब अपना मुख्य बॉट या लूप यहाँ चलाओ
    # (अगर यह टेलीग्राम बॉट होता, तो bot.infinity_polling() यहाँ आता)
    while True:
        # यहाँ तेरी बैकग्राउंड प्रोसेस या बॉट का लूप चलता रहेगा
        time.sleep(30)
