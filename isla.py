import os
import tempfile
import asyncio
import logging
import threading
import time
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import requests

# ─── 1) FLASK HEALTH CHECK SERVER ───────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def healthz():
    # Render's load-balancer and port scanner will hit this endpoint.
    return "OK", 200

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ─── 2) LOGGING & CONFIGURATION ──────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES = range(3)

# ─── 3) YOUR EXISTING IslamicReelsBot CLASS ─────────────────────────────────
class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}
        self.setup_fonts()
    def setup_fonts(self):
        try:
            os.makedirs('fonts', exist_ok=True)
            self.download_fonts()
        except Exception as e:
            logger.error(f"Error setting up fonts: {e}")
    def download_fonts(self):
        font_urls = {
            'amiri': 'https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip',
            'noto': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf',
            'arial': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf'
        }
        for name, url in font_urls.items():
            font_path = f'fonts/{name}.ttf'
            if not os.path.exists(font_path):
                try:
                    resp = requests.get(url, timeout=30)
                    if resp.status_code == 200:
                        with open(font_path, 'wb') as f:
                            f.write(resp.content)
                        logger.info(f"Downloaded {name} font")
                except Exception as e:
                    logger.error(f"Failed to download {name} font: {e}")

    def get_main_keyboard(self):
        kb = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Reels"),    KeyboardButton("💾 Save All")],
            [KeyboardButton("🛑 Stop Process"),  KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)

    def get_save_keyboard(self, i):
        return InlineKeyboardMarkup([[InlineKeyboardButton("💾 Save This Reel", callback_data=f"save_{i}")]])

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        self.user_sessions[uid] = {'photos': [], 'videos': [], 'quotes': [], 'processed_media': []}
        welcome = """🕌 *Islamic Reels Maker* 🌟

1️⃣ Upload Media  
2️⃣ Add Quotes  
3️⃣ Make Reels  
4️⃣ Save

Use the buttons below! 🚀"""
        await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=self.get_main_keyboard())
        return MAIN_MENU

    async def handle_upload_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in self.user_sessions:
            return await self.start(update, context)
        await update.message.reply_text(
            "📤 Send photos/videos now. When done, tap 📝 Add Quotes.",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        return UPLOADING_MEDIA

    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in self.user_sessions:
            return await self.start(update, context)
        sess = self.user_sessions[uid]
        try:
            if update.message.photo:
                f = await update.message.photo[-1].get_file()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                await f.download_to_drive(tmp.name)
                sess['photos'].append({'file_path': tmp.name, 'type': 'image'})
                c = len(sess['photos'])
                await update.message.reply_text(f"✅ Photo {c} received!", reply_markup=self.get_main_keyboard())
            elif update.message.video:
                vid = update.message.video
                if vid.duration > 60:
                    return await update.message.reply_text(
                        "❌ Video too long! (<60s)", reply_markup=self.get_main_keyboard()
                    )
                f = await vid.get_file()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                await f.download_to_drive(tmp.name)
                sess['videos'].append({'file_path': tmp.name, 'type': 'video'})
                c = len(sess['videos'])
                await update.message.reply_text(f"✅ Video {c} received!", reply_markup=self.get_main_keyboard())
            elif update.message.document:
                mt = update.message.document.mime_type or ''
                if mt.startswith('video/'):
                    f = await update.message.document.get_file()
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                    await f.download_to_drive(tmp.name)
                    sess['videos'].append({'file_path': tmp.name, 'type': 'video'})
                    c = len(sess['videos'])
                    await update.message.reply_text(f"✅ Video {c} received!", reply_markup=self.get_main_keyboard())
                else:
                    await update.message.reply_text("❌ Unsupported file.", reply_markup=self.get_main_keyboard())
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("❌ Error uploading.", reply_markup=self.get_main_keyboard())
        return UPLOADING_MEDIA

    async def handle_add_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in self.user_sessions:
            return await self.start(update, context)
        tot = len(self.user_sessions[uid]['photos']) + len(self.user_sessions[uid]['videos'])
        if tot == 0:
            return await update.message.reply_text("❌ Upload media first!", reply_markup=self.get_main_keyboard())
        await update.message.reply_text(
            "📝 Send your quotes (one per line).", parse_mode='Markdown', reply_markup=self.get_main_keyboard()
        )
        return ADDING_QUOTES

    async def handle_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in self.user_sessions:
            return await self.start(update, context)
        text = update.message.text.strip()
        quotes = [q for q in text.split('\n') if q.strip()]
        if not quotes:
            return await update.message.reply_text("❌ Send valid quotes.", reply_markup=self.get_main_keyboard())
        self.user_sessions[uid]['quotes'] = quotes
        await update.message.reply_text(
            f"✅ Received {len(quotes)} quotes. Tap 🎬 Make Reels.",
            reply_markup=self.get_main_keyboard()
        )
        return MAIN_MENU

    # ... include your methods: is_arabic_text, get_font, process_arabic_text,
    # split_text_to_lines, create_image_with_quote, create_video_thumbnail,
    # handle_stop_process, handle_make_reels, handle_save_callback,
    # handle_save_all, handle_reset exactly as you had ...

# ─── 4) RUN BOT WITH POLLING ────────────────────────────────────────────────
def run_bot():
    bot = IslamicReelsBot()
    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^📤 Upload Media$'), bot.handle_upload_media),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                MessageHandler(filters.Regex('^🎬 Make Reels$'), bot.handle_make_reels),
                MessageHandler(filters.Regex('^💾 Save All$'), bot.handle_save_all),
                MessageHandler(filters.Regex('^🛑 Stop Process$'), bot.handle_stop_process),
                MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
            ],
            UPLOADING_MEDIA: [
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, bot.handle_media),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
            ],
            ADDING_QUOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_quotes)
            ],
        },
        fallbacks=[CommandHandler('start', bot.start)]
    )

    application.add_handler(CallbackQueryHandler(bot.handle_save_callback, pattern="^save_"))
    application.add_handler(conv)

    print("🤖 Islamic Reels Bot Starting…")
    application.run_polling(drop_pending_updates=True)

# ─── 5) MAIN: START HEALTH SERVER + BOT ────────────────────────────────────
def main():
    # 1) Launch Flask health-check in background so port is bound
    threading.Thread(target=run_health_server, daemon=True).start()
    print(f"🌐 Health server up on 0.0.0.0:{os.environ.get('PORT',10000)}")

    # 2) Run bot with retry logic
    max_retries, delay = 3, 10
    for i in range(max_retries):
        try:
            print(f"🚀 Bot attempt {i+1}/{max_retries}")
            run_bot()
            break
        except Exception as e:
            print(f"❌ Crash: {e}")
            if i < max_retries - 1:
                print(f"🔄 Retrying in {delay}s…")
                time.sleep(delay)
            else:
                print("💥 Max retries reached, exiting.")

if __name__ == "__main__":
    print("="*50)
    print("🕌 Islamic Reels Bot - Lifetime Version")
    print("🎥 Photos/Videos • 📝 Quotes")
    print("💾 Save • 🛑 Stop • 🔄 Reset")
    print("="*50)
    main()
