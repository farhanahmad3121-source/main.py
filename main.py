import os
import re
import time
from pyrogram import Client

# ==========================================
# 1. CONFIGURATION & CREDENTIALS
# ==========================================
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "@Gpaysquadofficial2")
BOT_1 = os.environ.get("BOT_1", "@first_bot_username")
BOT_2 = os.environ.get("BOT_2", "@second_bot_username")
FINAL_TARGET = os.environ.get("FINAL_TARGET", "me")

# Pyrogram क्लाइंट इनिशिएट करेंगे
app = Client(
    "loot_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# ==========================================
# 2. EVENT-LOOP FREE SAFE LISTENER
# ==========================================
def main_loop():
  print("🚀 Starting Userbot safely...")
  app.start()
  print("🚀 2-Bot Chain Userbot is running live and connected!")

  # चैनल के नए मैसेज लगातार चेक करने का सबसे सुरक्षित तरीका (बिना किसी Event Loop के)
  last_processed_id = 0

  while True:
    try:
      # सोर्स चैनल के आखिरी मैसेज फेच करेंगे
      for message in app.get_chat_history(SOURCE_CHANNEL, limit=1):
        if message.id > last_processed_id:
          last_processed_id = message.id
          text = message.text or message.caption or ""

          url_match = re.search(r"https?://[^\s]+", text)
          if url_match:
            raw_link = url_match.group(0)
            print(f"📥 Caught raw link from source: {raw_link}")

            # --- Step 1: BOT_1 को भेजना ---
            app.send_message(BOT_1, raw_link)
            print(f"📤 Sent to Bot 1 ({BOT_1})")

            time.sleep(3)

            # --- Step 2: BOT_1 का रिप्लाई निकालना ---
            for bot1_msg in app.get_chat_history(BOT_1, limit=1):
              bot1_text = bot1_msg.text or bot1_msg.caption or ""
              link_match_1 = re.search(r"https?://[^\s]+", bot1_text)

              if link_match_1:
                intermediate_link = link_match_1.group(0)
                print(f"🔗 Extracted link from Bot 1: {intermediate_link}")

                # --- Step 3: BOT_2 को भेजना ---
                app.send_message(BOT_2, intermediate_link)
                print(f"📤 Sent to Bot 2 ({BOT_2})")

                time.sleep(3)

                # --- Step 4: BOT_2 का आउटपुट टारगेट पर भेजना ---
                for bot2_msg in app.get_chat_history(BOT_2, limit=1):
                  bot2_text = bot2_msg.text or bot2_msg.caption or ""
                  link_match_2 = re.search(r"https?://[^\s]+", bot2_text)
                  final_output = (
                      link_match_2.group(0) if link_match_2 else bot2_text
                  )

                  app.send_message(FINAL_TARGET, final_output)
                  print(
                      f"🚀 Delivered final link to Target ({FINAL_TARGET})!"
                  )
                  break
              break

    except Exception as e:
      print(f"⚠️ Minor loop error (retrying): {e}")

    # हर 5 सेकंड में नया मैसेज चेक करेगा ताकि सर्वर पर लोड न पड़े
    time.sleep(5)


if __name__ == "__main__":
  main_loop()
