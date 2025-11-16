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

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_PHOTOS, ADDING_QUOTES = range(3)

class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
    
    def get_main_keyboard(self):
        """Create main menu buttons"""
        keyboard = [
            [KeyboardButton("📤 Upload Photos"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Reels"), KeyboardButton("📥 Download All")],
            [KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_download_keyboard(self, image_index):
        """Create download button for each reel"""
        keyboard = [
            [InlineKeyboardButton("📥 Download This Reel", callback_data=f"download_{image_index}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'photos': [],
            'quotes': [],
            'processed_images': []
        }
        
        welcome_text = """
🕌 *Islamic Reels Maker*

*3 Simple Steps:*

1. 📤 *Upload Photos* - Send your images
2. 📝 *Add Quotes* - Write your custom quotes  
3. 🎬 *Make Reels* - Create images with quotes
4. 📥 *Download* - Get all images

*New Feature:* Upload 1 photo + multiple quotes = multiple reels!

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
    
    async def handle_upload_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        await update.message.reply_text(
            "📤 *Send your photos*:\n\nSend multiple photos one by one.\nClick '📝 Add Quotes' when done.\n\n*Tip:* Upload 1 photo + multiple quotes to create multiple reels from the same image!",
            parse_mode='Markdown'
        )
        return UPLOADING_PHOTOS
    
    async def handle_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process uploaded photos"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        if update.message.photo:
            try:
                # Get the photo
                photo_file = await update.message.photo[-1].get_file()
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    await photo_file.download_to_drive(temp_file.name)
                    temp_path = temp_file.name
                
                # Store photo info
                self.user_sessions[user_id]['photos'].append({
                    'file_path': temp_path,
                    'file_id': photo_file.file_id
                })
                
                count = len(self.user_sessions[user_id]['photos'])
                await update.message.reply_text(
                    f"✅ Photo {count} received!",
                    reply_markup=self.get_main_keyboard()
                )
                
            except Exception as e:
                logger.error(f"Error uploading photo: {e}")
                await update.message.reply_text(
                    "❌ Error uploading photo. Try again.",
                    reply_markup=self.get_main_keyboard()
                )
        
        return UPLOADING_PHOTOS
    
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
            f"📝 *Add your quotes*:\n\nYou have {photo_count} photos.\n"
            f"Send your quotes (one quote per line):\n\n"
            f"*New Feature:* If you upload 1 photo and multiple quotes, you'll get multiple reels from the same image!\n\n"
            f"*يدعم اللغة العربية والحركات*\n"
            f"*Supports Arabic with Harakat*\n\n"
            f"Example Arabic:\n"
            f"رَّبِّ أَدْخِلْنِي مُدْخَلَ صِدْقٍ\nوَأَخْرِجْنِي مُخْرَجَ صِدْقٍ\nوَاجْعَل لِّي مِن لَّدُنكَ سُلْطَانًا نَّصِيرًا",
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
    
    def get_english_font(self, size):
        """Get English font with fallbacks"""
        english_fonts = [
            "arial.ttf",
            "times.ttf",
            "helvetica.ttf",
            "verdana.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ]
        
        for font_path in english_fonts:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
                else:
                    # Try to load by name
                    return ImageFont.truetype(font_path, size)
            except Exception as e:
                continue
        
        # Fallback to default font
        logger.warning("Using default font for English")
        try:
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()
    
    def get_arabic_font(self, size):
        """Get Arabic-compatible font with fallbacks"""
        arabic_fonts = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "arial.ttf",
            "times.ttf"
        ]
        
        for font_path in arabic_fonts:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
                else:
                    return ImageFont.truetype(font_path, size)
            except Exception as e:
                continue
        
        # Ultimate fallback
        logger.warning("Using default font for Arabic")
        try:
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()
    
    def process_arabic_text(self, text):
        """Process Arabic text with proper reshaping and bidirectional support"""
        try:
            # Reshape Arabic text for proper display
            reshaped_text = arabic_reshaper.reshape(text)
            # Apply bidirectional algorithm for RTL display
            processed_text = get_display(reshaped_text)
            return processed_text
        except Exception as e:
            logger.error(f"Error processing Arabic text: {e}")
            return text
    
    def split_english_text(self, text, font, max_width):
        """Split English text into lines that fit within max_width"""
        lines = []
        
        # Split by user's line breaks first
        user_lines = text.split('\n')
        
        for user_line in user_lines:
            if not user_line.strip():
                lines.append('')
                continue
            
            words = user_line.split()
            current_line = []
            
            for word in words:
                # Test line with new word
                test_line = ' '.join(current_line + [word])
                
                # Get text dimensions
                try:
                    bbox = font.getbbox(test_line)
                    text_width = bbox[2] - bbox[0]
                except:
                    # Fallback for older PIL versions
                    text_width = font.getlength(test_line)
                
                if text_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return lines
    
    def split_arabic_text(self, text, font, max_width):
        """Split Arabic text into lines that fit within max_width"""
        lines = []
        
        # Process the entire text first
        processed_text = self.process_arabic_text(text)
        
        # Split by user's line breaks first
        user_lines = processed_text.split('\n')
        
        for user_line in user_lines:
            if not user_line.strip():
                lines.append('')
                continue
            
            words = user_line.split()
            current_line = []
            
            for word in words:
                # Test line with new word
                test_line = ' '.join(current_line + [word])
                test_line_processed = self.process_arabic_text(test_line)
                
                # Get text dimensions
                try:
                    bbox = font.getbbox(test_line_processed)
                    text_width = bbox[2] - bbox[0]
                except:
                    text_width = font.getlength(test_line_processed)
                
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
        """Create beautiful image with quote in the MIDDLE - supports both Arabic and English"""
        try:
            # Open original image
            original = Image.open(image_path)
            
            # Create Instagram-size image (1080x1350 - 4:5 ratio)
            width, height = 1080, 1350
            background = Image.new('RGB', (width, height), (0, 0, 0))
            
            # Resize original to fit width while maintaining aspect ratio
            original.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # Calculate position to center the image
            x = (width - original.width) // 2
            y = (height - original.height) // 2
            
            # Paste image onto background
            background.paste(original, (x, y))
            
            draw = ImageDraw.Draw(background)
            
            # Check if text is Arabic
            is_arabic = self.is_arabic_text(quote)
            
            # Choose font and size based on language
            if is_arabic:
                # Arabic settings
                font_size = 65
                font = self.get_arabic_font(font_size)
                lines = self.split_arabic_text(quote, font, width * 0.75)
                line_height = 85
            else:
                # English settings - PROPER FONT AND SIZE
                font_size = 55
                font = self.get_english_font(font_size)
                lines = self.split_english_text(quote, font, width * 0.75)
                line_height = 75
            
            # Calculate text position - CENTER of the image
            total_height = len(lines) * line_height
            text_y = (height - total_height) // 2
            
            # Draw semi-transparent background for text
            padding = 40
            bg_height = total_height + (padding * 2)
            bg_width = width - 100
            bg_x = (width - bg_width) // 2
            bg_y = text_y - padding
            
            # Create transparent overlay for better text readability
            overlay = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 200))
            background.paste(overlay, (bg_x, bg_y), overlay)
            
            # Draw text lines
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                
                # For Arabic, process the line
                if is_arabic:
                    line = self.process_arabic_text(line)
                
                # Get text dimensions
                try:
                    bbox = font.getbbox(line)
                    text_width = bbox[2] - bbox[0]
                except:
                    text_width = font.getlength(line)
                
                # Calculate x position based on language
                if is_arabic:
                    # For Arabic (RTL), align to the right within the background
                    x_pos = bg_x + bg_width - text_width - 40
                else:
                    # For English (LTR), center the text
                    x_pos = (width - text_width) // 2
                
                y_pos = text_y + (i * line_height)
                
                # Draw text shadow for better readability
                shadow_offset = 3
                draw.text((x_pos + shadow_offset, y_pos + shadow_offset), line, font=font, fill=(0, 0, 0, 180))
                
                # Draw main text (white)
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255))
            
            # Save result with high quality
            output_path = tempfile.mktemp(suffix='_quote.jpg')
            background.save(output_path, quality=95, optimize=True)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating image: {e}")
            # Fallback: return original image if processing fails
            return image_path
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create images with quotes - supports multiple quotes per photo"""
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
        session['processed_images'] = []
        
        processing_msg = await update.message.reply_text("🔄 Creating your reels...")
        
        # Create multiple combinations
        total_combinations = len(photos) * len(quotes)
        created = 0
        
        for photo_index, photo in enumerate(photos):
            for quote_index, quote in enumerate(quotes):
                try:
                    current_index = created + 1
                    await processing_msg.edit_text(f"🔄 Creating reel {current_index}/{total_combinations}...")
                    
                    photo_path = photo['file_path']
                    
                    # Create image with quote
                    result_path = self.create_image_with_quote(photo_path, quote)
                    
                    if result_path and os.path.exists(result_path):
                        session['processed_images'].append({
                            'image_path': result_path,
                            'quote': quote,
                            'photo_index': photo_index,
                            'quote_index': quote_index,
                            'index': created
                        })
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Error with combination {photo_index}-{quote_index}: {e}")
                    continue
        
        # Send all created reels with download buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ Created {created} reels! Sending them now...")
            
            for i, img_data in enumerate(session['processed_images']):
                try:
                    if os.path.exists(img_data['image_path']):
                        with open(img_data['image_path'], 'rb') as f:
                            caption = f"**Reel {i+1}**\n{img_data['quote']}"
                            if len(photos) == 1 and len(quotes) > 1:
                                caption += f"\n\n📷 Photo 1 • 📝 Quote {img_data['quote_index'] + 1}"
                            
                            await update.message.reply_photo(
                                photo=f,
                                caption=caption,
                                reply_markup=self.get_download_keyboard(i),
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
                f"Click the 📥 button under each reel to download it directly to your device!",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No reels were created. Please try again with different photos.",
                reply_markup=self.get_main_keyboard()
            )
        
        return MAIN_MENU
    
    async def handle_download_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle download button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('download_'):
            try:
                image_index = int(data.split('_')[1])
                
                if user_id in self.user_sessions:
                    session = self.user_sessions[user_id]
                    images = session['processed_images']
                    
                    if 0 <= image_index < len(images):
                        img_data = images[image_index]
                        
                        if os.path.exists(img_data['image_path']):
                            with open(img_data['image_path'], 'rb') as f:
                                await query.message.reply_document(
                                    document=f,
                                    filename=f"islamic_reel_{image_index + 1}.jpg",
                                    caption=f"📥 Downloaded: Reel {image_index + 1}\n{img_data['quote']}"
                                )
                            await query.edit_message_reply_markup(reply_markup=None)
                            return
                
                await query.message.reply_text("❌ Could not download this reel.")
                
            except Exception as e:
                logger.error(f"Download error: {e}")
                await query.message.reply_text("❌ Error downloading reel.")
    
    async def handle_download_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download all reels as individual files"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        images = self.user_sessions[user_id]['processed_images']
        
        if not images:
            await update.message.reply_text(
                "❌ No reels found! Create reels first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        status_msg = await update.message.reply_text(f"📦 Preparing {len(images)} reels for download...")
        
        sent = 0
        for i, img_data in enumerate(images):
            try:
                if os.path.exists(img_data['image_path']):
                    with open(img_data['image_path'], 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=f"islamic_reel_{i+1}.jpg",
                            caption=f"Reel {i+1}\n{img_data['quote']}"
                        )
                    sent += 1
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error sending reel {i}: {e}")
                continue
        
        await status_msg.edit_text(f"✅ Sent {sent} reels as downloadable files!")
        return MAIN_MENU
    
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset everything"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            for photo in session['photos']:
                try:
                    if os.path.exists(photo['file_path']):
                        os.unlink(photo['file_path'])
                except:
                    pass
            
            for img in session['processed_images']:
                try:
                    if os.path.exists(img['image_path']):
                        os.unlink(img['image_path'])
                except:
                    pass
            
            self.user_sessions[user_id] = {'photos': [], 'quotes': [], 'processed_images': []}
        
        await update.message.reply_text(
            "🔄 Reset complete! Start fresh.",
            reply_markup=self.get_main_keyboard()
        )
        return MAIN_MENU

def run_bot():
    """Run the bot with polling"""
    bot = IslamicReelsBot()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^📤 Upload Photos$'), bot.handle_upload_photos),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                MessageHandler(filters.Regex('^🎬 Make Reels$'), bot.handle_make_reels),
                MessageHandler(filters.Regex('^📥 Download All$'), bot.handle_download_all),
                MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
            ],
            UPLOADING_PHOTOS: [
                MessageHandler(filters.PHOTO, bot.handle_photos),
                MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
            ],
            ADDING_QUOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_quotes)
            ]
        },
        fallbacks=[CommandHandler('start', bot.start)]
    )
    
    application.add_handler(CallbackQueryHandler(bot.handle_download_callback, pattern="^download_"))
    application.add_handler(conv_handler)
    
    print("🤖 Islamic Reels Bot Starting...")
    print("Bot is running with polling! Press Ctrl+C to stop")
    
    application.run_polling()

if __name__ == '__main__':
    if os.environ.get('RENDER'):
        print("🚀 Starting bot on Render...")
        run_bot()
    else:
        print("🔧 Starting bot locally...")
        run_bot()
