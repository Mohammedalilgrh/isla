import os
import tempfile
import asyncio
import threading
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import logging
import requests
import time

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES, PROCESSING = range(4)

class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_tasks = {}  # To track ongoing processes
        self.setup_fonts()
    
    def setup_fonts(self):
        """Setup Arabic and English fonts"""
        try:
            # Create fonts directory if it doesn't exist
            os.makedirs('fonts', exist_ok=True)
            
            # Download basic fonts if they don't exist
            self.download_fonts()
            
        except Exception as e:
            logger.error(f"Error setting up fonts: {e}")
    
    def download_fonts(self):
        """Download basic Arabic fonts"""
        font_urls = {
            'amiri': 'https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip',
            'noto': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf'
        }
        
        for name, url in font_urls.items():
            font_path = f'fonts/{name}.ttf'
            if not os.path.exists(font_path):
                try:
                    response = requests.get(url, timeout=30)
                    if response.status_code == 200:
                        with open(font_path, 'wb') as f:
                            f.write(response.content)
                        logger.info(f"Downloaded {name} font")
                except Exception as e:
                    logger.error(f"Failed to download {name} font: {e}")
    
    def get_main_keyboard(self):
        """Create main menu buttons"""
        keyboard = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Reels"), KeyboardButton("💾 Save All")],
            [KeyboardButton("🛑 Stop"), KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_save_keyboard(self, media_index):
        """Create save button for each reel"""
        keyboard = [
            [InlineKeyboardButton("💾 Save This Reel", callback_data=f"save_{media_index}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'photos': [],
            'quotes': [],
            'processed_media': []
        }
        
        welcome_text = """
🕌 *Islamic Reels Maker* 🌟

*3 Simple Steps:*

1. 📤 *Upload Photos* - Send your images
2. 📝 *Add Quotes* - Write your custom quotes  
3. 🎬 *Make Reels* - Create images with quotes
4. 💾 *Save* - Save all reels directly to your device

*New Features:*
• Multiple languages supported 🌍
• Stop processing anytime 🛑

*يدعم اللغة العربية والحركات*
*Supports Arabic with Harakat*

*Current Status:*
📷 Photos: 0
📝 Quotes: 0
🎬 Ready: 0

Use the buttons below!
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    async def handle_upload_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle media uploads"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        await update.message.reply_text(
            "📤 *Send your photos*:\n\n"
            "• Send multiple photos one by one\n"
            "• Click '📝 Add Quotes' when done\n"
            "• Supported formats: JPG, PNG\n\n"
            "*Tip:* Upload 1 photo + multiple quotes to create multiple reels from the same image!",
            parse_mode='Markdown'
        )
        return UPLOADING_MEDIA
    
    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process uploaded media"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return UPLOADING_MEDIA
        
        try:
            if update.message.photo:
                # Handle photo upload
                photo_file = await update.message.photo[-1].get_file()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    await photo_file.download_to_drive(temp_file.name)
                    temp_path = temp_file.name
                
                self.user_sessions[user_id]['photos'].append({
                    'file_path': temp_path,
                    'file_id': photo_file.file_id,
                    'type': 'image'
                })
                
                count = len(self.user_sessions[user_id]['photos'])
                await update.message.reply_text(
                    f"✅ Photo {count} received!",
                    reply_markup=self.get_main_keyboard()
                )
        
        except Exception as e:
            logger.error(f"Error uploading media: {e}")
            await update.message.reply_text(
                "❌ Error uploading photo. Try again.",
                reply_markup=self.get_main_keyboard()
            )
        
        return UPLOADING_MEDIA
    
    async def handle_add_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quote input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        photo_count = len(self.user_sessions[user_id]['photos'])
        
        if photo_count == 0:
            await update.message.reply_text(
                "❌ Please upload photos first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        await update.message.reply_text(
            f"📝 *Add your quotes*:\n\n"
            f"You have {photo_count} photos.\n"
            f"Send your quotes (one quote per line):\n\n"
            f"*New Feature:* If you upload 1 photo and multiple quotes, you'll get multiple reels from the same image!\n\n"
            f"*يدعم اللغة العربية والحركات*\n"
            f"*Supports Arabic with Harakat*\n\n"
            f"*Example Arabic:*\n"
            f"رَّبِّ أَدْخِلْنِي مُدْخَلَ صِدْقٍ\nوَأَخْرِجْنِي مُخْرَجَ صِدْقٍ\nوَاجْعَل لِّي مِن لَّدُنكَ سُلْطَانًا نَّصِيرًا\n\n"
            f"*Example English:*\n"
            f"O my Lord! Let my entry be good\nAnd likewise my exit be good\nAnd grant me from You an authority to help me",
            parse_mode='Markdown'
        )
        return ADDING_QUOTES
    
    async def handle_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user quotes"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        quotes_text = update.message.text
        quotes_list = [q.strip() for q in quotes_text.split('\n') if q.strip()]
        
        if not quotes_list:
            await update.message.reply_text(
                "❌ No quotes found. Please send quotes:",
                reply_markup=self.get_main_keyboard()
            )
            return ADDING_QUOTES
        
        photo_count = len(self.user_sessions[user_id]['photos'])
        
        # Store quotes
        self.user_sessions[user_id]['quotes'] = quotes_list
        
        await update.message.reply_text(
            f"✅ *Quotes received!*\n\n"
            f"📷 Photos: {photo_count}\n"
            f"📝 Quotes: {len(quotes_list)}\n\n"
            f"*Possible combinations:* {photo_count} photos × {len(quotes_list)} quotes = {photo_count * len(quotes_list)} possible reels!\n\n"
            f"Click '🎬 Make Reels' to create!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    def is_arabic_text(self, text):
        """Check if text contains Arabic characters"""
        arabic_range = range(0x0600, 0x06FF)  # Arabic Unicode range
        return any(ord(char) in arabic_range for char in text)
    
    def get_font(self, size, is_arabic=False):
        """Get appropriate font based on language"""
        if is_arabic:
            # Try Arabic fonts
            arabic_fonts = [
                'fonts/amiri.ttf',
                'fonts/noto.ttf',
                'fonts/tahoma.ttf'
            ]
            
            for font_path in arabic_fonts:
                try:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                except:
                    continue
        else:
            # English fonts
            english_fonts = [
                'fonts/arial.ttf',
                'arial.ttf'
            ]
            
            for font_path in english_fonts:
                try:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                except:
                    continue
        
        # Ultimate fallback
        return ImageFont.load_default()
    
    def process_arabic_text(self, text):
        """Process Arabic text with proper reshaping and bidirectional support"""
        try:
            arabic_reshaper.config.forget_letters()
            reshaped_text = arabic_reshaper.reshape(text)
            processed_text = get_display(reshaped_text)
            return processed_text
        except Exception as e:
            logger.error(f"Error processing Arabic text: {e}")
            return text
    
    def split_text_to_lines(self, text, font, max_width, is_arabic=False):
        """Split text into lines that fit within max_width"""
        lines = []
        
        # Process Arabic text
        if is_arabic:
            processed_text = self.process_arabic_text(text)
        else:
            processed_text = text
        
        # Split by user's line breaks first
        user_lines = processed_text.split('\n')
        
        for user_line in user_lines:
            if not user_line.strip():
                lines.append('')
                continue
            
            words = user_line.split()
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                
                if is_arabic:
                    test_line_processed = self.process_arabic_text(test_line)
                else:
                    test_line_processed = test_line
                
                bbox = font.getbbox(test_line_processed)
                text_width = bbox[2] - bbox[0]
                
                if text_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return lines
    
    def create_image_with_quote(self, image_path, quote):
        """Create beautiful image with quote"""
        try:
            original = Image.open(image_path)
            width, height = 1080, 1350
            background = Image.new('RGB', (width, height), (0, 0, 0))
            
            original.thumbnail((width, height), Image.Resampling.LANCZOS)
            x = (width - original.width) // 2
            y = (height - original.height) // 2
            background.paste(original, (x, y))
            
            draw = ImageDraw.Draw(background)
            is_arabic = self.is_arabic_text(quote)
            
            font_size = 60 if is_arabic else 50
            font = self.get_font(font_size, is_arabic)
            
            lines = self.split_text_to_lines(quote, font, width * 0.8, is_arabic)
            line_height = 80 if is_arabic else 70
            total_height = len(lines) * line_height
            text_y = (height - total_height) // 2
            
            # Draw semi-transparent background
            padding = 40
            bg_height = total_height + (padding * 2)
            bg_width = width - 100
            bg_x = (width - bg_width) // 2
            bg_y = text_y - padding
            
            overlay = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 180))
            background.paste(overlay, (bg_x, bg_y), overlay)
            
            # Draw text lines
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                
                if is_arabic:
                    line = self.process_arabic_text(line)
                
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                
                if is_arabic:
                    x_pos = bg_x + bg_width - text_width - 40
                else:
                    x_pos = (width - text_width) // 2
                
                y_pos = text_y + (i * line_height)
                
                # Draw text shadow
                shadow_offset = 3
                draw.text((x_pos + shadow_offset, y_pos + shadow_offset), line, font=font, fill=(0, 0, 0, 200))
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255))
            
            output_path = tempfile.mktemp(suffix='_quote.jpg')
            background.save(output_path, quality=95)
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating image: {e}")
            return image_path
    
    async def handle_stop_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop ongoing processing"""
        user_id = update.effective_user.id
        
        if user_id in self.processing_tasks:
            self.processing_tasks[user_id] = False
            await update.message.reply_text(
                "🛑 Processing stopped!",
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                "ℹ️ No ongoing process to stop.",
                reply_markup=self.get_main_keyboard()
            )
        
        return MAIN_MENU
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create reels with quotes"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        photos = session['photos']
        quotes = session['quotes']
        
        if not photos or not quotes:
            await update.message.reply_text(
                "❌ Please upload both photos and quotes first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        # Clear previous results
        session['processed_media'] = []
        self.processing_tasks[user_id] = True
        
        processing_msg = await update.message.reply_text("🔄 Creating your reels...")
        
        total_combinations = len(photos) * len(quotes)
        created = 0
        
        for photo_index, photo in enumerate(photos):
            for quote_index, quote in enumerate(quotes):
                # Check if user stopped the process
                if not self.processing_tasks.get(user_id, True):
                    await processing_msg.edit_text("🛑 Process stopped by user!")
                    return MAIN_MENU
                
                try:
                    current_index = created + 1
                    await processing_msg.edit_text(f"🔄 Creating reel {current_index}/{total_combinations}...")
                    
                    photo_path = photo['file_path']
                    
                    # Create image with quote
                    result_path = self.create_image_with_quote(photo_path, quote)
                    
                    if result_path and os.path.exists(result_path):
                        session['processed_media'].append({
                            'media_path': result_path,
                            'quote': quote,
                            'photo_index': photo_index,
                            'quote_index': quote_index,
                            'index': created
                        })
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Error with combination {photo_index}-{quote_index}: {e}")
                    continue
        
        # Clean up processing task
        if user_id in self.processing_tasks:
            del self.processing_tasks[user_id]
        
        # Send all created reels with save buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ Created {created} reels! Sending them now...")
            
            for i, media_data in enumerate(session['processed_media']):
                try:
                    if os.path.exists(media_data['media_path']):
                        with open(media_data['media_path'], 'rb') as f:
                            caption = f"**Reel {i+1}**\n{media_data['quote']}"
                            if len(photos) == 1 and len(quotes) > 1:
                                caption += f"\n\n📷 Photo 1 • 📝 Quote {media_data['quote_index'] + 1}"
                            
                            await update.message.reply_photo(
                                photo=f,
                                caption=caption,
                                reply_markup=self.get_save_keyboard(i),
                                parse_mode='Markdown'
                            )
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Error sending reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *All {created} reels sent!*\n\n"
                f"*Combination Summary:*\n"
                f"📷 Photos: {len(photos)}\n"
                f"📝 Quotes: {len(quotes)}\n"
                f"🎬 Created: {created} reels\n\n"
                f"Click the 💾 button under each reel to save it directly to your device!",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No reels were created. Please try again with different photos.",
                reply_markup=self.get_main_keyboard()
            )
        
        return MAIN_MENU
    
    async def handle_save_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle save button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('save_'):
            try:
                media_index = int(data.split('_')[1])
                
                if user_id in self.user_sessions:
                    session = self.user_sessions[user_id]
                    media_list = session['processed_media']
                    
                    if 0 <= media_index < len(media_list):
                        media_data = media_list[media_index]
                        
                        if os.path.exists(media_data['media_path']):
                            with open(media_data['media_path'], 'rb') as f:
                                await query.message.reply_document(
                                    document=f,
                                    filename=f"islamic_reel_{media_index + 1}.jpg",
                                    caption=f"💾 Saved: Reel {media_index + 1}\n{media_data['quote']}"
                                )
                            await query.edit_message_reply_markup(reply_markup=None)
                            return
                
                await query.message.reply_text("❌ Could not save this reel.")
                
            except Exception as e:
                logger.error(f"Save error: {e}")
                await query.message.reply_text("❌ Error saving reel.")
    
    async def handle_save_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save all reels as individual files"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        media_list = self.user_sessions[user_id]['processed_media']
        
        if not media_list:
            await update.message.reply_text(
                "❌ No reels found! Create reels first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        status_msg = await update.message.reply_text(f"💾 Saving {len(media_list)} reels...")
        
        sent = 0
        for i, media_data in enumerate(media_list):
            try:
                if os.path.exists(media_data['media_path']):
                    with open(media_data['media_path'], 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=f"islamic_reel_{i+1}.jpg",
                            caption=f"Reel {i+1}\n{media_data['quote']}"
                        )
                    sent += 1
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error saving reel {i}: {e}")
                continue
        
        await status_msg.edit_text(f"✅ Saved {sent} reels to your device!")
        return MAIN_MENU
    
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset everything"""
        user_id = update.effective_user.id
        
        # Stop any ongoing process
        if user_id in self.processing_tasks:
            self.processing_tasks[user_id] = False
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            
            # Clean up all temporary files
            for photo in session['photos']:
                try:
                    if os.path.exists(photo['file_path']):
                        os.unlink(photo['file_path'])
                except:
                    pass
            
            for media in session['processed_media']:
                try:
                    if os.path.exists(media['media_path']):
                        os.unlink(media['media_path'])
                except:
                    pass
            
            self.user_sessions[user_id] = {'photos': [], 'quotes': [], 'processed_media': []}
        
        await update.message.reply_text(
            "🔄 Reset complete! Start fresh.",
            reply_markup=self.get_main_keyboard()
        )
        return MAIN_MENU

def run_bot():
    """Run the bot with polling"""
    bot = IslamicReelsBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^📤 Upload Media$'), bot.handle_upload_media),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                MessageHandler(filters.Regex('^🎬 Make Reels$'), bot.handle_make_reels),
                MessageHandler(filters.Regex('^💾 Save All$'), bot.handle_save_all),
                MessageHandler(filters.Regex('^🛑 Stop$'), bot.handle_stop_process),
                MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
            ],
            UPLOADING_MEDIA: [
                MessageHandler(filters.PHOTO, bot.handle_media),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
            ],
            ADDING_QUOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_quotes)
            ]
        },
        fallbacks=[CommandHandler('start', bot.start)]
    )
    
    application.add_handler(CallbackQueryHandler(bot.handle_save_callback, pattern="^save_"))
    application.add_handler(conv_handler)
    
    print("🤖 Islamic Reels Bot Starting...")
    print("Bot is running with polling!")
    
    # Start the bot
    application.run_polling(
        drop_pending_updates=True,
        timeout=30,
        pool_timeout=30
    )

def main():
    """Main function to run the bot"""
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (attempt {attempt + 1}/{max_retries})...")
            run_bot()
        except Exception as e:
            print(f"❌ Bot crashed with error: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("💥 Max retries reached. Bot stopped.")
                raise

if __name__ == '__main__':
    # For Render, we need to run as a background worker
    print("🔧 Starting as Background Worker...")
    
    # Check if we're on Render
    if os.environ.get('RENDER'):
        print("🌐 Running on Render Cloud...")
        # Add health check endpoint for Render
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
            
            def log_message(self, format, *args):
                return  # Disable logging
        
        def start_health_server():
            server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
            print("❤️ Health check server running on port 8080")
            server.serve_forever()
        
        # Start health server in background thread
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()
    
    # Start the bot
    main()
