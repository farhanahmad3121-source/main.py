from telebot import types

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # इनलाइन कीबोर्ड (बटन) बनाएं
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # 1. चैनल जॉइन करने का बटन
    btn_channel = types.InlineKeyboardButton("📢 Join Channel", url="https://t.me/swiggylooters06")
    
    # 2. वेबसाइट/मिनी ऐप खोलने वाला वेब-ऐप बटन (जो सीधा तेरी वेबसाइट खोलेगा)
    web_app_url = "https://swiggy.totalh.net"
    btn_webapp = types.InlineKeyboardButton("🎯 OPEN LOOT ARENA", web_app=types.WebAppInfo(url=web_app_url))
    
    markup.add(btn_webapp, btn_channel)
    
    # स्क्रीनशॉट जैसी स्टाइलिश टेक्स्ट मेसेज
    welcome_text = (
        "🍔 **SWIGGY LOOT ARENA** 🍔\n\n"
        "Hey Hacker! 👋\n\n"
        "Welcome to the ultimate food deals hub — your gateway to massive Swiggy savings.\n\n"
        "✨ **WHAT YOU GET**\n"
        "| 🔥 Get upto ₹100 free cash swiggy food |\n\n"
        "📢 **STEP 1:** Join our official channel @swiggylooters06\n"
        "🚀 **STEP 2:** Tap the button below to enter."
    )
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)
