FROM python:3.10-slim

# Chrome और जरूरी पैकेज इंस्टॉल करो (यह खुद सही वर्जन मैनेज करेगा)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Chrome का रास्ता सेट करो
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
