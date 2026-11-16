import os
import re
import urllib.parse
import urllib.request
from pyrogram import Client, filters

# ==========================================
# 1. CONFIGURATION & CREDENTIALS
# ==========================================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "") # Telegram लॉगिन के लिए Session String

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "@source_channel_username") # जिस चैनल से पोस्ट उठानी है
TARGET_BOT = os.environ.get("TARGET_BOT", "@your_bot_username") # जिस बॉट या चैनल पर फाइनल मैसेज भेजना है
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "") # यदि बॉट के जरिए भेजना हो

# Pyrogram क्लाइंट इनिशिएट करेंगे (रियल-टाइम लिसनर के लिए)
app = Client(
    "deal_automation_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ==========================================
# 2. EXTRACT LINKS & REAL-TIME FORWARDING
# ==========================================
@app.on_message(filters.chat(SOURCE_CHANNEL))
def process_loot_post(client, message):
    try:
        # पोस्ट का टेक्स्ट या कैप्शन निकालेंगे
        text = message.text or message.caption or ""
        
        # अमेज़ॉन या फ्लिपकार्ट का लिंक ढूंढने के लिए रेगुलर एक्सप्रेसवे (Regex)
        url_match = re.search(r'https?://[^\s]+', text)
        extracted_link = url_match.group(0) if url_match else None

        print(f"📥 New post caught from {SOURCE_CHANNEL}!")

        # अगर पोस्ट में कोई एफिलिएट/लूट लिंक मिला है, तो उसे प्रोसेस कर सकते हैं
        if extracted_link:
            print(f"🔗 Extracted Link: {extracted_link}")
            # यहाँ चाहें तो अपने एफिलिएट टैग जोड़ सकते हैं या सीधे फॉरवर्ड कर सकते हैं

        # ऑप्शन A: पूरी पोस्ट को सीधे टारगेट बॉट या चैनल पर कॉपी कर देगा
        message.copy(chat_id=TARGET_BOT)
        print(f"⚡ Successfully sent to {TARGET_BOT}!")

    except Exception as e:
        print(f"❌ Error in processing post: {e}")

# ==========================================
# 3. RUNNING THE WORKER 24/7
# ==========================================
if __name__ == "__main__":
    print("🚀 Automation Userbot is running 24/7 in real-time...")
    app.run()
