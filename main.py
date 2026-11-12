import telebot
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

# ========================================================
# 1. यहाँ अपना Telegram Bot Token डालो
# ========================================================
BOT_TOKEN = '8950038013:AAE5YwWdw2CuqkIrdYKPFdS5HvyRq1mVV2U'

# ========================================================
# 2. यहाँ अपनी Amazon Affiliate ID डालो
# ========================================================
YOUR_TAG = 'dealspointofficial-21'

bot = telebot.TeleBot(BOT_TOKEN)

def add_tag(url):
    if "tag=" in url:
        parts = url.split("tag=")
        return parts[0] + f"tag={YOUR_TAG}" + (parts[1].split("&")[0] if "&" in parts[1] else "")
    elif "?" in url:
        return url + f"&tag={YOUR_TAG}"
    else:
        return url + f"?tag={YOUR_TAG}"

def get_amzn_link(url):
    tagged_url = add_tag(url)
    
    # Chrome को Headless (बिना स्क्रीन) मोड में सेट करना
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # असली इंसान जैसा दिखने के लिए User-Agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    try:
        # ड्राइवर का रास्ता सीधे Dockerfile से लिया जा रहा है (कोई वर्जन एरर नहीं आएगा)
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)
        
        # Bitly का होमपेज खोलो
        driver.get("https://bitly.com/pages/home/cp/")
        time.sleep(4)

        # Input बॉक्स ढूंढो
        input_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Place your long link here']"))
        )
        input_box.clear()
        input_box.send_keys(tagged_url)
        time.sleep(1)
        
        # Shorten URL बटन दबाओ
        btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Shorten URL')]")
        btn.click()

        # रिजल्ट का इंतज़ार करो
        result = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@value, 'amzn.to') or contains(@value, 'bit.ly')] | //div[contains(text(), 'amzn.to') or contains(text(), 'bit.ly')]"))
        )
        
        short_url = result.get_attribute("value")
        if not short_url:
            short_url = result.text
            
        driver.quit()
        return f"✅ Success:\n{short_url.strip()}"
        
    except Exception as e:
        try:
            driver.quit()
        except:
            pass
        
        # एरर को साफ-साफ समझना (404, 503 या कोई और)
        error_msg = str(e)
        if "404" in error_msg:
            return f"❌ Error 404: Bitly का पेज नहीं मिला।\n⚠️ Fallback Link: {tagged_url}"
        elif "503" in error_msg:
            return f"❌ Error 503: Bitly का सर्वर डाउन है या ब्लॉक कर रहा है।\n⚠️ Fallback Link: {tagged_url}"
        elif "TimeoutException" in error_msg:
            return f"❌ Timeout: Bitly ने बहुत देर ली या रोक दिया।\n⚠️ Fallback Link: {tagged_url}"
        else:
            return f"❌ Error: {error_msg}\n⚠️ Fallback Link: {tagged_url}"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_url = message.text.strip()
    
    if not (user_url.startswith("http")):
        bot.reply_to(message, "❌ भाई, सही लिंक भेजो जो 'https://' से शुरू होता हो।")
        return

    bot.reply_to(message, "⏳ रुको भाई, Chrome खोलकर amzn.to लिंक बना रहा हूँ...")
    
    final_link = get_amzn_link(user_url)
    
    bot.reply_to(message, final_link)

print("Bot chalu ho gaya hai... Server par!")
bot.infinity_polling()
