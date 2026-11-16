import os
import re
import telebot

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", ""
)  # @BotFather वाला बॉट टोकन (Render के Environment में डालना है)
TARGET_BOT = os.environ.get(
    "TARGET_BOT", "@second_bot_username"
)  # दूसरा बॉट या चैट जहाँ फाइनल लिंक भेजना है

if not BOT_TOKEN:
  print("❌ Error: BOT_TOKEN is missing!")

bot = telebot.TeleBot(BOT_TOKEN)


# ==========================================
# LINK EXTRACTOR & FORWARDER
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
  try:
    text = message.text or message.caption or ""

    # मैसेज में से कोई भी http/https वाला लिंक ढूंढेंगे
    url_match = re.search(r"https?://[^\s]+", text)

    if url_match:
      extracted_link = url_match.group(0)
      print(f"📥 Link caught: {extracted_link}")

      # सीधा निकाला हुआ लिंक दूसरे बॉट या टारगेट को भेज देगा
      bot.send_message(TARGET_BOT, extracted_link)
      print(f"🚀 Successfully forwarded clean link to {TARGET_BOT}")
    else:
      # अगर लिंक नहीं होगा तो बता देगा
      bot.reply_to(message, "⚠️ Bhai, is message mein koi link nahi mila!")

  except Exception as e:
    print(f"❌ Error: {e}")


# ==========================================
# RUNNING 24/7
# ==========================================
if __name__ == "__main__":
  print("🚀 Simple Link Bot is running 24/7...")
  bot.infinity_polling()
