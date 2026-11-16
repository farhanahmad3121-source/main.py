import os
import re
import time
from pyrogram import Client, filters

# ==========================================
# 1. CONFIGURATION & CREDENTIALS (RENDER SECRETS)
# ==========================================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")  # तेरी Colab वाली मास्टर चाबी

SOURCE_CHANNEL = os.environ.get(
    "SOURCE_CHANNEL", "@Gpaysquadofficial2"
)  # जहाँ से पोस्ट उठानी है (बिना एडमिन के भी काम करेगा)
BOT_1 = os.environ.get("BOT_1", "@first_bot_username")  # पहला बॉट
BOT_2 = os.environ.get("BOT_2", "@second_bot_username")  # दूसरा बॉट
FINAL_TARGET = os.environ.get(
    "FINAL_TARGET", "me"
)  # जहाँ फाइनल लिंक भेजना है ('me' यानी तेरी खुद की चैट)

# Pyrogram Userbot क्लाइंट (तेरी आईडी से जुड़ेगा)
app = Client(
    "my_userbot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# ==========================================
# 2. REAL-TIME LISTENER & 2-BOT CHAIN WORKFLOW
# ==========================================
@app.on_message(filters.chat(SOURCE_CHANNEL))
def process_loot_post(client, message):
  try:
    # पोस्ट का टेक्स्ट या कैप्शन निकालेंगे
    text = message.text or message.caption or ""

    # ओरिजिनल पोस्ट से लिंक ढूंढेंगे
    url_match = re.search(r"https?://[^\s]+", text)
    if not url_match:
      return

    raw_link = url_match.group(0)
    print(f"📥 Caught raw link from source: {raw_link}")

    # --- Step 1: पहला लिंक BOT_1 को भेजना ---
    client.send_message(BOT_1, raw_link)
    print(f"📤 Sent to Bot 1 ({BOT_1})")

    # Bot 1 के रिप्लाई का 3 सेकंड इंतज़ार
    time.sleep(3)

    # Bot 1 का रिप्लाई फेच करके उसमें से नया लिंक निकालना
    for bot1_msg in client.get_chat_history(BOT_1, limit=1):
      bot1_text = bot1_msg.text or bot1_msg.caption or ""
      link_match_1 = re.search(r"https?://[^\s]+", bot1_text)

      if link_match_1:
        intermediate_link = link_match_1.group(0)
        print(f"🔗 Extracted link from Bot 1: {intermediate_link}")

        # --- Step 2: उस लिंक को BOT_2 को भेजना ---
        client.send_message(BOT_2, intermediate_link)
        print(f"📤 Sent to Bot 2 ({BOT_2})")

        # Bot 2 के रिप्लाई का 3 सेकंड इंतज़ार
        time.sleep(3)

        # Bot 2 का फाइनल आउटपुट फेच करना
        for bot2_msg in client.get_chat_history(BOT_2, limit=1):
          bot2_text = bot2_msg.text or bot2_msg.caption or ""
          link_match_2 = re.search(r"https?://[^\s]+", bot2_text)
          final_output = link_match_2.group(0) if link_match_2 else bot2_text

          # --- Step 3: फाइनल लिंक को टारगेट आईडी पर भेजना ---
          client.send_message(FINAL_TARGET, final_output)
          print(
              f"🚀 Successfully delivered final link to Target ({FINAL_TARGET})!"
          )
          break
      break

  except Exception as e:
    print(f"❌ Error in pipeline: {e}")


# ==========================================
# 3. RUNNING 24/7
# ==========================================
if __name__ == "__main__":
  print("🚀 Userbot is running 24/7 in real-time with Session String...")
  app.run()
