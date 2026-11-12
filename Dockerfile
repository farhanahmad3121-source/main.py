FROM python:3.10
RUN apt-get update && apt-get install -y chromium chromium-driver
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
