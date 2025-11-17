from flask import Flask
from threading import Thread
import time
import requests

app = Flask('')

@app.route('/')
def home():
    return "🕌 Islamic Reels Bot is Alive! 🌟"

@app.route('/health')
def health():
    return {"status": "running", "timestamp": time.time()}

@app.route('/ping')
def ping():
    return "pong"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Start the keep-alive server"""
    server = Thread(target=run)
    server.daemon = True
    server.start()
    print("🔄 Keep-alive server started on port 8080")
