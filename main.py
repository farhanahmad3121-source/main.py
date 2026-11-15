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
from telebot import types

# SSL वार्निंग हटाने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
# 2. TELEBOT INITIALIZATION (पहले बॉट डिक्लेयर होगा)
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 3. /START COMMAND & MINI APP BUTTON
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # इनलाइन कीबोर्ड (बटन) बनाएं
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # 1. चैनल जॉइन करने का बटन
    btn_channel = types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/swiggylooters06")
    
    # 2. वेबसाइट/मिनी ऐप खोलने वाला वेब-ऐप बटन
    web_app_url = "https://swiggy.totalh.net"
    btn_webapp = types.InlineKeyboardButton("🎯 OPEN LOOT ARENA", web_app=types.WebAppInfo(url=web_app_url))
    
    markup.add(btn_webapp, btn_channel)
    
    # स्टाइलिश टेक्स्ट मैसेज (स्क्रीनशॉट जैसा)
    welcome_text = (
        "🍔 **SWIGGY LOOT ARENA** 🍔\n\n"
        "Hey Hacker! 👋\n\n"
        "Welcome to the ultimate food deals hub — your gateway to massive Swiggy savings.\n\n"
        "✨ **WHAT YOU GET**\n"
        "• 🔥 Get upto ₹100 free cash swiggy food\n\n"
        "📢 **STEP 1:** Join our official channel @swiggylooters06\n"
        "🚀 **STEP 2:** Tap the button below to enter."
    )
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    # Flask को बैकग्राउंड में चालू करें
    keep_alive()
    print("Bot is starting polling...")
    bot.infinity_polling()
