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

# यहाँ अपने दोनों फोर्स-सब्सक्रिप्शन वाले चैनलों के यूजरनेम डाल दे
CHANNEL_1 = "@swiggylooters06"
CHANNEL_2 = "@techhelperram" # यहाँ अपना दूसरा चैनल बदल लेना

# चेक करने का फंक्शन कि यूजर ने दोनों चैनल जॉइन किए हैं या नहीं
def check_subscription(user_id):
    try:
        m1 = bot.get_chat_member(CHANNEL_1, user_id)
        m2 = bot.get_chat_member(CHANNEL_2, user_id)
        
        valid_statuses = ['member', 'administrator', 'creator']
        if m1.status in valid_statuses and m2.status in valid_statuses:
            return True
    except Exception as e:
        print(f"Error checking sub: {e}")
    return False

# ==========================================
# 3. /START COMMAND & SUBSCRIPTION LOGIC
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # पहले चेक करो कि यूजर ने दोनों चैनल जॉइन किए हैं या नहीं
    if not check_subscription(user_id):
        # अगर जॉइन नहीं किया है, तो यह लॉक स्क्रीन (Force Sub message) दिखेगी
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_c1 = types.InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
        btn_c2 = types.InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        btn_verify = types.InlineKeyboardButton("🔄 I Have Joined (Verify)", callback_data="check_sub")
        markup.add(btn_c1, btn_c2, btn_verify)
        
        lock_text = (
            "⚠️ **ACCESS DENIED!** ⚠️\n\n"
            "अरे भाई! बॉट का इस्तेमाल करने से पहले हमारे **दोनों चैनल्स** को जॉइन करना ज़रूरी है।\n\n"
            f"1️⃣ {CHANNEL_1}\n"
            f"2️⃣ {CHANNEL_2}\n\n"
            "चैनल जॉइन करने के बाद नीचे **'Verify'** बटन पर क्लिक करें! 👇"
        )
        bot.send_message(message.chat.id, lock_text, parse_mode="Markdown", reply_markup=markup)
    else:
        # अगर दोनों चैनल जॉइन हैं, तो सीधा फाइनल लूट एरिना दिखाओ
        show_loot_arena(message.chat.id, message.from_user.first_name)

def show_loot_arena(chat_id, user_first_name):
    user_name = user_first_name or "Hacker"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    web_app_url = "https://swiggy.totalh.net"
    btn_webapp = types.InlineKeyboardButton("🎯 OPEN LOOT ARENA", web_app=types.WebAppInfo(url=web_app_url))
    btn_channel = types.InlineKeyboardButton("📢 Official Channel", url=f"https://t.me/{CHANNEL_1.replace('@', '')}")
    markup.add(btn_webapp, btn_channel)
    
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
        "📢 STEP 1: Join our official channel\n"
        f"     └ {CHANNEL_1}\n\n"
        "🚀 STEP 2: Tap the button below to enter"
    )
    bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# जब यूजर 'Verify' बटन दबाएगा
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def verify_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        bot.answer_callback_query(call.id, "✅ बहुत बढ़िया! दोनों चैनल जॉइन हो गए हैं।")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        show_loot_arena(call.message.chat.id, call.from_user.first_name)
    else:
        bot.answer_callback_query(call.id, "❌ भाई, तूने अभी तक दोनों चैनल जॉइन नहीं किए हैं पूरे!", show_alert=True)

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    keep_alive()
    print("Bot is starting polling...")
    bot.infinity_polling()
