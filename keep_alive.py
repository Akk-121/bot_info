from flask import Flask
from threading import Thread
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    return "🤖 Бот работает!", 200

@app.route('/health')
def health():
    return "OK", 200

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    """Запускает Flask сервер в отдельном потоке"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info("🌐 Keep-alive сервер запущен на порту 10000")