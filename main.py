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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. FLASK WEB SERVER (24/7 जिंदा रखने के लिए)
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

# यहाँ अपने दोनों चैनलों के यूजरनेम या आईडी डाल दे (जैसे '@channel1' और '@channel2')
CHANNEL_1 = "@swiggylooters06"  # पहला चैनल
CHANNEL_2 = "@techhelperram" # दूसरा चैनल (यहाँ अपना दूसरा चैनल बदल लेना)

def check_subscription(user_id):
    try:
        # चेक करो यूजर पहले चैनल में है या नहीं
        member1 = bot.get_chat_member(CHANNEL_1, user_id)
        # चेक करो यूजर दूसरे चैनल में है या नहीं
        member2 = bot.get_chat_member(CHANNEL_2, user_id)
        
        if member1.status in ['member', 'administrator', 'creator'] and member2.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Error checking sub: {e}")
    return False

# ==========================================
# 3. /START COMMAND & SUBSCRIPTION CHECK
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # चेक करो कि यूजर ने चैनल जॉइन किया है या नहीं
    is_joined = check_subscription(user_id)
    
    if not is_joined:
        # अगर जॉइन नहीं किया है, तो सिर्फ चैनल जॉइन करने का बटन दिखाओ
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_c1 = types.InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn_c2 = types.InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn_check = types.InlineKeyboardButton("🔄 Main Check / Verify", callback_data="check_sub")
        markup.add(btn_c1, btn_c2, btn_check)
        
        bot.send_message(
            message.chat.id, 
            "⚠️ **अरे भाई!** बॉट इस्तेमाल करने से पहले हमारे दोनों चैनल्स को जॉइन करना जरूरी है।\n\nचैनल जॉइन करने के बाद नीचे **'Verify'** बटन पर क्लिक करें!", 
            parse_mode="Markdown", 
            reply_markup=markup
        )
    else:
        # अगर जॉइन कर लिया है, तब ये फाइनल मिनी ऐप वाले बटन दिखाओ
        show_loot_arena(message.chat.id)

def show_loot_arena(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    web_app_url = "https://swiggy.totalh.net"
    btn_webapp = types.InlineKeyboardButton("🎯 OPEN LOOT ARENA", web_app=types.WebAppInfo(url=web_app_url))
    btn_channel = types.InlineKeyboardButton("📢 Official Channel", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
    markup.add(btn_webapp, btn_channel)
    
    welcome_text = (
        "🍔 **SWIGGY LOOT ARENA** 🍔\n\n"
        "Hey Hacker! 👋\n\n"
        "Welcome to the ultimate food deals hub — your gateway to massive Swiggy savings.\n\n"
        "✨ **WHAT YOU GET**\n"
        "• 🔥 Get upto ₹100 free cash swiggy food[cite: 29]\n\n"
        "🚀 **Tap the button below to enter.**"
    )
    bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# जब यूजर 'Verify' बटन दबाएगा
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ बहुत बढ़िया! दोनों चैनल जॉइन कर लिए हैं।")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        show_loot_arena(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ तुमने अभी तक दोनों चैनल जॉइन नहीं किए हैं भाई!", show_alert=True)

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    keep_alive()
    print("Bot is starting polling...")
    bot.infinity_polling()
