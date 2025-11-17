import os
import tempfile
import asyncio
import logging
import signal
import sys
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import requests

# ----------------------------------------
# Logging
# ----------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------------------
# Bot Token
# ----------------------------------------
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# ----------------------------------------
# Conversation States
# ----------------------------------------
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES = range(3)

# ----------------------------------------
# Core Bot Class
# ----------------------------------------
class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}
        self.setup_fonts()
    
    def setup_fonts(self):
        """Ensure font files are present."""
        try:
            os.makedirs('fonts', exist_ok=True)
            self.download_fonts()
        except Exception as e:
            logger.error(f"Error setting up fonts: {e}")
    
    def download_fonts(self):
        """Download Arabic/English fonts if missing."""
        font_urls = {
            'amiri': 'https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip',
            'noto': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf',
        }
        for name, url in font_urls.items():
            font_path = f'fonts/{name}.ttf'
            if not os.path.exists(font_path):
                try:
                    r = requests.get(url, timeout=30)
                    if r.status_code == 200:
                        with open(font_path, 'wb') as f:
                            f.write(r.content)
                        logger.info(f"Downloaded {name} font")
                except Exception as e:
                    logger.error(f"Failed to download {name} font: {e}")
    
    # ——— Keyboards ———
    def get_main_keyboard(self):
        kb = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Reels"), KeyboardButton("💾 Save All")],
            [KeyboardButton("🛑 Stop Process"), KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(kb, resize_keyboard=True)
    
    def get_save_keyboard(self, idx):
        return InlineKeyboardMarkup([[InlineKeyboardButton("💾 Save This Reel", callback_data=f"save_{idx}")]])
    
    # ——— Handlers ———
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.user_sessions[user_id] = {'photos': [], 'videos': [], 'quotes': [], 'processed_media': []}
        text = (
            "🕌 *Islamic Reels Maker* 🌟\n\n"
            "1️⃣ Upload Media\n2️⃣ Add Quotes\n3️⃣ Make Reels\n4️⃣ Save All\n\n"
            "Use the buttons below to start!"
        )
        await update.message.reply_text(
            text, reply_markup=self.get_main_keyboard(), parse_mode='Markdown'
        )
        return MAIN_MENU
    
    async def handle_upload_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return await self.start(update, context)
        await update.message.reply_text(
            "📤 Send your photos or short videos now.",
            reply_markup=self.get_main_keyboard()
        )
        return UPLOADING_MEDIA
    
    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return await self.start(update, context)
        sess = self.user_sessions[user_id]
        try:
            if update.message.photo:
                file = await update.message.photo[-1].get_file()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                await file.download_to_drive(tmp.name)
                sess['photos'].append({'file_path': tmp.name, 'type': 'image'})
                await update.message.reply_text("✅ Photo received!", reply_markup=self.get_main_keyboard())
            elif update.message.video:
                vid = update.message.video
                if vid.duration > 60:
                    return await update.message.reply_text("❌ Video too long (>60s).", reply_markup=self.get_main_keyboard())
                file = await vid.get_file()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                await file.download_to_drive(tmp.name)
                sess['videos'].append({'file_path': tmp.name, 'type': 'video'})
                await update.message.reply_text("✅ Video received!", reply_markup=self.get_main_keyboard())
            elif update.message.document and update.message.document.mime_type.startswith('video/'):
                file = await update.message.document.get_file()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                await file.download_to_drive(tmp.name)
                sess['videos'].append({'file_path': tmp.name, 'type': 'video'})
                await update.message.reply_text("✅ Video received!", reply_markup=self.get_main_keyboard())
            else:
                await update.message.reply_text("❌ Unsupported file. Send JPG/PNG/MP4.", reply_markup=self.get_main_keyboard())
        except Exception as e:
            logger.error(f"Error uploading media: {e}")
            await update.message.reply_text("❌ Upload error, try again.", reply_markup=self.get_main_keyboard())
        return UPLOADING_MEDIA
    
    async def handle_add_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return await self.start(update, context)
        sess = self.user_sessions[user_id]
        if not (sess['photos'] or sess['videos']):
            return await update.message.reply_text("❌ Upload media first!", reply_markup=self.get_main_keyboard())
        await update.message.reply_text(
            "📝 Send your quotes (one per line).", reply_markup=self.get_main_keyboard()
        )
        return ADDING_QUOTES
    
    async def handle_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            return await self.start(update, context)
        lines = [l.strip() for l in update.message.text.split('\n') if l.strip()]
        if not lines:
            return await update.message.reply_text("❌ No valid quotes found.", reply_markup=self.get_main_keyboard())
        self.user_sessions[user_id]['quotes'] = lines
        cnt_media = len(self.user_sessions[user_id]['photos']) + len(self.user_sessions[user_id]['videos'])
        await update.message.reply_text(
            f"✅ Received {len(lines)} quotes! Possible combos: {cnt_media * len(lines)}",
            reply_markup=self.get_main_keyboard()
        )
        return MAIN_MENU
    
    # ——— Text/Image Helpers ———
    def is_arabic_text(self, text):
        return any(0x0600 <= ord(c) <= 0x06FF for c in text)
    
    def get_font(self, size, is_arabic=False):
        paths = [
            'fonts/amiri.ttf' if is_arabic else 'arial.ttf',
            'fonts/noto.ttf' if is_arabic else 'arial.ttf',
            'arial.ttf'
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except:
                    pass
        return ImageFont.load_default()
    
    def process_arabic_text(self, text):
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text
    
    def split_text_to_lines(self, text, font, max_w, is_arabic=False):
        lines, raw = [], text.split('\n')
        for rl in raw:
            if not rl.strip():
                lines.append('')
                continue
            words, cur = rl.split(), []
            for w in words:
                test = ' '.join(cur + [w])
                tw = font.getbbox(self.process_arabic_text(test) if is_arabic else test)[2]
                if tw <= max_w:
                    cur.append(w)
                else:
                    if cur:
                        lines.append(' '.join(cur))
                    cur = [w]
            if cur:
                lines.append(' '.join(cur))
        return lines
    
    def create_image_with_quote(self, img_path, quote):
        try:
            W, H = 1080, 1350
            bg = Image.new('RGB', (W, H), (0, 0, 0))
            im = Image.open(img_path)
            im.thumbnail((W, H), Image.Resampling.LANCZOS)
            bg.paste(im, ((W-im.width)//2, (H-im.height)//2))
            draw = ImageDraw.Draw(bg)
            arabic = self.is_arabic_text(quote)
            font = self.get_font(60 if arabic else 50, arabic)
            lines = self.split_text_to_lines(quote, font, W*0.8, arabic)
            lh = 80 if arabic else 70
            total_h = len(lines)*lh
            y0 = (H - total_h)//2
            # background overlay
            pad = 40
            bw, bh = W-100, total_h + 2*pad
            x0, yb = (W-bw)//2, y0-pad
            over = Image.new('RGBA', (bw, bh), (0,0,0,180))
            bg.paste(over, (x0, yb), over)
            for i, ln in enumerate(lines):
                if not ln.strip(): continue
                if arabic: ln = self.process_arabic_text(ln)
                tw = draw.textbbox((0,0), ln, font=font)[2]
                x = x0 + (bw-tw-40 if arabic else (W-tw)//2)
                y = y0 + i*lh
                draw.text((x+3, y+3), ln, font=font, fill=(0,0,0,200))
                draw.text((x, y), ln, font=font, fill=(255,255,255))
            out = tempfile.mktemp(suffix='.jpg')
            bg.save(out, quality=95)
            return out
        except Exception as e:
            logger.error(f"Image quote error: {e}")
            return img_path
    
    def create_video_thumbnail(self, video_path, quote):
        try:
            W, H = 1080, 1350
            bg = Image.new('RGB', (W, H), (30,60,90))
            draw = ImageDraw.Draw(bg)
            arabic = self.is_arabic_text(quote)
            font = self.get_font(60 if arabic else 50, arabic)
            lines = self.split_text_to_lines(quote, font, W*0.8, arabic)
            lh = 80 if arabic else 70
            total_h = len(lines)*lh
            y0 = (H - total_h)//2
            # box
            draw.rectangle([50, y0-60, W-50, y0+total_h+60],
                           fill=(0,0,0,180), outline=(255,255,255), width=3)
            for i, ln in enumerate(lines):
                if not ln.strip(): continue
                if arabic: ln = self.process_arabic_text(ln)
                tw = draw.textbbox((0,0), ln, font=font)[2]
                x = (W - tw)//2
                y = y0 + i*lh
                draw.text((x, y), ln, font=font, fill=(255,255,255))
            out = tempfile.mktemp(suffix='_thumb.jpg')
            bg.save(out, quality=95)
            return out
        except Exception as e:
            logger.error(f"Video thumb error: {e}")
            return self.create_image_with_quote(video_path, quote)
    
    async def handle_stop_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid in self.processing_flags:
            self.processing_flags[uid] = False
            await update.message.reply_text("🛑 Processing stopped.", reply_markup=self.get_main_keyboard())
        else:
            await update.message.reply_text("ℹ️ No active process.", reply_markup=self.get_main_keyboard())
        return MAIN_MENU
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if uid not in self.user_sessions:
            return await self.start(update, context)
        sess = self.user_sessions[uid]
        media = sess['photos'] + sess['videos']
        quotes = sess['quotes']
        if not media or not quotes:
            return await update.message.reply_text("❌ Upload media & quotes first!", reply_markup=self.get_main_keyboard())
        sess['processed_media'].clear()
        self.processing_flags[uid] = True
        msg = await update.message.reply_text("🔄 Creating your reels...", parse_mode='Markdown')
        total = len(media) * len(quotes)
        done = 0
        for mi, m in enumerate(media):
            for qi, q in enumerate(quotes):
                if not self.processing_flags.get(uid, True):
                    await msg.edit_text("🛑 Stopped by user.", parse_mode='Markdown')
                    return MAIN_MENU
                done += 1
                await msg.edit_text(f"🔄 {done}/{total}", parse_mode='Markdown')
                path = m['file_path']
                out = (self.create_image_with_quote if m['type']=='image' else self.create_video_thumbnail)(path, q)
                if os.path.exists(out):
                    sess['processed_media'].append({'path': out, 'quote': q})
                await asyncio.sleep(0.1)
        self.processing_flags.pop(uid, None)
        if sess['processed_media']:
            await msg.edit_text(f"✅ Created {len(sess['processed_media'])} reels!", parse_mode='Markdown')
            for idx, item in enumerate(sess['processed_media']):
                with open(item['path'], 'rb') as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption=f"Reel {idx+1}\n{item['quote']}",
                        reply_markup=self.get_save_keyboard(idx),
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.3)
            await update.message.reply_text("🎉 Done! Use Save buttons or Save All.", reply_markup=self.get_main_keyboard())
        else:
            await msg.edit_text("❌ No reels created.", reply_markup=self.get_main_keyboard())
        return MAIN_MENU
    
    async def handle_save_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id
        idx = int(query.data.split('_')[1])
        sess = self.user_sessions.get(uid, {})
        pm = sess.get('processed_media', [])
        if 0 <= idx < len(pm):
            item = pm[idx]
            if os.path.exists(item['path']):
                with open(item['path'], 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=f"islamic_reel_{idx+1}.jpg",
                        caption=f"💾 Reel {idx+1}\n{item['quote']}"
                    )
                await query.edit_message_reply_markup(None)
                return
        await query.message.reply_text("❌ Could not save reel.")
    
    async def handle_save_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        sess = self.user_sessions.get(uid, {})
        pm = sess.get('processed_media', [])
        if not pm:
            return await update.message.reply_text("❌ No reels to save.", reply_markup=self.get_main_keyboard())
        status = await update.message.reply_text(f"💾 Sending {len(pm)} reels...", parse_mode='Markdown')
        cnt = 0
        for idx, item in enumerate(pm):
            if os.path.exists(item['path']):
                with open(item['path'], 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=f"islamic_reel_{idx+1}.jpg",
                        caption=f"Reel {idx+1}\n{item['quote']}"
                    )
                cnt += 1
                await asyncio.sleep(0.3)
        await status.edit_text(f"✅ Sent {cnt} reels!", parse_mode='Markdown')
        return MAIN_MENU
    
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        self.processing_flags.pop(uid, None)
        sess = self.user_sessions.get(uid, {})
        for m in sess.get('photos', []) + sess.get('videos', []):
            try: os.unlink(m['file_path'])
            except: pass
        for m in sess.get('processed_media', []):
            try: os.unlink(m['path'])
            except: pass
        self.user_sessions[uid] = {'photos': [], 'videos': [], 'quotes': [], 'processed_media': []}
        await update.message.reply_text("🔄 Reset done!", reply_markup=self.get_main_keyboard())
        return MAIN_MENU

# ----------------------------------------
# Setup Conversation & Handlers
# ----------------------------------------
def setup_bot() -> Application:
    bot = IslamicReelsBot()
    app = Application.builder().token(BOT_TOKEN).build()
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
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(bot.handle_save_callback, pattern=r"^save_\d+$"))
    return app

# ----------------------------------------
# Forever‐Running Logic
# ----------------------------------------
async def run_bot_forever():
    restart_count = 0
    max_restarts = 1000
    while restart_count < max_restarts:
        restart_count += 1
        try:
            print(f"🔄 Starting Bot (Attempt {restart_count})")
            app = setup_bot()
            # هذه الدالة تقوم بالتشغيل الكامل و البقاء في وضع الاستماع
            await app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
            # إذا خرج run_polling بسلام (مثلاً عند إيقاف يدوي)، نكسر الحلقة
            break
        except (asyncio.CancelledError, KeyboardInterrupt):
            print("🛑 Bot stopped by user.")
            break
        except Exception as e:
            print(f"💥 Crashed with: {e}\n🔄 Restarting in 5s...")
            try:
                await app.stop()
                await app.shutdown()
            except:
                pass
            await asyncio.sleep(5)
    print("🔴 Bot has stopped permanently.")

def signal_handler(sig, frame):
    print(f"\n🛑 Received signal {sig}, shutting down.")
    sys.exit(0)

async def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    await run_bot_forever()

if __name__ == '__main__':
    print("🚀 Launching Islamic Reels Bot...")
    if not BOT_TOKEN:
        print("❌ Missing BOT_TOKEN!"); sys.exit(1)
    asyncio.run(main())
