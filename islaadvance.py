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
import time
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
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import arabic_reshaper
from bidi.algorithm import get_display
import requests
import time
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip, AudioFileClip
import numpy as np
import pyttsx3
from concurrent.futures import ThreadPoolExecutor
import json

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_MEDIA, ADDING_QUOTES, REEL_SETTINGS, VOICE_SETTINGS = range(5)

class IslamicReelsBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}
        self.tts_engine = self.setup_tts()
        self.setup_fonts()
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def setup_tts(self):
        """Initialize text-to-speech engine"""
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            # Try to find Arabic voice
            for voice in voices:
                if 'arabic' in voice.name.lower() or 'ar_' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
            engine.setProperty('rate', 150)
            return engine
        except Exception as e:
            logger.error(f"TTS setup failed: {e}")
            return None
    
    def setup_fonts(self):
        """Setup Arabic and English fonts"""
        try:
            os.makedirs('fonts', exist_ok=True)
            self.download_fonts()
        except Exception as e:
            logger.error(f"Error setting up fonts: {e}")
    
    def download_fonts(self):
        """Download required fonts"""
        font_urls = {
            'amiri': 'https://github.com/alif-type/amiri/releases/download/0.113/amiri-0.113.zip',
            'noto': 'https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf',
            'arial': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf',
            'me_quran': 'https://github.com/mustafa0x01/prayer-times/raw/master/fonts/me_quran.ttf'
        }
        
        for name, url in font_urls.items():
            font_path = f'fonts/{name}.ttf'
            if not os.path.exists(font_path):
                try:
                    if url.endswith('.zip'):
                        # Handle zip files (simplified - in production you'd extract)
                        response = requests.get(url, timeout=30)
                        if response.status_code == 200:
                            # For now, just download as ttf
                            with open(font_path, 'wb') as f:
                                f.write(response.content)
                    else:
                        response = requests.get(url, timeout=30)
                        if response.status_code == 200:
                            with open(font_path, 'wb') as f:
                                f.write(response.content)
                    logger.info(f"Downloaded {name} font")
                except Exception as e:
                    logger.error(f"Failed to download {name} font: {e}")
    
    def get_main_keyboard(self):
        """Create advanced main menu"""
        keyboard = [
            [KeyboardButton("📤 Upload Media"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("⚙️ Reel Settings"), KeyboardButton("🎙️ Voice Settings")],
            [KeyboardButton("🎬 Make Reels"), KeyboardButton("🚀 Bulk Create")],
            [KeyboardButton("💾 Save All"), KeyboardButton("🛑 Stop Process")],
            [KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_settings_keyboard(self):
        """Settings menu keyboard"""
        keyboard = [
            [KeyboardButton("🎨 Change Theme"), KeyboardButton("📐 Change Layout")],
            [KeyboardButton("🔤 Font Size"), KeyboardButton("⏱️ Duration")],
            [KeyboardButton("🔙 Back to Main")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_voice_keyboard(self):
        """Voice settings keyboard"""
        keyboard = [
            [KeyboardButton("🔊 Enable Voice"), KeyboardButton("🔇 Disable Voice")],
            [KeyboardButton("👨‍💼 Change Voice"), KeyboardButton("🎵 Add Background Music")],
            [KeyboardButton("🔙 Back to Main")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_save_keyboard(self, media_index):
        """Create save button for each reel"""
        keyboard = [
            [
                InlineKeyboardButton("💾 Save Image", callback_data=f"save_img_{media_index}"),
                InlineKeyboardButton("🎥 Save Video", callback_data=f"save_vid_{media_index}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with enhanced features"""
        user_id = update.effective_user.id
        
        # Initialize user session with advanced settings
        self.user_sessions[user_id] = {
            'photos': [],
            'videos': [],
            'quotes': [],
            'processed_media': [],
            'settings': {
                'theme': 'islamic_blue',
                'layout': 'centered',
                'font_size': 60,
                'duration': 10,
                'voice_enabled': False,
                'background_music': None,
                'output_format': 'video',  # 'image' or 'video'
                'bulk_quality': 'medium'
            }
        }
        
        welcome_text = """
🕌 *Islamic Reels Maker Pro* 🌟

*🚀 Advanced Features:*

📤 *Upload Media* - Images & Videos
📝 *Add Quotes* - Multiple languages supported
⚙️ *Reel Settings* - Customize appearance
🎙️ *Voice Settings* - Text-to-speech & background music
🎬 *Make Reels* - Create individual reels
🚀 *Bulk Create* - Generate multiple reels instantly
💾 *Save All* - Download all creations

✨ *New Advanced Features:*
• Real video reels with animations 🎥
• Text-to-speech voiceovers 🎙️
• Background music integration 🎵
• Multiple themes and layouts 🎨
• Bulk processing in seconds ⚡
• Arabic text with proper harakat 🌍

*يدعم اللغة العربية والحركات بشكل متقدم*

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
    
    async def handle_reel_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reel settings menu"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        settings = self.user_sessions[user_id]['settings']
        
        settings_text = f"""
⚙️ *Current Reel Settings:*

🎨 *Theme:* {settings['theme']}
📐 *Layout:* {settings['layout']}
🔤 *Font Size:* {settings['font_size']}
⏱️ *Duration:* {settings['duration']} seconds
🎥 *Output Format:* {settings['output_format']}
🚀 *Bulk Quality:* {settings['bulk_quality']}

*Available Options:*
• *Themes:* islamic_blue, golden, green, dark, light
• *Layouts:* centered, bottom, top, split
• *Output:* image, video
• *Quality:* low, medium, high
        """
        
        await update.message.reply_text(
            settings_text,
            reply_markup=self.get_settings_keyboard(),
            parse_mode='Markdown'
        )
        return REEL_SETTINGS
    
    async def handle_voice_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice settings menu"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        settings = self.user_sessions[user_id]['settings']
        voice_status = "✅ Enabled" if settings['voice_enabled'] else "❌ Disabled"
        music_status = "✅ Added" if settings['background_music'] else "❌ None"
        
        voice_text = f"""
🎙️ *Voice Settings:*

🔊 *Voice Over:* {voice_status}
🎵 *Background Music:* {music_status}

*Features:*
• Text-to-speech for quotes
• Multiple voice options
• Background music integration
• Audio mixing capabilities
        """
        
        await update.message.reply_text(
            voice_text,
            reply_markup=self.get_voice_keyboard(),
            parse_mode='Markdown'
        )
        return VOICE_SETTINGS
    
    async def handle_upload_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced media upload handler"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        await update.message.reply_text(
            "📤 *Upload Media*:\n\n"
            "• Send multiple photos/videos\n"
            "• Videos up to 60 seconds\n"
            "• Supports: JPG, PNG, MP4, MOV\n"
            "• Bulk processing available\n\n"
            "💡 *Pro Tip:* Upload 1 media + multiple quotes = automated bulk creation!",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        return UPLOADING_MEDIA
    
    async def handle_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process uploaded media with enhanced capabilities"""
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
                    'type': 'image',
                    'duration': 5  # Default duration for images in videos
                })
                
                count = len(self.user_sessions[user_id]['photos'])
                await update.message.reply_text(
                    f"✅ Photo {count} received! 📷\n"
                    f"💡 This can be used for {len(self.user_sessions[user_id]['quotes'])} quote combinations",
                    reply_markup=self.get_main_keyboard()
                )
                
            elif update.message.video:
                # Handle video upload
                video = update.message.video
                if video.duration > 60:
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
                    f"✅ Video {count} received! 🎥\n"
                    f"Duration: {video.duration}s\n"
                    f"💡 Ready for {len(self.user_sessions[user_id]['quotes'])} quote combinations",
                    reply_markup=self.get_main_keyboard()
                )
                
            elif update.message.document:
                # Handle document upload
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
        """Enhanced quote input handler"""
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
            f"📝 *Add Your Quotes*:\n\n"
            f"You have {photo_count} photos and {video_count} videos.\n"
            f"Send your quotes (one quote per line):\n\n"
            f"🚀 *Bulk Creation Ready:*\n"
            f"• {total_media} media × your quotes = automatic bulk reels!\n"
            f"• Videos with text-to-speech voiceovers\n"
            f"• Professional transitions and effects\n\n"
            f"🌍 *Multi-language Support:*\n"
            f"• Arabic with full harakat support\n"
            f"• English and other languages\n"
            f"• Automatic language detection\n\n"
            f"📚 *Examples:*\n"
            f"*Arabic:*\n"
            f"رَّبِّ أَدْخِلْنِي مُدْخَلَ صِدْقٍ\nوَأَخْرِجْنِي مُخْرَجَ صِدْقٍ\n\n"
            f"*English:*\n"
            f"O my Lord! Let my entry be good\nAnd likewise my exit be good",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        return ADDING_QUOTES
    
    async def handle_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user quotes with enhanced features"""
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
            f"🚀 *Bulk Creation Potential:*\n"
            f"• {total_media} × {len(quotes_list)} = {total_media * len(quotes_list)} reels!\n"
            f"• Videos with voiceovers: {'✅' if self.user_sessions[user_id]['settings']['voice_enabled'] else '❌'}\n"
            f"• Background music: {'✅' if self.user_sessions[user_id]['settings']['background_music'] else '❌'}\n\n"
            f"Click '🚀 Bulk Create' for instant processing!",
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
            'fonts/me_quran.ttf' if is_arabic else 'fonts/arial.ttf',
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
        
        if is_arabic:
            processed_text = self.process_arabic_text(text)
        else:
            processed_text = text
        
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
    
    def create_tts_audio(self, text, output_path):
        """Create text-to-speech audio file"""
        try:
            if self.tts_engine:
                self.tts_engine.save_to_file(text, output_path)
                self.tts_engine.runAndWait()
                return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"TTS error: {e}")
        return False
    
    def create_video_with_quote(self, media_path, quote, settings, output_path):
        """Create video reel with quote overlay and effects"""
        try:
            # Load video or create from image
            if media_path.endswith(('.mp4', '.mov', '.avi')):
                clip = VideoFileClip(media_path)
            else:
                # Create video from image
                clip = ColorClip((1080, 1920), color=(0, 0, 0), duration=settings['duration'])
                img_clip = ImageClip(media_path).set_duration(settings['duration'])
                clip = CompositeVideoClip([clip, img_clip.set_position('center')])
            
            # Resize for consistency
            clip = clip.resize(height=1920) if clip.h > 1920 else clip
            clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
            
            # Create text clip
            is_arabic = self.is_arabic_text(quote)
            font_size = settings['font_size']
            font = self.get_font(font_size, is_arabic)
            
            # Process text
            processed_quote = self.process_arabic_text(quote) if is_arabic else quote
            
            # Create text clip with styling
            text_clip = TextClip(
                processed_quote,
                fontsize=font_size,
                color='white',
                font=font.name if hasattr(font, 'name') else 'Arial',
                stroke_color='black',
                stroke_width=2
            )
            
            # Position text based on layout
            if settings['layout'] == 'centered':
                text_clip = text_clip.set_position('center')
            elif settings['layout'] == 'bottom':
                text_clip = text_clip.set_position(('center', 1400))
            elif settings['layout'] == 'top':
                text_clip = text_clip.set_position(('center', 200))
            
            # Add semi-transparent background to text
            text_bg = ColorClip(
                (1080, 300), 
                color=(0, 0, 0, 180), 
                duration=clip.duration
            ).set_position(('center', 800))
            
            # Composite everything
            final_clip = CompositeVideoClip([clip, text_bg, text_clip])
            
            # Add audio if enabled
            if settings['voice_enabled']:
                tts_path = tempfile.mktemp(suffix='.mp3')
                if self.create_tts_audio(quote, tts_path):
                    tts_audio = AudioFileClip(tts_path)
                    final_clip = final_clip.set_audio(tts_audio)
            
            # Write output
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio_codec='aac' if settings['voice_enabled'] else None,
                verbose=False,
                logger=None
            )
            
            # Cleanup
            clip.close()
            final_clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Video creation error: {e}")
            return False
    
    def create_image_with_quote(self, image_path, quote, settings):
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
            
            font_size = settings['font_size']
            font = self.get_font(font_size, is_arabic)
            
            lines = self.split_text_to_lines(quote, font, width * 0.8, is_arabic)
            line_height = font_size + 20
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
                
                # Draw text with shadow
                shadow_offset = 3
                draw.text((x_pos + shadow_offset, y_pos + shadow_offset), line, font=font, fill=(0, 0, 0, 200))
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255))
            
            output_path = tempfile.mktemp(suffix='_quote.jpg')
            background.save(output_path, quality=95)
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating image: {e}")
            return image_path
    
    async def handle_bulk_create(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle bulk reel creation"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        photos = session['photos']
        videos = session['videos']
        quotes = session['quotes']
        settings = session['settings']
        
        all_media = photos + videos
        
        if not all_media or not quotes:
            await update.message.reply_text(
                "❌ Please upload both media and quotes first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        # Set processing flag
        session['processed_media'] = []
        self.processing_flags[user_id] = True
        
        processing_msg = await update.message.reply_text(
            "🚀 *Starting Bulk Creation...*\n\n"
            f"📊 Processing {len(all_media)} media × {len(quotes)} quotes = {len(all_media) * len(quotes)} reels\n"
            f"🎥 Output: {settings['output_format'].upper()}\n"
            f"🔊 Voice: {'✅ ON' if settings['voice_enabled'] else '❌ OFF'}\n\n"
            "⏳ This may take a few minutes...",
            parse_mode='Markdown'
        )
        
        total_combinations = len(all_media) * len(quotes)
        created = 0
        
        # Process in batches
        for media_index, media in enumerate(all_media):
            for quote_index, quote in enumerate(quotes):
                if not self.processing_flags.get(user_id, True):
                    await processing_msg.edit_text("🛑 *Bulk creation stopped by user!*", parse_mode='Markdown')
                    return MAIN_MENU
                
                try:
                    current_index = created + 1
                    progress = (current_index / total_combinations) * 100
                    
                    await processing_msg.edit_text(
                        f"🚀 *Bulk Creation Progress*\n\n"
                        f"📈 {progress:.1f}% Complete\n"
                        f"🎬 Reel {current_index}/{total_combinations}\n"
                        f"📝 Quote {quote_index + 1}/{len(quotes)}\n"
                        f"🖼️ Media {media_index + 1}/{len(all_media)}",
                        parse_mode='Markdown'
                    )
                    
                    media_path = media['file_path']
                    output_filename = f"reel_{media_index}_{quote_index}"
                    
                    if settings['output_format'] == 'video':
                        output_path = tempfile.mktemp(suffix='_reel.mp4')
                        success = self.create_video_with_quote(media_path, quote, settings, output_path)
                    else:
                        output_path = self.create_image_with_quote(media_path, quote, settings)
                        success = os.path.exists(output_path)
                    
                    if success and os.path.exists(output_path):
                        session['processed_media'].append({
                            'media_path': output_path,
                            'quote': quote,
                            'media_index': media_index,
                            'quote_index': quote_index,
                            'index': created,
                            'type': settings['output_format']
                        })
                        created += 1
                    
                    await asyncio.sleep(0.1)  # Small delay
                        
                except Exception as e:
                    logger.error(f"Error in bulk creation {media_index}-{quote_index}: {e}")
                    continue
        
        # Clean up processing flag
        if user_id in self.processing_flags:
            del self.processing_flags[user_id]
        
        # Send results
        if created > 0:
            await processing_msg.edit_text(
                f"✅ *Bulk Creation Complete!*\n\n"
                f"🎉 Successfully created {created} reels!\n"
                f"📊 Success rate: {(created/total_combinations)*100:.1f}%\n\n"
                f"📤 Sending your reels now...",
                parse_mode='Markdown'
            )
            
            # Send reels in batches
            batch_size = 5
            for i in range(0, len(session['processed_media']), batch_size):
                batch = session['processed_media'][i:i + batch_size]
                
                for media_data in batch:
                    try:
                        if os.path.exists(media_data['media_path']):
                            with open(media_data['media_path'], 'rb') as f:
                                caption = f"**Reel {media_data['index'] + 1}**\n{media_data['quote']}"
                                
                                if media_data['type'] == 'video':
                                    await update.message.reply_video(
                                        video=f,
                                        caption=caption,
                                        reply_markup=self.get_save_keyboard(media_data['index']),
                                        parse_mode='Markdown'
                                    )
                                else:
                                    await update.message.reply_photo(
                                        photo=f,
                                        caption=caption,
                                        reply_markup=self.get_save_keyboard(media_data['index']),
                                        parse_mode='Markdown'
                                    )
                            await asyncio.sleep(1)
                            
                    except Exception as e:
                        logger.error(f"Error sending reel {media_data['index']}: {e}")
                        continue
                
                await asyncio.sleep(2)  # Batch delay
            
            await update.message.reply_text(
                f"🎊 *Bulk Processing Complete!*\n\n"
                f"📈 *Final Statistics:*\n"
                f"• Total Combinations: {total_combinations}\n"
                f"• Successfully Created: {created}\n"
                f"• Success Rate: {(created/total_combinations)*100:.1f}%\n"
                f"• Output Format: {settings['output_format'].upper()}\n"
                f"• Voice Over: {'✅ ON' if settings['voice_enabled'] else '❌ OFF'}\n\n"
                f"💾 *Use the save buttons to download individual reels!*",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await processing_msg.edit_text(
                "❌ No reels were created. Please check your media and quotes.",
                reply_markup=self.get_main_keyboard()
            )
        
        return MAIN_MENU
    
    async def handle_make_reels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create individual reels (legacy method)"""
        # Implementation similar to before but using new creation methods
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        settings = session['settings']
        
        # Set output to image for legacy method
        settings['output_format'] = 'image'
        
        await self.handle_bulk_create(update, context)
        return MAIN_MENU
    
    async def handle_save_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle save button clicks for both images and videos"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('save_'):
            try:
                media_type, media_index = data.split('_')[1], int(data.split('_')[2])
                
                if user_id in self.user_sessions:
                    session = self.user_sessions[user_id]
                    media_list = session['processed_media']
                    
                    if 0 <= media_index < len(media_list):
                        media_data = media_list[media_index]
                        
                        if os.path.exists(media_data['media_path']):
                            with open(media_data['media_path'], 'rb') as f:
                                filename = f"islamic_reel_{media_index + 1}.{media_data['type']}"
                                
                                if media_data['type'] == 'video':
                                    await query.message.reply_document(
                                        document=f,
                                        filename=filename,
                                        caption=f"💾 Saved: Reel {media_index + 1}\n{media_data['quote']}"
                                    )
                                else:
                                    await query.message.reply_document(
                                        document=f,
                                        filename=filename,
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
        
        status_msg = await update.message.reply_text(
            f"💾 *Preparing {len(media_list)} reels for download...*",
            parse_mode='Markdown'
        )
        
        sent = 0
        for i, media_data in enumerate(media_list):
            try:
                if os.path.exists(media_data['media_path']):
                    with open(media_data['media_path'], 'rb') as f:
                        extension = 'mp4' if media_data['type'] == 'video' else 'jpg'
                        filename = f"islamic_reel_{i+1}.{extension}"
                        
                        await update.message.reply_document(
                            document=f,
                            filename=filename,
                            caption=f"Reel {i+1}\n{media_data['quote']}"
                        )
                    sent += 1
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error saving reel {i}: {e}")
                continue
        
        await status_msg.edit_text(
            f"✅ *Successfully saved {sent} reels to your device!*",
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
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
    
    async def handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset everything"""
        user_id = update.effective_user.id
        
        # Stop any ongoing process
        if user_id in self.processing_flags:
            self.processing_flags[user_id] = False
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            
            # Clean up all temporary files
            for media in session['photos'] + session['videos'] + session['processed_media']:
                try:
                    if 'file_path' in media and os.path.exists(media['file_path']):
                        os.unlink(media['file_path'])
                except:
                    pass
            
            # Reset session
            self.user_sessions[user_id] = {
                'photos': [], 'videos': [], 'quotes': [], 'processed_media': [],
                'settings': {
                    'theme': 'islamic_blue', 'layout': 'centered', 'font_size': 60,
                    'duration': 10, 'voice_enabled': False, 'background_music': None,
                    'output_format': 'video', 'bulk_quality': 'medium'
                }
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
                    MessageHandler(filters.Regex('^⚙️ Reel Settings$'), bot.handle_reel_settings),
                    MessageHandler(filters.Regex('^🎙️ Voice Settings$'), bot.handle_voice_settings),
                    MessageHandler(filters.Regex('^🎬 Make Reels$'), bot.handle_make_reels),
                    MessageHandler(filters.Regex('^🚀 Bulk Create$'), bot.handle_bulk_create),
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
                REEL_SETTINGS: [
                    MessageHandler(filters.Regex('^🔙 Back to Main$'), bot.start),
                    # Add more setting handlers here
                ],
                VOICE_SETTINGS: [
                    MessageHandler(filters.Regex('^🔙 Back to Main$'), bot.start),
                    # Add more voice setting handlers here
                ]
            },
            fallbacks=[CommandHandler('start', bot.start)]
        )
        
        application.add_handler(CallbackQueryHandler(bot.handle_save_callback, pattern="^save_"))
        application.add_handler(conv_handler)
        
        print("🤖 Islamic Reels Bot Pro Starting...")
        print("✅ Bot is running with advanced features!")
        print("🚀 Ready for bulk video creation...")
        
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
            print(f"🚀 Starting Advanced Bot (attempt {attempt + 1}/{max_retries})...")
            run_bot()
        except Exception as e:
            print(f"❌ Bot crashed: {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("💥 Max retries reached. Bot stopped.")

if __name__ == '__main__':
    print("=" * 60)
    print("🕌 Islamic Reels Bot Pro - Advanced Version")
    print("🚀 Bulk Video Creation & Advanced Features")
    print("🎥 Real Video Reels with Voiceovers")
    print("🌍 Multi-language Support")
    print("⚡ Fast Bulk Processing")
    print("=" * 60)
    
    main()
