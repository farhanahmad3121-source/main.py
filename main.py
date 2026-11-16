import os
import re
import time
import telebot

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # तेरे अपने बॉट का टोकन
BOT_1 = os.environ.get(
    "BOT_1", "@first_bot_username"
)  # पहला बॉट (यूजरनेम के साथ)
BOT_2 = os.environ.get(
    "BOT_2", "@second_bot_username"
)  # दूसरा बॉट (यूजरनेम के साथ)

if not BOT_TOKEN:
  print("❌ Error: BOT_TOKEN is missing!")

bot = telebot.TeleBot(BOT_TOKEN)


# ==========================================
# GROUP CHAIN AUTOMATION WORKFLOW
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_group_messages(message):
  try:
    chat_id = message.chat.id
    text = message.text or message.caption or ""

    # भेजने वाले का यूजरनेम पता करेंगे
    sender_username = message.from_user.username if message.from_user else ""

    # 1. अगर मैसेज 'BOT_1' की तरफ से आया है
    if sender_username and f"@{sender_username.lower()}" == BOT_1.lower():
      url_match = re.search(r"https?://[^\s]+", text)
      if url_match:
        inter_link = url_match.group(0)
        print(f"🔗 Extracted link from Bot 1: {inter_link}")

        time.sleep(2)
        # उस लिंक को अब BOT_2 को भेजेंगे
        bot.send_message(chat_id, f"{BOT_2} {inter_link}")
        print(f"📤 Forwarded to Bot 2 ({BOT_2})")
      return

    # 2. अगर मैसेज 'BOT_2' की तरफ से आया है (फाइनल आउटपुट)
    if sender_username and f"@{sender_username.lower()}" == BOT_2.lower():
      url_match = re.search(r"https?://[^\s]+", text)
      if url_match:
        final_link = url_match.group(0)
        print(f"🚀 Final link received from Bot 2: {final_link}")

        # फाइनल लिंक को साफ-सुथरा करके ग्रुप में भेज देंगे
        bot.send_message(
            chat_id, f"🔥 **Ye le tera final loot link:**\n{final_link}"
        )
      return

    # 3. अगर मैसेज तूने (यूजर ने) भेजा है (लूट पोस्ट)
    url_match = re.search(r"https?://[^\s]+", text)
    if url_match:
      raw_link = url_match.group(0)
      print(f"📥 Caught raw loot link from user: {raw_link}")

      # तुरंत सबसे पहले लिंक को Bot 1 को भेजेंगे
      bot.send_message(chat_id, f"{BOT_1} {raw_link}")
      print(f"📤 Sent raw link to Bot 1 ({BOT_1})")

  except Exception as e:
    print(f"❌ Error in chain: {e}")


# ==========================================
# RUNNING 24/7
# ==========================================
if __name__ == "__main__":
  print("🚀 Group Chain Bot is running 24/7...")
  bot.infinity_polling()
