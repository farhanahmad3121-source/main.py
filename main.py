import asyncio
import os
import re
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

app = Client(
    "loot_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


# ==========================================
# 2. DIRECT MESSAGE HANDLER (NO EVENT LOOP CRASH)
# ==========================================
@app.on_message()
async def handle_all_messages(client, message):
  try:
    # सिर्फ सोर्स चैनल के मैसेज पकड़ेगा
    if message.chat.username and f"@{message.chat.username.lower()}" == SOURCE_CHANNEL.lower():
      text = message.text or message.caption or ""
      url_match = re.search(r"https?://[^\s]+", text)
      if not url_match:
        return

      raw_link = url_match.group(0)
      print(f"📥 Caught raw link from source: {raw_link}")

      # --- Step 1: BOT_1 को भेजना ---
      await client.send_message(BOT_1, raw_link)
      print(f"📤 Sent to Bot 1 ({BOT_1})")

      await asyncio.sleep(3)

      # --- Step 2: BOT_1 का रिप्लाई निकालना ---
      async for bot1_msg in client.get_chat_history(BOT_1, limit=1):
        bot1_text = bot1_msg.text or bot1_msg.caption or ""
        link_match_1 = re.search(r"https?://[^\s]+", bot1_text)

        if link_match_1:
          intermediate_link = link_match_1.group(0)
          print(f"🔗 Extracted link from Bot 1: {intermediate_link}")

          # --- Step 3: BOT_2 को भेजना ---
          await client.send_message(BOT_2, intermediate_link)
          print(f"📤 Sent to Bot 2 ({BOT_2})")

          await asyncio.sleep(3)

          # --- Step 4: BOT_2 का आउटपुट निकालकर टारगेट पर भेजना ---
          async for bot2_msg in client.get_chat_history(BOT_2, limit=1):
            bot2_text = bot2_msg.text or bot2_msg.caption or ""
            link_match_2 = re.search(r"https?://[^\s]+", bot2_text)
            final_output = link_match_2.group(0) if link_match_2 else bot2_text

            await client.send_message(FINAL_TARGET, final_output)
            print(f"🚀 Delivered final link to Target ({FINAL_TARGET})!")
            break
        break

  except Exception as e:
    print(f"❌ Error in pipeline: {e}")


# ==========================================
# 3. RUNNING 24/7 SAFELY
# ==========================================
async def main():
  print("🚀 Starting Userbot...")
  await app.start()
  print("🚀 2-Bot Chain Userbot is running 24/7 smoothly!")
  # अनंत काल तक चलाने के लिए निष्क्रिय रूप से लूप रखेंगे
  while True:
    await asyncio.sleep(3600)


if __name__ == "__main__":
  asyncio.run(main())
