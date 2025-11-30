from keep_alive import keep_alive
import requests

# Start keep-alive server BEFORE starting the bot
keep_alive()

# Add this function for self-pinging
def self_ping():
    """Ping ourselves to stay awake"""
    try:
        requests.get("https://your-bot-name.onrender.com/", timeout=10)
        print(f"✅ Self-ping at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"⚠️ Self-ping failed: {e}")

# Start self-pinging in background
import threading
def start_self_ping():
    while True:
        self_ping()
        time.sleep(300)  # 5 minutes

ping_thread = threading.Thread(target=start_self_ping, daemon=True)
ping_thread.start()


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
import time
import moviepy.editor as mp
import numpy as np
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.fx.all import resize, fadein, fadeout
import threading
import concurrent.futures

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES, SELECTING_STYLE = range(4)

class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}  # To track and stop processing
        self.setup_fonts()
        self.setup_background_music()
    
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
    
    def setup_background_music(self):
        """Download background music for videos"""
        try:
            os.makedirs('music', exist_ok=True)
            music_url = 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
            music_path = 'music/background.mp3'
            
            if not os.path.exists(music_path):
                response = requests.get(music_url, timeout=30)
                if response.status_code == 200:
                    with open(music_path, 'wb') as f:
                        f.write(response.content)
                    logger.info("Downloaded background music")
        except Exception as e:
            logger.error(f"Error setting up background music: {e}")
    
    def get_main_keyboard(self):
        """Create main menu buttons"""
        keyboard = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Make Reels"), KeyboardButton("💾 Save All")],
            [KeyboardButton("🛑 Stop Process"), KeyboardButton("🔄 Reset")],
            [KeyboardButton("⚡ Bulk Mode"), KeyboardButton("🎨 Style Settings")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_save_keyboard(self, media_index):
        """Create save button for each reel"""
        keyboard = [
            [InlineKeyboardButton("💾 Save This Reel", callback_data=f"save_{media_index}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_style_keyboard(self):
        """Create style selection keyboard"""
        keyboard = [
            [KeyboardButton("🌙 Night Theme"), KeyboardButton("🌺 Garden Theme")],
            [KeyboardButton("🌅 Sunset Theme"), KeyboardButton("🌻 Field Theme")],
            [KeyboardButton("Back to Main Menu")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'photos': [],
            'videos': [],
            'quotes': [],
            'processed_media': [],
            'style': 'default',
            'duration': 5,
            'add_music': True,
            'text_animation': 'fade',
            'bulk_mode': False
        }
        
        welcome_text = """
🕌 *Islamic Reels Maker* 🌟

*3 Simple Steps:*

1️⃣ *Upload Media* - Send your images or short videos
2️⃣ *Add Quotes* - Write your custom quotes  
3️⃣ *Make Reels* - Create beautiful reels with quotes
4️⃣ *Save* - Save directly to your device

✨ *New Advanced Features:*
• ✅ Create REAL VIDEO REELS (not just images)
• ⚡ Bulk Processing - Create 10+ reels in seconds
• 🎨 Multiple Styles & Animations
• 🎵 Add Background Music
• 🛑 Stop processing anytime
• 💾 Save individual reels

*يدعم اللغة العربية والحركات*
*Supports Arabic with Harakat*

*Current Status:*
📷 Photos: 0
🎥 Videos: 0  
📝 Quotes: 0
🎬 Ready: 0

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
            f"Click '🎬 Make Reels' to create your content!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    async def handle_style_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle style settings"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        await update.message.reply_text(
            "🎨 *Style Settings*\n\n"
            "Choose a style for your reels:\n\n"
            "🌙 *Night Theme* - Dark backgrounds with moon/stars\n"
            "🌺 *Garden Theme* - Flowers and nature backgrounds\n"
            "🌅 *Sunset Theme* - Warm sunset colors\n"
            "🌻 *Field Theme* - Sunflower fields and rural scenes\n\n"
            "You can also customize:\n"
            "• Duration (default: 5 seconds)\n"
            "• Add background music (default: ON)\n"
            "• Text animation (default: Fade)\n\n"
            "Select a style or click 'Back to Main Menu'",
            reply_markup=self.get_style_keyboard(),
            parse_mode='Markdown'
        )
        return SELECTING_STYLE
    
    async def handle_style_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle style selection"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        
        if text == "🌙 Night Theme":
            session['style'] = 'night'
            await update.message.reply_text(
                "🌙 *Night Theme Selected!*\n\n"
                "Your reels will have dark backgrounds with moon/stars.",
                reply_markup=self.get_main_keyboard()
            )
        elif text == "🌺 Garden Theme":
            session['style'] = 'garden'
            await update.message.reply_text(
                "🌺 *Garden Theme Selected!*\n\n"
                "Your reels will have flower and nature backgrounds.",
                reply_markup=self.get_main_keyboard()
            )
        elif text == "🌅 Sunset Theme":
            session['style'] = 'sunset'
            await update.message.reply_text(
                "🌅 *Sunset Theme Selected!*\n\n"
                "Your reels will have warm sunset colors.",
                reply_markup=self.get_main_keyboard()
            )
        elif text == "🌻 Field Theme":
            session['style'] = 'field'
            await update.message.reply_text(
                "🌻 *Field Theme Selected!*\n\n"
                "Your reels will have sunflower fields and rural scenes.",
                reply_markup=self.get_main_keyboard()
            )
        elif text == "Back to Main Menu":
            await update.message.reply_text(
                "🏠 *Back to Main Menu*",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        return SELECTING_STYLE
    
    async def handle_bulk_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle bulk mode toggle"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        session['bulk_mode'] = not session['bulk_mode']
        
        status = "ON" if session['bulk_mode'] else "OFF"
        await update.message.reply_text(
            f"⚡ *Bulk Mode {status}!*\n\n"
            f"{'✅ Bulk processing enabled - create multiple reels simultaneously' if session['bulk_mode'] else '❌ Bulk processing disabled - create reels one by one'}\n\n"
            f"Click '🎬 Make Reels' to start creating reels!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    def is_arabic_text(self, text):
        """Check if text contains Arabic characters"""
        arabic_range = range(0x0600, 0x06FF)
        return any(ord(char) in arabic_range for char in text)
    
    def get_font(self, size, is_arabic=False):
        """Get appropriate font based on language"""
        font_paths = [
            'fonts/amiri.ttf' if is_arabic else 'fonts/arial.ttf',
            'fonts/noto.ttf' if is_arabic else 'fonts/arial.ttf',
            'arial.ttf'
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()
    
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
    
    def create_video_reel(self, media_path, quote, duration=5, style='default', add_music=True, text_animation='fade'):
        """Create a real video reel with quote"""
        try:
            # Create a temporary directory for processing
            temp_dir = tempfile.mkdtemp()
            
            # Create video clip from image or use existing video
            if media_path.endswith('.jpg') or media_path.endswith('.png'):
                # Create video from image
                img = Image.open(media_path)
                width, height = 1080, 1350
                
                # Resize image to fit
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                img_bg = Image.new('RGB', (width, height), (0, 0, 0))
                x = (width - img.width) // 2
                y = (height - img.height) // 2
                img_bg.paste(img, (x, y))
                
                # Save as temporary image
                temp_img_path = os.path.join(temp_dir, 'temp_image.jpg')
                img_bg.save(temp_img_path, quality=95)
                
                # Create video clip from image
                clip = mp.ImageClip(temp_img_path).set_duration(duration)
            else:
                # Use existing video
                clip = mp.VideoFileClip(media_path).set_duration(duration)
                
                # Resize to standard dimensions
                if clip.w != 1080 or clip.h != 1350:
                    clip = resize(clip, (1080, 1350))
            
            # Add text overlay
            is_arabic = self.is_arabic_text(quote)
            font_size = 60 if is_arabic else 50
            font_path = 'fonts/amiri.ttf' if is_arabic else 'fonts/arial.ttf'
            
            if not os.path.exists(font_path):
                font_path = 'arial.ttf'
            
            # Create text clip
            text_clip = mp.TextClip(
                quote, 
                fontsize=font_size, 
                color='white', 
                font=font_path,
                method='caption',
                size=(900, None),
                align='center'
            ).set_duration(duration)
            
            # Position text
            text_clip = text_clip.set_position(('center', 'center'))
            
            # Apply text animation
            if text_animation == 'fade':
                text_clip = text_clip.fadein(1).fadeout(1)
            elif text_animation == 'slide':
                text_clip = text_clip.set_position(lambda t: ('center', 1350 - 100*t))
            
            # Create semi-transparent background for text
            txt_bg = mp.ColorClip(size=(900, 150), color=(0, 0, 0, 180)).set_duration(duration)
            txt_bg = txt_bg.set_position(('center', 'center')).set_opacity(0.7)
            
            # Composite clips
            final_clip = mp.CompositeVideoClip([clip, txt_bg, text_clip])
            
            # Add background music if requested
            if add_music:
                try:
                    music_path = 'music/background.mp3'
                    if os.path.exists(music_path):
                        audio = mp.AudioFileClip(music_path).subclip(0, duration)
                        audio = audio.volumex(0.3)  # Lower volume
                        final_clip = final_clip.set_audio(audio)
                except Exception as e:
                    logger.warning(f"Could not add background music: {e}")
            
            # Add style effects based on selected style
            if style == 'night':
                # Add night effect
                final_clip = final_clip.fx(mp.vfx.colorx, 0.8).fx(mp.vfx.lum_contrast, lum=0.9, contrast=1.1)
            elif style == 'garden':
                # Add garden effect
                final_clip = final_clip.fx(mp.vfx.colorx, 1.1).fx(mp.vfx.lum_contrast, lum=1.0, contrast=1.0)
            elif style == 'sunset':
                # Add sunset effect
                final_clip = final_clip.fx(mp.vfx.colorx, 1.2).fx(mp.vfx.lum_contrast, lum=1.1, contrast=1.0)
            elif style == 'field':
                # Add field effect
                final_clip = final_clip.fx(mp.vfx.colorx, 1.05).fx(mp.vfx.lum_contrast, lum=1.05, contrast=1.0)
            
            # Export video
            output_path = os.path.join(temp_dir, 'reel_output.mp4')
            final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating video reel: {e}")
            return None
    
    def create_image_with_quote(self, image_path, quote):
        """Create beautiful image with quote (fallback)"""
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
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create reels with quotes"""
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
        session['processed_media'] = []
        self.processing_flags[user_id] = True
        
        processing_msg = await update.message.reply_text("🔄 *Starting to create your reels...*", parse_mode='Markdown')
        
        total_combinations = len(all_media) * len(quotes)
        created = 0
        
        # Get user preferences
        style = session.get('style', 'default')
        duration = session.get('duration', 5)
        add_music = session.get('add_music', True)
        text_animation = session.get('text_animation', 'fade')
        bulk_mode = session.get('bulk_mode', False)
        
        # Create reels
        if bulk_mode:
            # Bulk processing using threads
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                
                for media_index, media in enumerate(all_media):
                    for quote_index, quote in enumerate(quotes):
                        # Check if user stopped the process
                        if not self.processing_flags.get(user_id, True):
                            await processing_msg.edit_text("🛑 *Process stopped by user!*", parse_mode='Markdown')
                            break
                        
                        future = executor.submit(
                            self.create_video_reel, 
                            media['file_path'], 
                            quote, 
                            duration, 
                            style, 
                            add_music, 
                            text_animation
                        )
                        futures.append((future, media_index, quote_index, media['type']))
                
                # Collect results
                for i, (future, media_index, quote_index, media_type) in enumerate(futures):
                    if not self.processing_flags.get(user_id, True):
                        break
                    
                    try:
                        result_path = future.result(timeout=60)  # 60 second timeout
                        
                        if result_path and os.path.exists(result_path):
                            session['processed_media'].append({
                                'media_path': result_path,
                                'quote': quote,
                                'media_index': media_index,
                                'quote_index': quote_index,
                                'index': created,
                                'type': media_type
                            })
                            created += 1
                            
                            # Update progress
                            progress = f"🔄 Creating reel {created}/{total_combinations}..."
                            await processing_msg.edit_text(progress)
                        
                    except Exception as e:
                        logger.error(f"Error with combination {media_index}-{quote_index}: {e}")
                        continue
        else:
            # Sequential processing
            for media_index, media in enumerate(all_media):
                for quote_index, quote in enumerate(quotes):
                    # Check if user stopped the process
                    if not self.processing_flags.get(user_id, True):
                        await processing_msg.edit_text("🛑 *Process stopped by user!*", parse_mode='Markdown')
                        break
                    
                    try:
                        current_index = created + 1
                        progress = f"🔄 Creating reel {current_index}/{total_combinations}..."
                        await processing_msg.edit_text(progress)
                        
                        media_path = media['file_path']
                        
                        # Try to create video reel
                        result_path = self.create_video_reel(
                            media_path, 
                            quote, 
                            duration, 
                            style, 
                            add_music, 
                            text_animation
                        )
                        
                        if result_path and os.path.exists(result_path):
                            session['processed_media'].append({
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
        
        # Send all created reels with save buttons
        if created > 0:
            await processing_msg.edit_text(f"✅ *Created {created} reels! Sending them now...*", parse_mode='Markdown')
            
            for i, media_data in enumerate(session['processed_media']):
                try:
                    if not self.processing_flags.get(user_id, True):
                        break
                        
                    if os.path.exists(media_data['media_path']):
                        with open(media_data['media_path'], 'rb') as f:
                            caption = f"**Reel {i+1}**\n{media_data['quote']}"
                            
                            if len(all_media) == 1 and len(quotes) > 1:
                                caption += f"\n\n📝 Quote {media_data['quote_index'] + 1}"
                            
                            # Send as video if it's a .mp4 file, otherwise as photo
                            if media_data['media_path'].endswith('.mp4'):
                                await update.message.reply_video(
                                    video=f,
                                    caption=caption,
                                    reply_markup=self.get_save_keyboard(i),
                                    parse_mode='Markdown'
                                )
                            else:
                                await update.message.reply_photo(
                                    photo=f,
                                    caption=caption,
                                    reply_markup=self.get_save_keyboard(i),
                                    parse_mode='Markdown'
                                )
                        await asyncio.sleep(1)  # Rate limiting
                        
                except Exception as e:
                    logger.error(f"Error sending reel {i}: {e}")
                    continue
            
            await update.message.reply_text(
                f"🎉 *Successfully Created {created} Reels!*\n\n"
                f"📊 *Summary:*\n"
                f"📷 Photos: {len(photos)}\n"
                f"🎥 Videos: {len(videos)}\n"
                f"📝 Quotes: {len(quotes)}\n"
                f"🎬 Created: {created} reels\n\n"
                f"💾 *Click the 'Save' button under each reel to download it directly to your device!*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No reels were created. Please try again with different media or quotes.",
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
                                # Send as document to preserve quality
                                await query.message.reply_document(
                                    document=f,
                                    filename=f"islamic_reel_{media_index + 1}.mp4" if media_data['media_path'].endswith('.mp4') else f"islamic_reel_{media_index + 1}.jpg",
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
                "❌ No reels found! Please create reels first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        status_msg = await update.message.reply_text(f"💾 *Preparing {len(media_list)} reels for download...*", parse_mode='Markdown')
        
        sent = 0
        for i, media_data in enumerate(media_list):
            try:
                if os.path.exists(media_data['media_path']):
                    with open(media_data['media_path'], 'rb') as f:
                        # Send as document to preserve quality
                        await update.message.reply_document(
                            document=f,
                            filename=f"islamic_reel_{i+1}.mp4" if media_data['media_path'].endswith('.mp4') else f"islamic_reel_{i+1}.jpg",
                            caption=f"Reel {i+1}\n{media_data['quote']}"
                        )
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
            
            for media in session['processed_media']:
                try:
                    if os.path.exists(media['media_path']):
                        os.unlink(media['media_path'])
                except:
                    pass
            
            # Reset session
            self.user_sessions[user_id] = {'photos': [], 'videos': [], 'quotes': [], 'processed_media': [], 'style': 'default', 'duration': 5, 'add_music': True, 'text_animation': 'fade', 'bulk_mode': False}
        
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
                    MessageHandler(filters.Regex('^🎬 Make Reels$'), bot.handle_make_reels),
                    MessageHandler(filters.Regex('^💾 Save All$'), bot.handle_save_all),
                    MessageHandler(filters.Regex('^🛑 Stop Process$'), bot.handle_stop_process),
                    MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
                    MessageHandler(filters.Regex('^⚡ Bulk Mode$'), bot.handle_bulk_mode),
                    MessageHandler(filters.Regex('^🎨 Style Settings$'), bot.handle_style_settings),
                ],
                UPLOADING_MEDIA: [
                    MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, bot.handle_media),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                ],
                ADDING_QUOTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_quotes)
                ],
                SELECTING_STYLE: [
                    MessageHandler(filters.Regex('^(🌙 Night Theme|🌺 Garden Theme|🌅 Sunset Theme|🌻 Field Theme|Back to Main Menu)$'), bot.handle_style_selection),
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
    print("=" * 50)
    print("🕌 Islamic Reels Bot - Lifetime Version")
    print("🌍 Supports English & Arabic")
    print("🎥 Photos & Videos")
    print("💾 Save Direct to Device")
    print("🛑 Stop Process Feature")
    print("⚡ Bulk Processing")
    print("🎨 Advanced Styling")
    print("=" * 50)
    
    main()
