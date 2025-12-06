import os
import tempfile
import asyncio
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
import requests
import time
import moviepy.editor as mp
from moviepy.editor import CompositeVideoClip, TextClip, ColorClip, AudioFileClip
import numpy as np
from io import BytesIO

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8422015788:AAF2HozDLDeDVMXD0HLwCa0LGWIcdK6S2p0"

# Conversation states
MAIN_MENU, UPLOADING_IMAGES, ADDING_QUOTES = range(3)

class ImageToVideoBot:
    def __init__(self):
        self.user_sessions = {}
        self.processing_flags = {}
        self.VIDEO_DURATION = 17  # Fixed 17 seconds
        self.VIDEO_FPS = 24
        self.VIDEO_SIZE = (1080, 1350)  # Instagram Reels size
        
        # Download background music
        self.background_music_path = 'background_music.mp3'
        self.download_background_music()
    
    def download_background_music(self):
        """Download background music"""
        if not os.path.exists(self.background_music_path):
            try:
                # Free copyright-free background music
                music_url = "https://assets.mixkit.co/music/preview/mixkit-chill-abstract-loop-229.mp3"
                response = requests.get(music_url, timeout=30)
                if response.status_code == 200:
                    with open(self.background_music_path, 'wb') as f:
                        f.write(response.content)
                    logger.info("Downloaded background music")
            except Exception as e:
                logger.error(f"Could not download music: {e}")
                # Create silent audio as fallback
                from moviepy.audio.io.AudioFileClip import AudioFileClip
                silent_audio = AudioFileClip().set_duration(1).volumex(0)
                silent_audio.write_audiofile(self.background_music_path, logger=None)
    
    def get_main_keyboard(self):
        """Create main menu buttons"""
        keyboard = [
            [KeyboardButton("📤 Upload Images"), KeyboardButton("📝 Add Quotes")],
            [KeyboardButton("🎬 Create Videos (17s)"), KeyboardButton("💾 Download All")],
            [KeyboardButton("🛑 Stop Process"), KeyboardButton("🔄 Reset")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Choose an option...")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'images': [],
            'quotes': [],
            'videos': [],
            'processing': False
        }
        
        welcome_text = """
🎬 *Bulk Image to Video Converter*

*Convert Images to 17-Second Videos*

📊 *Stats:*
• Images: 0
• Quotes: 0
• Videos: 0

✨ *Features:*
✅ Convert images to MP4 videos
✅ 17-second duration (fixed)
✅ Background music
✅ Text overlay
✅ Bulk processing
✅ Download all videos

*How to use:*
1️⃣ Upload images
2️⃣ Add quotes (optional)
3️⃣ Create videos
4️⃣ Download all

Use buttons below to get started! 🚀
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    async def handle_upload_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image uploads"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        await update.message.reply_text(
            "📤 *Send me images*:\n\n"
            "• Send multiple images at once\n"
            "• Supported formats: JPG, PNG\n"
            "• Maximum 10 images per batch\n\n"
            "Click '📝 Add Quotes' when done",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        return UPLOADING_IMAGES
    
    async def handle_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process uploaded images"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return UPLOADING_IMAGES
        
        try:
            if update.message.photo:
                # Get the highest resolution photo
                photo_file = await update.message.photo[-1].get_file()
                
                # Download image to memory
                image_data = await photo_file.download_as_bytearray()
                
                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(image_data)
                    temp_path = temp_file.name
                
                # Store image info
                self.user_sessions[user_id]['images'].append({
                    'file_path': temp_path,
                    'file_id': photo_file.file_id,
                    'index': len(self.user_sessions[user_id]['images'])
                })
                
                count = len(self.user_sessions[user_id]['images'])
                await update.message.reply_text(
                    f"✅ Image {count} saved!",
                    reply_markup=self.get_main_keyboard()
                )
            
            elif update.message.document and update.message.document.mime_type in ['image/jpeg', 'image/png']:
                # Handle document images
                doc_file = await update.message.document.get_file()
                
                # Download image to memory
                image_data = await doc_file.download_as_bytearray()
                
                # Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(image_data)
                    temp_path = temp_file.name
                
                # Store image info
                self.user_sessions[user_id]['images'].append({
                    'file_path': temp_path,
                    'file_id': doc_file.file_id,
                    'index': len(self.user_sessions[user_id]['images'])
                })
                
                count = len(self.user_sessions[user_id]['images'])
                await update.message.reply_text(
                    f"✅ Image {count} saved!",
                    reply_markup=self.get_main_keyboard()
                )
        
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            await update.message.reply_text(
                "❌ Error saving image. Please try again.",
                reply_markup=self.get_main_keyboard()
            )
        
        return UPLOADING_IMAGES
    
    async def handle_add_quotes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quote input"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        image_count = len(self.user_sessions[user_id]['images'])
        
        if image_count == 0:
            await update.message.reply_text(
                "❌ Please upload images first!",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        await update.message.reply_text(
            f"📝 *Add quotes (optional):*\n\n"
            f"You have {image_count} images ready.\n"
            f"Send your quotes (one per line):\n\n"
            f"*Example:*\n"
            f"Quote 1\n"
            f"Quote 2\n"
            f"Quote 3\n\n"
            f"If no quotes provided, videos will be created without text.",
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
        
        image_count = len(self.user_sessions[user_id]['images'])
        
        # Store quotes (use empty string if no quotes provided)
        if quotes_list:
            self.user_sessions[user_id]['quotes'] = quotes_list
            quote_info = f"📝 Quotes: {len(quotes_list)}"
        else:
            self.user_sessions[user_id]['quotes'] = [""] * image_count
            quote_info = "📝 No quotes (videos without text)"
        
        await update.message.reply_text(
            f"✅ *Ready to create videos!*\n\n"
            f"📊 *Summary:*\n"
            f"📷 Images: {image_count}\n"
            f"{quote_info}\n"
            f"🎬 Videos to create: {image_count} × 17 seconds each\n\n"
            f"Click '🎬 Create Videos (17s)' to start!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    def prepare_image_for_video(self, image_path):
        """Prepare image for video - resize and enhance"""
        try:
            img = Image.open(image_path)
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to fit video dimensions while maintaining aspect ratio
            img.thumbnail((self.VIDEO_SIZE[0] * 1.2, self.VIDEO_SIZE[1] * 1.2), Image.Resampling.LANCZOS)
            
            # Create a black background
            background = Image.new('RGB', self.VIDEO_SIZE, (0, 0, 0))
            
            # Paste image centered on background
            x = (self.VIDEO_SIZE[0] - img.width) // 2
            y = (self.VIDEO_SIZE[1] - img.height) // 2
            background.paste(img, (x, y))
            
            # Save processed image
            processed_path = tempfile.mktemp(suffix='_processed.jpg')
            background.save(processed_path, quality=95)
            
            return processed_path
            
        except Exception as e:
            logger.error(f"Error preparing image: {e}")
            return image_path
    
    def create_ken_burns_effect(self, image_path, duration):
        """Create Ken Burns effect (zoom + pan)"""
        try:
            # Load image
            img_clip = mp.ImageClip(image_path, duration=duration)
            
            # Ken Burns effect: slow zoom in + subtle pan
            def zoom_func(t):
                # Zoom from 1.0 to 1.1 over the duration
                return 1.0 + 0.1 * (t / duration)
            
            def pan_func(t):
                # Gentle pan movement
                x_pan = 0.01 * np.sin(t * 0.5)  # Slow horizontal movement
                y_pan = 0.005 * np.cos(t * 0.3)  # Slower vertical movement
                return ('center', 'center')
            
            # Apply effects
            zoomed_clip = img_clip.resize(zoom_func)
            final_clip = zoomed_clip.set_position(pan_func)
            
            return final_clip
            
        except Exception as e:
            logger.error(f"Error creating Ken Burns effect: {e}")
            return mp.ImageClip(image_path, duration=duration)
    
    def add_text_overlay(self, video_clip, text, duration):
        """Add text overlay to video"""
        if not text or text.strip() == "":
            return video_clip
        
        try:
            # Split long text into lines
            max_chars_per_line = 30
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                if len(' '.join(current_line + [word])) <= max_chars_per_line:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Join lines with newline
            display_text = '\n'.join(lines)
            
            # Create text clip
            font_size = 60
            text_clip = TextClip(
                display_text,
                fontsize=font_size,
                color='white',
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(self.VIDEO_SIZE[0] * 0.9, None),
                align='center'
            ).set_duration(duration)
            
            # Position text (lower third for social media)
            text_clip = text_clip.set_position(('center', 'bottom')).margin(bottom=100, opacity=0)
            
            # Add fade in/out
            text_clip = text_clip.fadein(1).fadeout(1)
            
            # Composite video with text
            return CompositeVideoClip([video_clip, text_clip])
            
        except Exception as e:
            logger.error(f"Error adding text overlay: {e}")
            return video_clip
    
    def add_background_music(self, video_clip, duration):
        """Add background music to video"""
        try:
            if os.path.exists(self.background_music_path):
                # Load background music
                audio_clip = AudioFileClip(self.background_music_path)
                
                # Loop music to match video duration
                if audio_clip.duration < duration:
                    # Calculate loops needed
                    loops_needed = int(np.ceil(duration / audio_clip.duration))
                    audio_segments = [audio_clip] * loops_needed
                    audio_clip = mp.concatenate_audioclips(audio_segments)
                
                # Trim to exact duration
                audio_clip = audio_clip.subclip(0, duration)
                
                # Reduce volume to 30%
                audio_clip = audio_clip.volumex(0.3)
                
                # Set audio to video
                video_clip = video_clip.set_audio(audio_clip)
                
                return video_clip
            
        except Exception as e:
            logger.warning(f"Could not add background music: {e}")
        
        return video_clip
    
    async def create_single_video(self, image_path, quote, index, total):
        """Create a single 17-second video from image"""
        try:
            # Prepare image
            processed_image = self.prepare_image_for_video(image_path)
            
            # Create video with Ken Burns effect
            video_clip = self.create_ken_burns_effect(processed_image, self.VIDEO_DURATION)
            
            # Add text overlay
            video_clip = self.add_text_overlay(video_clip, quote, self.VIDEO_DURATION)
            
            # Add background music
            video_clip = self.add_background_music(video_clip, self.VIDEO_DURATION)
            
            # Set video size
            video_clip = video_clip.resize(self.VIDEO_SIZE)
            
            # Create output file
            output_path = tempfile.mktemp(suffix=f'_video_{index}.mp4')
            
            # Write video file (optimized for speed)
            video_clip.write_videofile(
                output_path,
                fps=self.VIDEO_FPS,
                codec='libx264',
                audio_codec='aac',
                preset='ultrafast',
                threads=2,
                ffmpeg_params=['-crf', '28'],  # Higher CRF for faster encoding
                logger=None,
                verbose=False
            )
            
            # Clean up
            video_clip.close()
            if processed_image != image_path and os.path.exists(processed_image):
                os.unlink(processed_image)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating video {index}: {e}")
            return None
    
    async def handle_create_videos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create 17-second videos from all images"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        session = self.user_sessions[user_id]
        images = session['images']
        quotes = session['quotes']
        
        if not images:
            await update.message.reply_text(
                "❌ No images found! Please upload images first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        # Clear previous videos
        session['videos'] = []
        
        # Set processing flag
        self.processing_flags[user_id] = True
        
        # Send initial message
        total_images = len(images)
        progress_msg = await update.message.reply_text(
            f"🎬 *Starting video creation...*\n\n"
            f"📊 Total images: {total_images}\n"
            f"⏱️ Duration per video: 17 seconds\n"
            f"⏳ Estimated time: {total_images * 10} seconds\n\n"
            f"🔄 Processing... 0/{total_images}",
            parse_mode='Markdown'
        )
        
        created_count = 0
        
        # Process images in sequence
        for i, image_data in enumerate(images):
            # Check if user stopped the process
            if not self.processing_flags.get(user_id, True):
                await progress_msg.edit_text("🛑 Process stopped by user!")
                break
            
            try:
                # Update progress
                await progress_msg.edit_text(
                    f"🎬 *Creating videos...*\n\n"
                    f"🔄 Processing image {i+1}/{total_images}\n"
                    f"✅ Created: {created_count}\n"
                    f"⏱️ Each video: 17 seconds",
                    parse_mode='Markdown'
                )
                
                # Get quote for this image (cycle through quotes if available)
                if quotes and len(quotes) > 0:
                    quote_index = i % len(quotes)
                    quote = quotes[quote_index]
                else:
                    quote = ""
                
                # Create video
                video_path = await self.create_single_video(
                    image_data['file_path'],
                    quote,
                    i,
                    total_images
                )
                
                if video_path and os.path.exists(video_path):
                    # Store video info
                    session['videos'].append({
                        'file_path': video_path,
                        'image_index': i,
                        'quote': quote,
                        'index': created_count
                    })
                    created_count += 1
                    
                    # Send preview every 3 videos
                    if created_count % 3 == 0 or created_count == total_images:
                        with open(video_path, 'rb') as f:
                            await update.message.reply_video(
                                video=f,
                                caption=f"✅ Video {created_count}/{total_images}\n"
                                       f"⏱️ 17 seconds",
                                supports_streaming=True
                            )
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing image {i}: {e}")
                continue
        
        # Clean up processing flag
        if user_id in self.processing_flags:
            del self.processing_flags[user_id]
        
        # Send completion message
        if created_count > 0:
            await progress_msg.edit_text(
                f"✅ *Video creation complete!*\n\n"
                f"📊 *Results:*\n"
                f"📷 Images processed: {total_images}\n"
                f"🎬 Videos created: {created_count}\n"
                f"⏱️ Duration per video: 17 seconds\n"
                f"💾 Total size: ~{created_count * 5} MB\n\n"
                f"Click '💾 Download All' to download all videos!",
                parse_mode='Markdown',
                reply_markup=self.get_main_keyboard()
            )
        else:
            await progress_msg.edit_text(
                "❌ No videos were created. Please try again.",
                reply_markup=self.get_main_keyboard()
            )
        
        return MAIN_MENU
    
    async def handle_download_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download all created videos"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            await self.start(update, context)
            return MAIN_MENU
        
        videos = self.user_sessions[user_id]['videos']
        
        if not videos:
            await update.message.reply_text(
                "❌ No videos found! Create videos first.",
                reply_markup=self.get_main_keyboard()
            )
            return MAIN_MENU
        
        status_msg = await update.message.reply_text(
            f"💾 *Preparing {len(videos)} videos for download...*\n\n"
            f"📦 Creating archive...",
            parse_mode='Markdown'
        )
        
        # Send videos one by one
        for i, video_data in enumerate(videos):
            try:
                if os.path.exists(video_data['file_path']):
                    with open(video_data['file_path'], 'rb') as f:
                        await update.message.reply_document(
                            document=f,
                            filename=f"video_{i+1}_17s.mp4",
                            caption=f"Video {i+1}/17 seconds"
                        )
                    
                    # Update status every 5 videos
                    if (i + 1) % 5 == 0:
                        await status_msg.edit_text(
                            f"💾 *Downloading videos...*\n\n"
                            f"📤 Sent: {i+1}/{len(videos)}",
                            parse_mode='Markdown'
                        )
                    
                    # Rate limiting
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error sending video {i}: {e}")
                continue
        
        await status_msg.edit_text(
            f"✅ *All videos sent!*\n\n"
            f"📊 Total: {len(videos)} videos\n"
            f"⏱️ Each: 17 seconds\n\n"
            f"All videos are 17-second MP4 files ready for use!",
            parse_mode='Markdown',
            reply_markup=self.get_main_keyboard()
        )
        
        return MAIN_MENU
    
    async def handle_stop_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop ongoing processing"""
        user_id = update.effective_user.id
        
        if user_id in self.processing_flags:
            self.processing_flags[user_id] = False
            await update.message.reply_text(
                "🛑 *Processing stopped!*\n\nVideo creation has been cancelled.",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ *No active process to stop.*",
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
            for image in session['images']:
                try:
                    if os.path.exists(image['file_path']):
                        os.unlink(image['file_path'])
                except:
                    pass
            
            for video in session['videos']:
                try:
                    if os.path.exists(video['file_path']):
                        os.unlink(video['file_path'])
                except:
                    pass
            
            # Reset session
            self.user_sessions[user_id] = {'images': [], 'quotes': [], 'videos': [], 'processing': False}
        
        await update.message.reply_text(
            "🔄 *Reset complete!*\n\nAll data cleared. You can start fresh!",
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return MAIN_MENU

def main():
    """Run the bot"""
    try:
        # Create bot instance
        bot = ImageToVideoBot()
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Create conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', bot.start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.Regex('^📤 Upload Images$'), bot.handle_upload_images),
                    MessageHandler(filters.Regex('^📝 Add Quotes$'), bot.handle_add_quotes),
                    MessageHandler(filters.Regex('^🎬 Create Videos \(17s\)$'), bot.handle_create_videos),
                    MessageHandler(filters.Regex('^💾 Download All$'), bot.handle_download_all),
                    MessageHandler(filters.Regex('^🛑 Stop Process$'), bot.handle_stop_process),
                    MessageHandler(filters.Regex('^🔄 Reset$'), bot.handle_reset),
                ],
                UPLOADING_IMAGES: [
                    MessageHandler(filters.PHOTO | filters.Document.IMAGE, bot.handle_images),
                ],
                ADDING_QUOTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_quotes)
                ]
            },
            fallbacks=[CommandHandler('start', bot.start)],
            allow_reentry=True
        )
        
        # Add handlers
        application.add_handler(conv_handler)
        
        print("=" * 50)
        print("🤖 Bulk Image to Video Bot")
        print(f"🎬 Converts images to 17-second MP4 videos")
        print("📊 Bulk processing supported")
        print("💾 BOT_TOKEN Loaded")
        print("=" * 50)
        print("\n🚀 Bot is starting...")
        
        # Start the bot
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("🔄 Restarting in 5 seconds...")
        time.sleep(5)
        main()

if __name__ == '__main__':
    print("Starting Bulk Image to Video Converter Bot...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...")  # Show only first 10 chars for security
    main()
