import telebot
import requests
import re
import urllib.parse
import time

# यहाँ अपना Telegram Bot Token डालो
BOT_TOKEN = '8950038013:AAE5YwWdw2CuqkIrdYKPFdS5HvyRq1mVV2U'
bot = telebot.TeleBot(BOT_TOKEN)

YOUR_TAG = 'dealspointofficial-21'

def add_tag(url):
    if "tag=" in url:
        parts = url.split("tag=")
        return parts[0] + f"tag={YOUR_TAG}" + (parts[1].split("&")[0] if "&" in parts[1] else "")
    elif "?" in url:
        return url + f"&tag={YOUR_TAG}"
    else:
        return url + f"?tag={YOUR_TAG}"

def get_bitly_link(url):
    tagged_url = add_tag(url)
    
    # नया सेशन बनाओ (जैसे नया ब्राउज़र खुला हो)
    session = requests.Session()
    
    # Chrome जैसा Fake Header (ताकि Bitly ब्लॉक न करे)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Origin': 'https://bitly.com',
        'Referer': 'https://bitly.com/'
    }

    try:
        # 1. Bitly के होमपेज पर जाओ और छिपा हुआ CSRF Token निकालो
        page = session.get("https://bitly.com/pages/home/cp/", headers=headers, timeout=15)
        match = re.search(r'csrfToken["\']?\s*:\s*["\']([^"\']+)', page.text)
        token = match.group(1) if match else None

        # 2. API के लिए हेडर्स तैयार करो
        api_headers = headers.copy()
        api_headers['Content-Type'] = 'application/json'
        if token:
            api_headers['X-CSRF-Token'] = token

        # 3. Bitly की API पर लिंक भेजो
        payload = {"long_url": tagged_url}
        response = session.post("https://bitly.com/data/shorten", headers=api_headers, json=payload, timeout=15)
        
        if response.status_code in (200, 201):
            data = response.json()
            link = data.get('url') or data.get('link')
            if link:
                return f"✅ Official Link:\n{link}"
                
    except Exception as e:
        pass

    # 4. अगर Bitly फेल हो जाए, तो Is.gd (बिना Chrome के 100% काम करता है)
    try:
        res = requests.get(f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(tagged_url)}", timeout=10)
        if res.status_code == 200:
            return f"✅ Short Link:\n{res.text.strip()}"
    except:
        pass

    # 5. अगर सब फेल हो जाए, तो लंबा लिंक दे दो
    return f"⚠️ Short link नहीं बना, ये लंबा लिंक कॉपी कर लो:\n{tagged_url}"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_url = message.text.strip()
    
    if not (user_url.startswith("http")):
        bot.reply_to(message, "❌ भाई, सही लिंक भेजो जो 'https://' से शुरू होता हो।")
        return

    bot.reply_to(message, "⏳ रुको भाई, लिंक बना रहा हूँ...")
    
    final_link = get_bitly_link(user_url)
    
    bot.reply_to(message, final_link)
    time.sleep(2)

print("Bot chalu ho gaya hai... Server par!")
bot.infinity_polling()
