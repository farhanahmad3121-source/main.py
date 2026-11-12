FROM python:3.10-slim

# Chrome और जरूरी चीजें इंस्टॉल करो
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Python की लाइब्रेरीज़ इंस्टॉल करो
RUN pip install --no-cache-dir -r requirements.txt

# Bot को चालू करो
CMD ["python", "main.py"]
