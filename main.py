import os
import threading
from flask import Flask
import telebot
from telebot import types

# ==========================================
# 1. FLASK WEB SERVER (रेंडर को जगाए रखने के लिए)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Swiggy Loot Bot is alive and running smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. TELEBOT INITIALIZATION
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 3. /START COMMAND & BUTTONS
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # यूजर का असली नाम ले लेगा (ताकि हर किसी को उसका खुद का नाम दिखे)
    user_name = message.from_user.first_name or "Hacker"
    
    # इनलाइन कीबोर्ड (बटन) बनाएं
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # 1. मिनी ऐप खोलने वाला वेब-ऐप बटन
    web_app_url = "https://swiggy.totalh.net"
    btn_webapp = types.InlineKeyboardButton("🎯 OPEN LOOT ARENA", web_app=types.WebAppInfo(url=web_app_url))
    
    # 2. दोनों चैनलों के बटन (पहला फिक्स, दूसरा वाला तू अपने हिसाब से बदल लेना)
    btn_channel1 = types.InlineKeyboardButton("📢 Join Official Channel", url="https://t.me/swiggylooters06")
    btn_channel2 = types.InlineKeyboardButton("📢 Join Second Channel", url="https://t.me/techhelperram")
    
    # बटन्स को जोड़ दिया
    markup.add(btn_webapp, btn_channel1, btn_channel2)
    
    # तेरी माँगी हुई डिज़ाइन और टेक्स्ट वाला फॉर्मेट (दो चैनलों के साथ)
    welcome_text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🍔  SWIGGY LOOT ARENA  🍔\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hey {user_name}! 👋\n\n"
        "Welcome to the ultimate food deals hub — your gateway to massive Swiggy savings.\n\n"
        "┌─── ✨ WHAT YOU GET ───┐\n"
        "│\n"
        "│  🔥  Up to 60% OFF on food\n"
        "│  🛒  ₹1 deals on Instamart\n"
        "│  ⚡  FREE delivery combos\n"
        "│  🎯  Daily updated offers\n"
        "│\n"
        "└────────────────────┘\n\n"
        "📢 STEP 1: Join our channels\n"
        "    ├ @swiggylooters06\n"
        "    └ @your_second_channel\n\n"
        "🚀 STEP 2: Tap the button below to enter"
    )
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    keep_alive()
    print("Bot is starting polling...")
    bot.infinity_polling()
