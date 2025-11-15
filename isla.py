import os
import tempfile
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import asyncio
from flask import Flask

# Bot Configuration - Use environment variable for Render
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0')

# Conversation states
MAIN_MENU, UPLOADING_PHOTOS, ADDING_QUOTES = range(3)

# Create Flask app for web server
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Islamic Reels Bot is running!"

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
            "📤 *Send your photos*:\n\nSend multiple photos one by one.\nClick '📝 Add Quotes' when done.",
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
            f"Click '🎬 Make Reels' to create!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    def is_arabic_text(self, text):
        """Check if text contains Arabic characters"""
        arabic_range = range(0x0600, 0x06FF)  # Arabic Unicode range
        return any(ord(char) in arabic_range for char in text)
    
    def process_arabic_line(self, line):
        """Process a single line of Arabic text with proper reshaping and bidirectional support"""
        try:
            # Reshape Arabic text for proper display
            reshaped_text = arabic_reshaper.reshape(line)
            # Apply bidirectional algorithm for RTL display
            processed_text = get_display(reshaped_text)
            return processed_text
        except:
            # Fallback if processing fails
            return line
    
    def split_text_into_lines(self, text, font, max_width):
        """Split text into lines that fit within max_width, preserving line breaks"""
        lines = []
        
        # First, split by actual line breaks to preserve user's intended structure
        original_lines = text.split('\n')
        
        for original_line in original_lines:
            if not original_line.strip():
                lines.append('')
                continue
                
            words = original_line.split()
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
                
                if text_width < max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
        
        return lines
    
    def create_image_with_quote(self, image_path, quote):
        """Create beautiful image with quote in the MIDDLE - supports Arabic with correct line order"""
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
            
            # Choose font based on text language
            if self.is_arabic_text(quote):
                # Arabic font - try different Arabic fonts
                arabic_fonts = [
                    "arial.ttf",  # Some versions support Arabic
                    "tahoma.ttf",
                    "seguiui.ttf",
                    "simpo.ttf",
                    "arialuni.ttf"
                ]
                font = None
                for font_path in arabic_fonts:
                    try:
                        font = ImageFont.truetype(font_path, 42)
                        break
                    except:
                        continue
                if font is None:
                    # Fallback to default font
                    font = ImageFont.load_default()
                
                # Process Arabic text line by line to maintain correct order
                lines = self.split_text_into_lines(quote, font, width * 0.8)
                # Process each line individually for proper Arabic display
                processed_lines = [self.process_arabic_line(line) for line in lines]
            else:
                # English/other languages font
                try:
                    font = ImageFont.truetype("arial.ttf", 45)
                except:
                    font = ImageFont.load_default()
                lines = self.split_text_into_lines(quote, font, width * 0.8)
                processed_lines = lines
            
            # Calculate text position - CENTER of the image
            line_height = 60
            total_height = len(processed_lines) * line_height
            text_y = (height - total_height) // 2  # Center vertically
            
            # Draw semi-transparent background for text
            padding = 25
            bg_height = total_height + (padding * 2)
            bg_width = width - 100
            bg_x = (width - bg_width) // 2
            bg_y = text_y - padding
            
            # Create transparent overlay
            overlay = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 180))
            background.paste(overlay, (bg_x, bg_y), overlay)
            
            # Draw text - maintaining the original line order
            for i, line in enumerate(processed_lines):
                if not line.strip():  # Skip empty lines
                    continue
                    
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (width - text_width) // 2
                y_pos = text_y + (i * line_height)
                
                # Text shadow for better readability
                draw.text((x_pos+3, y_pos+3), line, font=font, fill=(0, 0, 0, 200))
                # Main text (white)
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255))
            
            # Save result
            output_path = tempfile.mktemp(suffix='_quote.jpg')
            background.save(output_path, quality=95)
            
            return output_path
            
        except Exception as e:
            print(f"Error creating image: {e}")
            return image_path
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create images with quotes and send them with download buttons"""
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
        
        # Process each photo with a quote
        total = min(len(photos), len(quotes))
        created = 0
        
        for i in range(total):
            try:
                await processing_msg.edit_text(f"🔄 Creating reel {i+1}/{total}...")
                
                photo_path = photos[i]['file_path']
                quote = quotes[i % len(quotes)]
                
                # Create image with quote
                result_path = self.create_image_with_quote(photo_path, quote)
                
                if result_path and os.path.exists(result_path):
                    session['processed_images'].append({
                        'image_path': result_path,
                        'quote': quote,
                        'index': i
                    })
                    created += 1
                    
            except Exception as e:
                print(f"Error with image {i}: {e}")
                continue
        
        # Send all created reels with download buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ Created {created} reels! Sending them now...")
            
            for i, img_data in enumerate(session['processed_images']):
                try:
                    if os.path.exists(img_data['image_path']):
                        with open(img_data['image_path'], 'rb') as f:
                            await update.message.reply_photo(
                                photo=f,
                                caption=f"**Reel {i+1}**\n{img_data['quote']}",
                                reply_markup=self.get_download_keyboard(i),
                                parse_mode='Markdown'
                            )
                        # Small delay to avoid rate limits
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    print(f"Error sending reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *All {created} reels sent!*\n\n"
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
                            # Send the image as a document (so user can download it directly)
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
                print(f"Download error: {e}")
                await query.message.reply_text("❌ Error downloading reel.")
    
    async def handle_download_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download all reels as a zip file"""
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
        
        status_msg = await update.message.reply_text("📦 Preparing all reels for download...")
        
        # Send each reel as a downloadable document
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
                    await asyncio.sleep(1)  # Avoid rate limits
            except Exception as e:
                print(f"Error sending reel {i}: {e}")
                continue
        
        await status_msg.edit_text(f"✅ Sent {sent} reels as downloadable files!")
        return MAIN_MENU
    
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset everything"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            # Cleanup files
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
            
            # Reset session
            self.user_sessions[user_id] = {'photos': [], 'quotes': [], 'processed_images': []}
        
        await update.message.reply_text(
            "🔄 Reset complete! Start fresh.",
            reply_markup=self.get_main_keyboard()
        )
        return MAIN_MENU
    
    def run_bot(self):
        """Start the bot"""
        # Create application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.Regex('^📤 Upload Photos$'), self.handle_upload_photos),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), self.handle_add_quotes),
                    MessageHandler(filters.Regex('^🎬 Make Reels$'), self.handle_make_reels),
                    MessageHandler(filters.Regex('^📥 Download All$'), self.handle_download_all),
                    MessageHandler(filters.Regex('^🔄 Reset$'), self.handle_reset),
                ],
                UPLOADING_PHOTOS: [
                    MessageHandler(filters.PHOTO, self.handle_photos),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), self.handle_add_quotes),
                ],
                ADDING_QUOTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_quotes)
                ]
            },
            fallbacks=[CommandHandler('start', self.start)]
        )
        
        # Add callback handler for download buttons
        app.add_handler(CallbackQueryHandler(self.handle_download_callback, pattern="^download_"))
        app.add_handler(conv_handler)
        
        print("🤖 Islamic Reels Bot Starting...")
        print("Bot is running! Press Ctrl+C to stop")
        app.run_polling()

def run_flask():
    """Run Flask app for web server"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Run the bot
if __name__ == '__main__':
    bot = IslamicReelsBot()
    
    # Start both bot and web server
    import threading
    
    # Start bot in a separate thread
    bot_thread = threading.Thread(target=bot.run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask web server
    run_flask()
