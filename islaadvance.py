from keep_alive import keep_alive
import requests
import time
import threading
import os
import tempfile
import asyncio
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import requests
import moviepy.editor as mp
from moviepy.editor import concatenate_videoclips, CompositeVideoClip, TextClip, ColorClip, AudioFileClip, concatenate_audioclips
import numpy as np
import random

# Start keep-alive server BEFORE starting the bot
keep_alive()

# Add this function for self-pinning
def self_ping():
    """Ping ourselves to stay awake"""
    try:
        requests.get("https://your-bot-name.onrender.com/", timeout=10)
        print(f"✅ Self-ping at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"⚠️ Self-ping failed: {e}")

# Start self-pinging in background
def start_self_ping():
    while True:
        self_ping()
        time.sleep(300)  # 5 minutes

ping_thread = threading.Thread(target=start_self_ping, daemon=True)
ping_thread.start()

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES, SELECTING_REEL_TYPE = range(4)

class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}  # To track and stop processing
        self.setup_fonts()
        self.download_background_music()  # Download default nasheed

    def setup_fonts(self):
        """Setup Arabic and English fonts"""
        try:
            os.makedirs('fonts', exist_ok=True)
            self.download_fonts()
        except Exception as e:
            logger.error(f"Error setting up fonts: {e}")

    def download_fonts(self):
        """Download basic fonts"""
        font_urls = {
            'amiri': 'https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip',
            'noto': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf',
            'arial': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf'
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

    def download_background_music(self):
        """Download a default soothing nasheed for video reels"""
        nasheed_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"  # Replace with actual Islamic nasheed URL
        nasheed_path = 'background_nasheed.mp3'
        if not os.path.exists(nasheed_path):
            try:
                response = requests.get(nasheed_url, timeout=30)
                if response.status_code == 200:
                    with open(nasheed_path, 'wb') as f:
                        f.write(response.content)
                    logger.info("Downloaded background nasheed")
            except Exception as e:
                logger.error(f"Failed to download background music: {e}")

    def get_main_keyboard(self):
        """Create main menu buttons"""
        keyboard = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Image Reels"), KeyboardButton("🎥 Make Video Reels")],
            [KeyboardButton("🖼️ Convert Pic to Reel"), KeyboardButton("💾 Save All")],
            [KeyboardButton("🛑 Stop Process"), KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_save_keyboard(self, media_index, is_video=False):
        """Create save button for each reel"""
        keyboard = [
            [InlineKeyboardButton("💾 Save This Reel", callback_data=f"save_{media_index}_{'video' if is_video else 'image'}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'photos': [],
            'videos': [],
            'quotes': [],
            'processed_images': [],  # For image reels
            'processed_videos': [],  # For video reels
            'pic_to_reel_photos': []  # For pic-to-reel feature
        }
        
        welcome_text = """🕌 Islamic Reels Maker 🌟

3 Simple Steps:

1️⃣ Upload Media - Send your images or short videos
2️⃣ Add Quotes - Write your custom quotes
3️⃣ Make Reels - Choose between Image or Video Reels!
4️⃣ Save - Save directly to your device

✨ New Advanced Features:
• Create REAL VIDEO REELS 🎥
• Bulk generation in seconds
• Elegant Arabic text animation
• Soothing background nasheeds
• Stop processing anytime 🛑
• Convert Pics to 17-sec Reels 🖼️

يدعم اللغة العربية والحركات
Supports Arabic with Harakat

Current Status:
📷 Photos: 0
🎥 Videos: 0
📝 Quotes: 0
🖼️ Image Reels: 0
🎬 Video Reels: 0

Use the buttons below to get started! 🚀
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
            "📤 *Send your photos or short videos*:\n\n"
            "• Send multiple files one by one\n"
            "• Click '📝 Add Quotes' when done\n"
            "• Supported: JPG, PNG, MP4 (short videos)\n\n"
            "💡 *Tip:* Upload 1 media + multiple quotes = multiple reels from the same file!",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
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
                    f"✅ Photo {count} received! 📷",
                    reply_markup=self.get_main_keyboard()
                )
                
            elif update.message.video:
                # Handle video upload
                video = update.message.video
                if video.duration > 60:  # Limit to 60 seconds
                    await update.message.reply_text(
                        "❌ Video too long! Please send videos under 60 seconds.",
                        reply_markup=self.get_main_keyboard()
                    )
                    return UPLOADING_MEDIA
                    
                video_file = await video.get_file()
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                    await video_file.download_to_drive(temp_file.name)
                    temp_path = temp_file.name
                
                self.user_sessions[user_id]['videos'].append({
                    'file_path': temp_path,
                    'file_id': video_file.file_id,
                    'type': 'video',
                    'duration': video.duration
                })
                
                count = len(self.user_sessions[user_id]['videos'])
                await update.message.reply_text(
                    f"✅ Video {count} received! 🎥",
                    reply_markup=self.get_main_keyboard()
                )
                
            elif update.message.document:
                # Handle document upload (could be video)
                mime_type = update.message.document.mime_type
                if mime_type and mime_type.startswith('video/'):
                    video_file = await update.message.document.get_file()
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        await video_file.download_to_drive(temp_file.name)
                        temp_path = temp_file.name
                    
                    self.user_sessions[user_id]['videos'].append({
                        'file_path': temp_path,
                        'file_id': video_file.file_id,
                        'type': 'video',
                        'duration': 0
                    })
                    
                    count = len(self.user_sessions[user_id]['videos'])
                    await update.message.reply_text(
                        f"✅ Video {count} received! 🎥",
                        reply_markup=self.get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Unsupported file type. Please send photos or videos.",
                        reply_markup=self.get_main_keyboard()
                    )
            else:
                await update.message.reply_text(
                    "❌ Unsupported file type. Please send photos or videos.",
                    reply_markup=self.get_main_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error uploading media: {e}")
            await update.message.reply_text(
                "❌ Error uploading media. Please try again.",
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
        video_count = len(self.user_sessions[user_id]['videos'])
        total_media = photo_count + video_count
        
        if total_media == 0:
            await update.message.reply_text(
                "❌ Please upload photos or videos first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
            
        await update.message.reply_text(
            f"📝 *Add your quotes*:\n\n"
            f"You have {photo_count} photos and {video_count} videos.\n"
            f"Send your quotes (one quote per line):\n\n"
            f"✨ *New Feature:* Upload 1 media + multiple quotes = multiple reels!\n\n"
            f"🌍 *Supports Multiple Languages:*\n"
            f"• Arabic with full harakat support\n"
            f"• English and other languages\n\n"
            f"📚 *Examples:*\n"
            f"*Arabic:*\n"
            f"رَّبِّ أَدْخِلْنِي مُدْخَلَ صِدْقٍ\nوَأَخْرِجْنِي مُخْرَجَ صِدْقٍ\n\n"
            f"*English:*\n"
            f"O my Lord! Let my entry be good\nAnd likewise my exit be good",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
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
                "❌ No quotes found. Please send valid quotes:",
                reply_markup=self.get_main_keyboard()
            )
            return ADDING_QUOTES
            
        photo_count = len(self.user_sessions[user_id]['photos'])
        video_count = len(self.user_sessions[user_id]['videos'])
        total_media = photo_count + video_count
        
        # Store quotes
        self.user_sessions[user_id]['quotes'] = quotes_list
        
        await update.message.reply_text(
            f"✅ *Quotes Received Successfully!* 📝\n\n"
            f"📊 *Your Collection:*\n"
            f"📷 Photos: {photo_count}\n"
            f"🎥 Videos: {video_count}\n"
            f"📝 Quotes: {len(quotes_list)}\n\n"
            f"🎬 *Possible Combinations:* {total_media} × {len(quotes_list)} = {total_media * len(quotes_list)} reels!\n\n"
            f"Click '🎬 Make Image Reels' or '🎥 Make Video Reels' to create your content!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU

    def is_arabic_text(self, text):
        """Check if text contains Arabic characters"""
        arabic_range = range(0x0600, 0x06FF)
        return any(ord(char) in arabic_range for char in text)

    def get_font_path(self, is_arabic=False):
        """Get appropriate font path based on language"""
        font_paths = [
            'fonts/amiri.ttf' if is_arabic else 'fonts/arial.ttf',
            'fonts/noto.ttf' if is_arabic else 'fonts/arial.ttf',
            'arial.ttf'
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                return font_path
        return None  # Will fall back to default

    def process_arabic_text(self, text):
        """Process Arabic text with proper reshaping"""
        try:
            arabic_reshaper.config.forget_letters()
            reshaped_text = arabic_reshaper.reshape(text)
            processed_text = get_display(reshaped_text)
            return processed_text
        except Exception as e:
            logger.error(f"Error processing Arabic text: {e}")
            return text

    def split_text_to_lines(self, text, font_size, max_width, is_arabic=False):
        """Split text into lines that fit within max_width using PIL"""
        # Use a dummy image to measure text width
        dummy_img = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        font_path = self.get_font_path(is_arabic)
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        
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
                    
                bbox = draw.textbbox((0, 0), test_line_processed, font=font)
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
        """Create beautiful image with quote (for image reels)"""
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
            font_path = self.get_font_path(is_arabic)
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            
            lines = self.split_text_to_lines(quote, font_size, width * 0.8, is_arabic)
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

    def create_video_thumbnail(self, video_path, quote):
        """Create a thumbnail from video with quote (simplified)"""
        try:
            # For simplicity, create an image thumbnail from video
            # In production, you might want to use moviepy or other libraries
            thumbnail_path = tempfile.mktemp(suffix='_thumbnail.jpg')
            
            # Create a simple colored background with the quote
            width, height = 1080, 1350
            background = Image.new('RGB', (width, height), (30, 60, 90))  # Islamic blue
            draw = ImageDraw.Draw(background)
            
            is_arabic = self.is_arabic_text(quote)
            font_size = 60 if is_arabic else 50
            font_path = self.get_font_path(is_arabic)
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            
            lines = self.split_text_to_lines(quote, font_size, width * 0.8, is_arabic)
            line_height = 80 if is_arabic else 70
            total_height = len(lines) * line_height
            text_y = (height - total_height) // 2
            
            # Draw decorative elements
            draw.rectangle([50, text_y-60, width-50, text_y+total_height+60], fill=(0, 0, 0, 180), outline=(255, 255, 255), width=3)
            
            # Draw text lines
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                    
                if is_arabic:
                    line = self.process_arabic_text(line)
                    
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (width - text_width) // 2
                y_pos = text_y + (i * line_height)
                
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255))
            
            background.save(thumbnail_path, quality=95)
            return thumbnail_path
        except Exception as e:
            logger.error(f"Error creating video thumbnail: {e}")
            return self.create_image_with_quote(video_path, quote)

    async def handle_stop_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop ongoing processing"""
        user_id = update.effective_user.id
        if user_id in self.processing_flags:
            self.processing_flags[user_id] = False
            await update.message.reply_text(
                "🛑 *Processing Stopped!*\n\nAll ongoing operations have been cancelled.",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ *No active process to stop.*\n\nThere are no ongoing operations.",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        return MAIN_MENU

    async def handle_make_image_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create image reels (static images with quotes)"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
            
        session = self.user_sessions[user_id]
        photos = session['photos']
        videos = session['videos']
        quotes = session['quotes']
        all_media = photos + videos
        
        if not all_media or not quotes:
            await update.message.reply_text(
                "❌ Please upload both media and quotes first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
            
        # Clear previous results and set processing flag
        session['processed_images'] = []
        self.processing_flags[user_id] = True
        
        processing_msg = await update.message.reply_text("🔄 *Starting to create your image reels...*", parse_mode='Markdown')
        
        total_combinations = len(all_media) * len(quotes)
        created = 0
        
        for media_index, media in enumerate(all_media):
            for quote_index, quote in enumerate(quotes):
                # Check if user stopped the process
                if not self.processing_flags.get(user_id, True):
                    await processing_msg.edit_text("🛑 *Process stopped by user!*", parse_mode='Markdown')
                    return MAIN_MENU
                    
                try:
                    current_index = created + 1
                    progress = f"🔄 Creating image {current_index}/{total_combinations}..."
                    await processing_msg.edit_text(progress)
                    
                    media_path = media['file_path']
                    if media['type'] == 'image':
                        result_path = self.create_image_with_quote(media_path, quote)
                    else:  # video
                        result_path = self.create_video_thumbnail(media_path, quote)
                    
                    if result_path and os.path.exists(result_path):
                        session['processed_images'].append({
                            'media_path': result_path,
                            'quote': quote,
                            'media_index': media_index,
                            'quote_index': quote_index,
                            'index': created,
                            'type': media['type']
                        })
                        created += 1
                        
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error with combination {media_index}-{quote_index}: {e}")
                    continue
        
        # Clean up processing flag
        if user_id in self.processing_flags:
            del self.processing_flags[user_id]
        
        # Send all created image reels with save buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ *Created {created} image reels! Sending them now...*", parse_mode='Markdown')
            
            for i, media_data in enumerate(session['processed_images']):
                try:
                    if not self.processing_flags.get(user_id, True):
                        break
                    if os.path.exists(media_data['media_path']):
                        with open(media_data['media_path'], 'rb') as f:
                            caption = f"**Image Reel {i+1}**\n{media_data['quote']}"
                            if len(all_media) == 1 and len(quotes) > 1:
                                caption += f"\n\n📝 Quote {media_data['quote_index'] + 1}"
                                
                            await update.message.reply_photo(
                                photo=f,
                                caption=caption,
                                reply_markup=self.get_save_keyboard(i, is_video=False),
                                parse_mode='Markdown'
                            )
                        await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error sending image reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *Successfully Created {created} Image Reels!*\n\n"
                f"📊 *Summary:*\n"
                f"📷 Photos: {len(photos)}\n"
                f"🎥 Videos: {len(videos)}\n"
                f"📝 Quotes: {len(quotes)}\n"
                f"🖼️ Created: {created} image reels\n\n"
                f"💾 *Click the 'Save' button under each image to download it directly to your device!*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No image reels were created. Please try again with different media or quotes.",
                reply_markup=self.get_main_keyboard()
            )
        return MAIN_MENU

    async def handle_make_video_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create REAL video reels with transitions, text animations, and background music"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
            
        session = self.user_sessions[user_id]
        photos = session['photos']
        videos = session['videos']
        quotes = session['quotes']
        all_media = photos + videos
        
        if not all_media or not quotes:
            await update.message.reply_text(
                "❌ Please upload both media and quotes first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
            
        # Clear previous results and set processing flag
        session['processed_videos'] = []
        self.processing_flags[user_id] = True
        
        processing_msg = await update.message.reply_text("🎥 *Starting to create your REAL video reels...*", parse_mode='Markdown')
        
        total_combinations = len(all_media) * len(quotes)
        created = 0
        
        for media_index, media in enumerate(all_media):
            for quote_index, quote in enumerate(quotes):
                # Check if user stopped the process
                if not self.processing_flags.get(user_id, True):
                    await processing_msg.edit_text("🛑 *Process stopped by user!*", parse_mode='Markdown')
                    return MAIN_MENU
                    
                try:
                    current_index = created + 1
                    progress = f"🎥 Creating video reel {current_index}/{total_combinations}..."
                    await processing_msg.edit_text(progress)
                    
                    media_path = media['file_path']
                    # Create the video reel
                    result_path = await self.create_video_reel(media_path, quote, media['type'])
                    
                    if result_path and os.path.exists(result_path):
                        session['processed_videos'].append({
                            'media_path': result_path,
                            'quote': quote,
                            'media_index': media_index,
                            'quote_index': quote_index,
                            'index': created,
                            'type': media['type']
                        })
                        created += 1
                        
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error creating video reel {media_index}-{quote_index}: {e}")
                    continue
        
        # Clean up processing flag
        if user_id in self.processing_flags:
            del self.processing_flags[user_id]
        
        # Send all created video reels with save buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ *Created {created} video reels! Sending them now...*", parse_mode='Markdown')
            
            for i, media_data in enumerate(session['processed_videos']):
                try:
                    if not self.processing_flags.get(user_id, True):
                        break
                    if os.path.exists(media_data['media_path']):
                        with open(media_data['media_path'], 'rb') as f:
                            caption = f"**Video Reel {i+1}**\n{media_data['quote']}"
                            if len(all_media) == 1 and len(quotes) > 1:
                                caption += f"\n\n📝 Quote {media_data['quote_index'] + 1}"
                                
                            await update.message.reply_video(
                                video=f,
                                caption=caption,
                                reply_markup=self.get_save_keyboard(i, is_video=True),
                                parse_mode='Markdown'
                            )
                        await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error sending video reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *Successfully Created {created} Video Reels!*\n\n"
                f"📊 *Summary:*\n"
                f"📷 Photos: {len(photos)}\n"
                f"🎥 Videos: {len(videos)}\n"
                f"📝 Quotes: {len(quotes)}\n"
                f"🎬 Created: {created} video reels\n\n"
                f"💾 *Click the 'Save' button under each video to download it directly to your device!*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No video reels were created. Please try again with different media or quotes.",
                reply_markup=self.get_main_keyboard()
            )
        return MAIN_MENU

    async def create_video_reel(self, media_path, quote, media_type):
        """Create a single video reel with smooth transitions, text animation, and background music"""
        try:
            # Define video parameters
            width, height = 1080, 1350
            duration = 5  # Each clip will be 5 seconds
            
            # Load media
            if media_type == 'image':
                # Create a video clip from the image
                img_clip = mp.ImageClip(media_path).set_duration(duration)
                # Add zoom effect
                zoom_clip = img_clip.resize(lambda t: 1 + 0.01*t).set_position(('center', 'center'))
                final_clip = zoom_clip
            else:  # video
                # Load video clip
                video_clip = mp.VideoFileClip(media_path)
                # Trim to 5 seconds if longer
                if video_clip.duration > duration:
                    video_clip = video_clip.subclip(0, duration)
                # Resize to fit
                video_clip = video_clip.resize((width, height))
                final_clip = video_clip
            
            # Create text clip with animation
            is_arabic = self.is_arabic_text(quote)
            font_path = self.get_font_path(is_arabic)
            font_size = 60 if is_arabic else 50
            color = 'white'
            stroke_color = 'black'
            stroke_width = 2
            
            # Process Arabic text
            if is_arabic:
                display_text = self.process_arabic_text(quote)
            else:
                display_text = quote
            
            # Create text clip with fade-in/fade-out
            text_clip = TextClip(
                display_text, 
                fontsize=font_size, 
                font=font_path if font_path else 'Arial',
                color=color, 
                stroke_color=stroke_color, 
                stroke_width=stroke_width,
                method='caption',
                size=(width * 0.8, None)
            ).set_duration(duration)
            
            # Position text at center
            text_clip = text_clip.set_position(('center', 'center')).set_start(0)
            
            # Add subtle animation: slight scale up and down
            def scale_func(t):
                base_scale = 1.0
                oscillation = 0.02 * np.sin(2 * np.pi * t / 5)  # Oscillate every 5 seconds
                return base_scale + oscillation
            
            text_clip = text_clip.resize(scale_func)
            
            # Add fade-in and fade-out to text
            text_clip = text_clip.fadein(1).fadeout(1)
            
            # Composite video with text
            final_video = CompositeVideoClip([final_clip, text_clip]).set_duration(duration)
            
            # Add background music if available
            nasheed_path = 'background_nasheed.mp3'
            if os.path.exists(nasheed_path):
                try:
                    audio_clip = AudioFileClip(nasheed_path).subclip(0, duration)
                    # Loop audio if shorter than video
                    if audio_clip.duration < duration:
                        audio_clip = audio_clip.loop(duration=duration)
                    final_video = final_video.set_audio(audio_clip)
                except Exception as e:
                    logger.warning(f"Could not add background music: {e}")
            
            # Create output path
            output_path = tempfile.mktemp(suffix='_reel.mp4')
            
            # Write video file
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec='libx264', 
                audio_codec='aac', 
                preset='ultrafast', 
                threads=4, 
                logger=None
            )
            
            # Close clips to free memory
            final_video.close()
            if media_type == 'image':
                img_clip.close()
            else:
                video_clip.close()
            text_clip.close()
            
            return output_path
        except Exception as e:
            logger.error(f"Error creating video reel: {e}")
            return None

    async def handle_pic_to_reel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle picture to reel conversion"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
            
        # Initialize pic_to_reel_photos if not exists
        if 'pic_to_reel_photos' not in self.user_sessions[user_id]:
            self.user_sessions[user_id]['pic_to_reel_photos'] = []
        
        await update.message.reply_text(
            "🖼️ *Send your photos to convert to 17-second reels*:\n\n"
            "• Send multiple photos one by one\n"
            "• Click '📝 Add Quotes' when done to add text\n"
            "• Or click '🎬 Convert to Reel' to create without text\n\n"
            "✨ *Feature:* Each photo will be converted to a 17-second video reel with smooth transitions!",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        return UPLOADING_MEDIA

    async def handle_pic_to_reel_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process uploaded media for pic-to-reel"""
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
                
                self.user_sessions[user_id]['pic_to_reel_photos'].append({
                    'file_path': temp_path,
                    'file_id': photo_file.file_id,
                    'type': 'image'
                })
                
                count = len(self.user_sessions[user_id]['pic_to_reel_photos'])
                await update.message.reply_text(
                    f"✅ Photo {count} received for reel conversion! 📷",
                    reply_markup=self.get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Please send only photos for reel conversion.",
                    reply_markup=self.get_main_keyboard()
                )
                
        except Exception as e:
            logger.error(f"Error uploading media for pic-to-reel: {e}")
            await update.message.reply_text(
                "❌ Error uploading media. Please try again.",
                reply_markup=self.get_main_keyboard()
            )
        return UPLOADING_MEDIA

    async def create_pic_to_reel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create 17-second reels from uploaded pictures"""
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
            
        photos = self.user_sessions[user_id]['pic_to_reel_photos']
        quotes = self.user_sessions[user_id]['quotes']
        
        if not photos:
            await update.message.reply_text(
                "❌ Please upload photos first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
            
        # Set processing flag
        self.processing_flags[user_id] = True
        
        processing_msg = await update.message.reply_text("🖼️ *Converting pictures to 17-second reels...*", parse_mode='Markdown')
        
        created = 0
        for photo_index, photo in enumerate(photos):
            # Check if user stopped the process
            if not self.processing_flags.get(user_id, True):
                await processing_msg.edit_text("🛑 *Process stopped by user!*", parse_mode='Markdown')
                return MAIN_MENU
                
            try:
                current_index = created + 1
                progress = f"🎥 Creating reel {current_index}/{len(photos)}..."
                await processing_msg.edit_text(progress)
                
                photo_path = photo['file_path']
                
                # Create 17-second reel from the photo
                if quotes and photo_index < len(quotes):
                    # Use the quote at the same index or cycle through quotes
                    quote = quotes[photo_index % len(quotes)]
                    result_path = await self.create_17_sec_reel(photo_path, quote)
                else:
                    # Create reel without text
                    result_path = await self.create_17_sec_reel(photo_path, "")
                
                if result_path and os.path.exists(result_path):
                    # Add to processed videos list
                    self.user_sessions[user_id]['processed_videos'].append({
                        'media_path': result_path,
                        'quote': quotes[photo_index % len(quotes)] if quotes else "Islamic Inspiration",
                        'media_index': photo_index,
                        'quote_index': photo_index % len(quotes) if quotes else 0,
                        'index': len(self.user_sessions[user_id]['processed_videos']),
                        'type': 'image_to_video'
                    })
                    created += 1
                    
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error creating 17-sec reel for photo {photo_index}: {e}")
                continue
        
        # Clean up processing flag
        if user_id in self.processing_flags:
            del self.processing_flags[user_id]
        
        # Send created reels
        if created > 0:
            await processing_msg.edit_text(f"✅ *Created {created} 17-second reels! Sending them now...*", parse_mode='Markdown')
            
            for i in range(len(self.user_sessions[user_id]['processed_videos']) - created, len(self.user_sessions[user_id]['processed_videos'])):
                media_data = self.user_sessions[user_id]['processed_videos'][i]
                try:
                    if not self.processing_flags.get(user_id, True):
                        break
                    if os.path.exists(media_data['media_path']):
                        with open(media_data['media_path'], 'rb') as f:
                            caption = f"**17-Second Reel {i+1}**\n{media_data['quote']}"
                            await update.message.reply_video(
                                video=f,
                                caption=caption,
                                reply_markup=self.get_save_keyboard(i, is_video=True),
                                parse_mode='Markdown'
                            )
                        await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error sending 17-sec reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *Successfully Created {created} 17-Second Reels!*\n\n"
                f"📊 *Summary:*\n"
                f"🖼️ Photos: {len(photos)}\n"
                f"🎬 Created: {created} 17-second reels\n\n"
                f"💾 *Click the 'Save' button under each video to download it directly to your device!*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No reels were created. Please try again with different photos.",
                reply_markup=self.get_main_keyboard()
            )
        return MAIN_MENU

    async def create_17_sec_reel(self, image_path, quote=""):
        """Create a 17-second reel from a single image with zoom and pan effects"""
        try:
            # Define video parameters
            width, height = 1080, 1350
            duration = 17  # 17 seconds
            
            # Load image
            img_clip = mp.ImageClip(image_path).set_duration(duration)
            
            # Create zoom and pan effect
            # We'll create a sequence of zooms to simulate camera movement
            # Start with original size and gradually zoom in
            def zoom_func(t):
                # Zoom gradually from 1.0 to 1.2 over 17 seconds
                return 1.0 + (0.2 * t / duration)
            
            # Apply zoom effect
            zoomed_clip = img_clip.resize(zoom_func).set_position(('center', 'center'))
            
            # Add background music if available
            nasheed_path = 'background_nasheed.mp3'
            if os.path.exists(nasheed_path):
                try:
                    audio_clip = AudioFileClip(nasheed_path).subclip(0, duration)
                    # Loop audio if shorter than video
                    if audio_clip.duration < duration:
                        audio_clip = audio_clip.loop(duration=duration)
                    final_video = zoomed_clip.set_audio(audio_clip)
                except Exception as e:
                    logger.warning(f"Could not add background music: {e}")
                    final_video = zoomed_clip
            else:
                final_video = zoomed_clip
            
            # Add text if provided
            if quote:
                is_arabic = self.is_arabic_text(quote)
                font_path = self.get_font_path(is_arabic)
                font_size = 60 if is_arabic else 50
                color = 'white'
                stroke_color = 'black'
                stroke_width = 2
                
                # Process Arabic text
                if is_arabic:
                    display_text = self.process_arabic_text(quote)
                else:
                    display_text = quote
                
                # Create text clip
                text_clip = TextClip(
                    display_text, 
                    fontsize=font_size, 
                    font=font_path if font_path else 'Arial',
                    color=color, 
                    stroke_color=stroke_color, 
                    stroke_width=stroke_width,
                    method='caption',
                    size=(width * 0.8, None)
                ).set_duration(duration)
                
                # Position text at bottom center
                text_clip = text_clip.set_position(('center', 0.8)).set_start(0)
                
                # Add fade-in and fade-out to text
                text_clip = text_clip.fadein(2).fadeout(2)
                
                # Composite video with text
                final_video = CompositeVideoClip([final_video, text_clip]).set_duration(duration)
            
            # Create output path
            output_path = tempfile.mktemp(suffix='_17sec_reel.mp4')
            
            # Write video file
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec='libx264', 
                audio_codec='aac', 
                preset='ultrafast', 
                threads=4, 
                logger=None
            )
            
            # Close clips to free memory
            final_video.close()
            img_clip.close()
            if quote:
                text_clip.close()
            
            return output_path
        except Exception as e:
            logger.error(f"Error creating 17-sec reel: {e}")
            return None

    async def handle_save_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle save button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('save_'):
            try:
                parts = data.split('_')
                media_index = int(parts[1])
                is_video = parts[2] == 'video'
                
                if user_id in self.user_sessions:
                    session = self.user_sessions[user_id]
                    media_list = session['processed_videos'] if is_video else session['processed_images']
                    
                    if 0 <= media_index < len(media_list):
                        media_data = media_list[media_index]
                        
                        if os.path.exists(media_data['media_path']):
                            with open(media_data['media_path'], 'rb') as f:
                                if is_video:
                                    await query.message.reply_document(
                                        document=f,
                                        filename=f"islamic_video_reel_{media_index + 1}.mp4",
                                        caption=f"💾 Saved: Video Reel {media_index + 1}\n{media_data['quote']}"
                                    )
                                else:
                                    await query.message.reply_document(
                                        document=f,
                                        filename=f"islamic_image_reel_{media_index + 1}.jpg",
                                        caption=f"💾 Saved: Image Reel {media_index + 1}\n{media_data['quote']}"
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
            
        # Combine both image and video reels
        image_list = self.user_sessions[user_id]['processed_images']
        video_list = self.user_sessions[user_id]['processed_videos']
        all_reels = image_list + video_list
        
        if not all_reels:
            await update.message.reply_text(
                "❌ No reels found! Please create reels first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
            
        status_msg = await update.message.reply_text(f"💾 *Preparing {len(all_reels)} reels for download...*", parse_mode='Markdown')
        
        sent = 0
        for i, media_data in enumerate(all_reels):
            try:
                if os.path.exists(media_data['media_path']):
                    with open(media_data['media_path'], 'rb') as f:
                        if media_data['type'] == 'image' or 'processed_images' in media_data:
                            filename = f"islamic_reel_{i+1}.jpg"
                            caption = f"Reel {i+1}\n{media_data['quote']}"
                            await update.message.reply_document(document=f, filename=filename, caption=caption)
                        else:
                            filename = f"islamic_reel_{i+1}.mp4"
                            caption = f"Reel {i+1}\n{media_data['quote']}"
                            await update.message.reply_document(document=f, filename=filename, caption=caption)
                        sent += 1
                    await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error saving reel {i}: {e}")
                continue
        
        await status_msg.edit_text(f"✅ *Successfully saved {sent} reels to your device!*", parse_mode='Markdown')
        return MAIN_MENU

    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset everything"""
        user_id = update.effective_user.id
        
        # Stop any ongoing process
        if user_id in self.processing_flags:
            self.processing_flags[user_id] = False
            
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            
            # Clean up all temporary files
            for media in session['photos'] + session['videos']:
                try:
                    if os.path.exists(media['file_path']):
                        os.unlink(media['file_path'])
                except:
                    pass
                    
            for media in session['processed_images']:
                try:
                    if os.path.exists(media['media_path']):
                        os.unlink(media['media_path'])
                except:
                    pass
                    
            for media in session['processed_videos']:
                try:
                    if os.path.exists(media['media_path']):
                        os.unlink(media['media_path'])
                except:
                    pass
            
            # Reset session
            self.user_sessions[user_id] = {
                'photos': [],
                'videos': [],
                'quotes': [],
                'processed_images': [],
                'processed_videos': [],
                'pic_to_reel_photos': []
            }
        
        await update.message.reply_text(
            "🔄 *Reset Complete!*\n\nAll data has been cleared. You can start fresh!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU

def run_bot():
    """Run the bot with polling"""
    try:
        bot = IslamicReelsBot()

        application = Application.builder().token(BOT_TOKEN).build()
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', bot.start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.Regex('^📤 Upload Media$'), bot.handle_upload_media),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                    MessageHandler(filters.Regex('^🎬 Make Image Reels$'), bot.handle_make_image_reels),
                    MessageHandler(filters.Regex('^🎥 Make Video Reels$'), bot.handle_make_video_reels),
                    MessageHandler(filters.Regex('^🖼️ Convert Pic to Reel$'), bot.handle_pic_to_reel),
                    MessageHandler(filters.Regex('^💾 Save All$'), bot.handle_save_all),
                    MessageHandler(filters.Regex('^🛑 Stop Process$'), bot.handle_stop_process),
                    MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
                ],
                UPLOADING_MEDIA: [
                    MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, bot.handle_media),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                    MessageHandler(filters.Regex('^🎬 Convert Pic to Reel$'), bot.handle_pic_to_reel_media),
                    MessageHandler(filters.Regex('^🎥 Convert to Reel$'), bot.create_pic_to_reel),
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
        print("✅ Bot is running with polling!")
        print("🚀 Ready to receive messages...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        raise

def main():
    """Main function with error handling"""
    max_retries = 3
    retry_delay = 10

    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (attempt {attempt + 1}/{max_retries})...")
            run_bot()
        except Exception as e:
            print(f"❌ Bot crashed: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("💥 Max retries reached. Bot stopped.")

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    print("=" * 50)
    print("🕌 Islamic Reels Bot - Lifetime Version")
    print("🌍 Supports English & Arabic")
    print("🎥 Photos & Videos")
    print("🎞️ REAL Video Reels Generation")
    print("🔊 Background Nasheeds")
    print("💾 Save Direct to Device")
    print("🛑 Stop Process Feature")
    print("🖼️ Pic to 17-sec Reel Conversion")
    print("=" * 50)

    main()
