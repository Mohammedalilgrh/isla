from flask import Flask, request
from threading import Thread
import telebot
from telebot import types
import sqlite3
import time
import logging
from datetime import datetime
import hashlib
import os
import tempfile
import asyncio
import arabic_reshaper
from bidi.algorithm import get_display
import requests
import yt_dlp
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy.editor as mp
from moviepy.editor import concatenate_videoclips, CompositeVideoClip, TextClip, ColorClip, AudioFileClip
import json
import urllib.parse
import concurrent.futures

# ==============================
# CONFIGURATION - إعدادات البوت
# ==============================
TOKEN = '7897542906:AAFWO23YZhUhLpDJ500d6yZ4jcUnPZY450g'  # توكن بوتك
ADMIN_CHAT_ID = "YOUR_ADMIN_ID"  # أضف آيدي حسابك هنا
CHANNELS = ["@s111sgrh"]  # القنوات المطلوبة للاشتراك
ORDER_CHANNEL = "@intorders"  # قناتك للطلبات (أنت الذي توافق عليها)
DOWNLOAD_PATH = "downloads"
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB
MAX_BULK_ITEMS = 50
SUPPORTED_DOMAINS = [
    'youtube.com', 'youtu.be',
    'facebook.com', 'fb.watch',
    'instagram.com', 'instagr.am',
    'tiktok.com', 'vm.tiktok.com',
    'twitter.com', 'x.com',
    'reddit.com',
    'pinterest.com',
    'likee.video',
    'twitch.tv',
    'dailymotion.com',
    'vimeo.com',
]

# Initialize Flask app
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)

# ==============================
# DATABASE SETUP - قاعدة البيانات
# ==============================
def init_db():
    conn = sqlite3.connect("data.db", check_same_thread=False)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        referral_code TEXT UNIQUE,
        withdraw_code TEXT UNIQUE,
        balance REAL DEFAULT 0.0,
        total_referrals INTEGER DEFAULT 0,
        active_referrals INTEGER DEFAULT 0,
        has_purchased BOOLEAN DEFAULT 0,
        user_type TEXT DEFAULT 'free',  # free, paid, agent
        joined_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_active DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Referrals tracking
    c.execute('''CREATE TABLE IF NOT EXISTS referral_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        reward_amount REAL DEFAULT 0.10,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Payment requests
    c.execute('''CREATE TABLE IF NOT EXISTS payment_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        phone_number TEXT,
        amount REAL,
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Withdrawal requests
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawal_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        method TEXT,
        account_info TEXT,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Services usage
    c.execute('''CREATE TABLE IF NOT EXISTS service_usage (
        usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_type TEXT,  # reels, download, etc
        usage_count INTEGER DEFAULT 1,
        last_used DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Agent commissions
    c.execute('''CREATE TABLE IF NOT EXISTS agent_commissions (
        commission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER,
        user_id INTEGER,
        amount REAL,
        description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    return conn, c

conn, c = init_db()

# ==============================
# HELPER FUNCTIONS - دوال مساعدة
# ==============================
def generate_referral_code(user_id):
    """توليد كود إحالة"""
    return f"REF_{user_id}_{int(time.time())}"

def generate_withdraw_code(user_id):
    """توليد كود سحب"""
    return hashlib.md5(f"{user_id}_{time.time()}".encode()).hexdigest()[:8].upper()

def check_subscription(user_id):
    """فحص الاشتراك في القنوات"""
    try:
        for channel in CHANNELS:
            chat_member = bot.get_chat_member(channel, user_id)
            if chat_member.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return False

def get_user_info(user_id):
    """الحصول على معلومات المستخدم"""
    c.execute("SELECT username, full_name, user_type, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        username, full_name, user_type, balance = result
        name = f"@{username}" if username and username != "None" else full_name
        return name, user_type, balance
    return "مستخدم", "free", 0.0

def update_user_activity(user_id):
    """تحديث نشاط المستخدم"""
    c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", 
             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()

def get_user_balance(user_id):
    """الحصول على رصيد المستخدم"""
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result[0] if result else 0.0

def get_referral_stats(user_id):
    """الحصول على إحصائيات الإحالات"""
    c.execute("SELECT COUNT(*) FROM referral_logs WHERE referrer_id = ?", (user_id,))
    total_refs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referral_logs WHERE referrer_id = ? AND status = 'approved'", (user_id,))
    active_refs = c.fetchone()[0]
    return total_refs, active_refs

def can_use_service(user_id, service_type):
    """فحص إذا كان المستخدم يمكنه استخدام الخدمة"""
    c.execute("SELECT user_type, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        user_type, balance = result
        # يمكن للجميع استخدام الخدمات الأساسية
        if user_type in ['paid', 'agent']:
            return True
        elif user_type == 'free':
            # مجاني يمكنه استخدام خدمات محدودة
            c.execute("SELECT COUNT(*) FROM service_usage WHERE user_id = ? AND service_type = ?", 
                     (user_id, service_type))
            usage_count = c.fetchone()[0]
            return usage_count < 3  # 3 استخدامات مجانية لكل خدمة
    return False

def log_service_usage(user_id, service_type):
    """تسجيل استخدام الخدمة"""
    c.execute("""
        INSERT INTO service_usage (user_id, service_type) 
        VALUES (?, ?)
        ON CONFLICT(user_id, service_type) 
        DO UPDATE SET usage_count = usage_count + 1, last_used = ?
    """, (user_id, service_type, datetime.now()))
    conn.commit()

def get_withdraw_code(user_id):
    """الحصول على كود السحب"""
    c.execute("SELECT withdraw_code FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0]:
        return result[0]
    else:
        code = generate_withdraw_code(user_id)
        c.execute("UPDATE users SET withdraw_code = ? WHERE user_id = ?", (code, user_id))
        conn.commit()
        return code

# ==============================
# TEXTS & KEYBOARDS - النصوص ولوحات المفاتيح
# ==============================
def get_main_menu_markup(user_type='free'):
    """لوحة القائمة الرئيسية"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    
    if user_type == 'free':
        markup.row("🚀 شراء اشتراك", "💰 سحب الأرباح")
        markup.row("🎬 صنع الريلز الإسلامية", "📥 تحميل الفيديوهات")
        markup.row("📊 إحصائياتي", "👥 الإحالات")
        markup.row("🆓 خدمات مجانية", "🆘 المساعدة")
    elif user_type == 'paid':
        markup.row("🎬 صنع الريلز الإسلامية", "📥 تحميل الفيديوهات")
        markup.row("💰 سحب الأرباح", "👥 الإحالات")
        markup.row("📊 إحصائياتي", "🔄 تحديث")
        markup.row("⭐ مميزات إضافية", "🆘 المساعدة")
    else:  # agent
        markup.row("👑 لوحة الوكيل", "💰 سحب الأرباح")
        markup.row("🎬 صنع الريلز الإسلامية", "📥 تحميل الفيديوهات")
        markup.row("📊 إحصائياتي", "👥 فريق الإحالات")
        markup.row("⭐ إدارة الخدمات", "🆘 المساعدة")
    
    return markup

def get_services_markup():
    """لوحة الخدمات"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row("🎬 صنع ريلز إسلامية", "📥 تحميل فيديو")
    markup.row("📚 تحميل جماعي", "📺 تحميل قناة")
    markup.row("🔙 القائمة الرئيسية")
    return markup

def get_payment_methods_markup():
    """طرق الدفع"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row("💳 آسيا سيل", "💳 زين العراق")
    markup.row("💳 بطاقات ائتمان", "💳 كريبتو")
    markup.row("🔙 القائمة الرئيسية")
    return markup

def get_withdraw_methods_markup():
    """طرق السحب"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row("💳 زين العراق", "💳 آسيا سيل")
    markup.row("💳 باي بال", "💳 كريبتو")
    markup.row("💳 ويسترن يونيون", "🔙 القائمة الرئيسية")
    return markup

# ==============================
# COMMAND HANDLERS - معالجات الأوامر
# ==============================
@bot.message_handler(commands=['start', 'restart'])
def start_command(message):
    """معالجة أمر /start"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "None"
        full_name = message.from_user.first_name or ""
        if message.from_user.last_name:
            full_name += f" {message.from_user.last_name}"

        # Check subscription
        if not check_subscription(user_id):
            show_subscription_alert(message)
            return

        # Check for referral code
        referral_code = None
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]

        # Register/update user
        ref_code = generate_referral_code(user_id)
        withdraw_code = generate_withdraw_code(user_id)
        
        c.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, referral_code, withdraw_code) 
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, full_name, ref_code, withdraw_code))
        
        c.execute("""
            UPDATE users SET 
            username = ?, 
            full_name = ?,
            last_active = ?,
            withdraw_code = COALESCE(withdraw_code, ?)
            WHERE user_id = ?
        """, (username, full_name, datetime.now(), withdraw_code, user_id))
        
        # Process referral if exists
        if referral_code:
            process_referral(user_id, referral_code)
        
        conn.commit()
        
        # Show welcome message
        show_welcome_message(message)
        
    except Exception as e:
        logging.error(f"Start command error: {e}")
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة لاحقاً")

def process_referral(user_id, referral_code):
    """معالجة الإحالة"""
    try:
        if not referral_code.startswith("REF_") or len(referral_code.split('_')) < 2:
            return
        
        referrer_id = int(referral_code.split('_')[1])
        
        # Check if self-referral
        if referrer_id == user_id:
            return
        
        # Check if already referred
        c.execute("SELECT 1 FROM referral_logs WHERE referred_id = ?", (user_id,))
        if c.fetchone():
            return
        
        # Check if referrer exists
        c.execute("SELECT user_type FROM users WHERE user_id = ?", (referrer_id,))
        referrer_data = c.fetchone()
        if not referrer_data:
            return
        
        referrer_type = referrer_data[0]
        
        # Log referral
        c.execute("INSERT OR IGNORE INTO referral_logs (referrer_id, referred_id) VALUES (?, ?)",
                 (referrer_id, user_id))
        
        # Update referrer stats
        c.execute("UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?",
                 (referrer_id,))
        
        # Add reward for agents and paid users
        if referrer_type in ['paid', 'agent']:
            c.execute("UPDATE users SET balance = balance + 0.10, active_referrals = active_referrals + 1 WHERE user_id = ?",
                     (referrer_id,))
            
            # Notify referrer
            try:
                user_info = get_user_info(user_id)
                referrer_balance = get_user_balance(referrer_id)
                bot.send_message(
                    referrer_id,
                    f"🎉 **حصلت على 0.10$ مقابل إحالة جديدة!**\n\n"
                    f"👤 المستخدم: {user_info[0]}\n"
                    f"💰 رصيدك الجديد: {referrer_balance:.2f}$\n\n"
                    f"استمر في نشر رابطك لكسب المزيد! 🔗"
                )
            except:
                pass
        
        # If referrer is an agent, add commission
        if referrer_type == 'agent':
            c.execute("INSERT INTO agent_commissions (agent_id, user_id, amount, description) VALUES (?, ?, ?, ?)",
                     (referrer_id, user_id, 0.05, f"عمولة إحالة جديدة: {user_id}"))
        
    except Exception as e:
        logging.error(f"Referral processing error: {e}")

def show_subscription_alert(message):
    """عرض تحذير الاشتراك"""
    markup = types.InlineKeyboardMarkup()
    for channel in CHANNELS:
        markup.add(types.InlineKeyboardButton(f"انضم إلى {channel}", url=f"https://t.me/{channel.strip('@')}"))
    markup.add(types.InlineKeyboardButton("✅ تم الاشتراك", callback_data="check_sub"))
    bot.send_message(message.chat.id, 
                    "⚠️ **للبدء، يرجى الانضمام إلى قنواتنا:**",
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription_callback(call):
    """فحص الاشتراك"""
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_welcome_message(call.message)
    else:
        bot.answer_callback_query(call.id, "❗ لم تنضم لجميع القنوات", show_alert=True)

def show_welcome_message(message):
    """عرض رسالة الترحيب"""
    user_id = message.from_user.id
    update_user_activity(user_id)
    
    user_info = get_user_info(user_id)
    name, user_type, balance = user_info
    total_refs, active_refs = get_referral_stats(user_id)
    
    welcome_text = f"""
🚀 **أهلاً بك {name} في بوت الربح من الإنترنت!** 👋

🎯 **نوع حسابك:** {'🆓 مجاني' if user_type == 'free' else '⭐ مميز' if user_type == 'paid' else '👑 وكيل'}
💰 **رصيدك الحالي:** {balance:.2f}$
👥 **إحالاتك:** {active_refs} نشطة من {total_refs}

✨ **ماذا يمكنك أن تفعل؟**

1️⃣ **الربح من الإحالات:** احصل على 0.10$ لكل شخص يشترك عبر رابطك
2️⃣ **صنع الريلز الإسلامية:** أنشئ ريلز إسلامية احترافية
3️⃣ **تحميل الفيديوهات:** حمل من يوتيوب، انستغرام، تيك توك وغيرها
4️⃣ **خدمات مجانية:** استخدم خدمات محدودة مجاناً

🔗 **رابط الإحالة الخاص بك:**
`https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}`

📌 **شارك الرابط واكسب 0.10$ لكل إحالة!**

👇 **اختر من القائمة:**
    """
    
    bot.send_message(message.chat.id, welcome_text, 
                     reply_markup=get_main_menu_markup(user_type),
                     parse_mode='Markdown')

# ==============================
# SERVICE HANDLERS - معالجات الخدمات
# ==============================
@bot.message_handler(func=lambda message: message.text == "🚀 شراء اشتراك")
def handle_purchase(message):
    """شراء اشتراك"""
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    
    if user_info[1] != 'free':
        bot.send_message(message.chat.id, "✅ لديك اشتراك نشط بالفعل!", 
                         reply_markup=get_main_menu_markup(user_info[1]))
        return
    
    purchase_text = """
💳 **شراء اشتراك مميز**

🌟 **بسعر 2$ فقط تحصل على:**

✅ **ميزات غير محدودة لصنع الريلز الإسلامية**
✅ **تحميل غير محدود للفيديوهات**
✅ **ربح 0.10$ لكل إحالة جديدة**
✅ **دعم فني متميز**
✅ **وصول إلى جميع الميزات الجديدة**

💰 **طريقة الدفع:**
1. ادفع 2$ عبر أي طريقة دفع
2. أرسل إيصال الدفع إلينا
3. سنقوم بالتفعيل خلال 24 ساعة

👇 **اختر طريقة الدفع:**
    """
    
    bot.send_message(message.chat.id, purchase_text,
                     reply_markup=get_payment_methods_markup())

@bot.message_handler(func=lambda message: message.text in ["💳 آسيا سيل", "💳 زين العراق", "💳 بطاقات ائتمان", "💳 كريبتو"])
def handle_payment_method(message):
    """معالجة طريقة الدفع"""
    method_text = message.text
    method_map = {
        "💳 آسيا سيل": "asiacell",
        "💳 زين العراق": "zain",
        "💳 بطاقات ائتمان": "card",
        "💳 كريبتو": "crypto"
    }
    
    method = method_map.get(method_text, "other")
    
    instructions = f"""
📌 **تعليمات الدفع عبر {method_text}:**

1. قم بتحويل 2$ إلى الرقم/الحساب المخصص
2. احفظ إيصال التحويل
3. أرسل لنا رقم الهاتف/الحساب الذي استخدمته
4. سنتحقق ونتصل بك للتأكيد

💡 **معلومة:** بعد التأكيد، ستتمتع بجميع الميزات وتبدأ بجني 0.10$ لكل إحالة!

📱 **أرسل رقم الهاتف/الحساب الذي استخدمته للدفع:**
    """
    
    msg = bot.send_message(message.chat.id, instructions)
    bot.register_next_step_handler(msg, lambda m: process_payment_info(m, method))

def process_payment_info(message, method):
    """معالجة معلومات الدفع"""
    user_id = message.from_user.id
    payment_info = message.text.strip()
    
    # Save payment request
    c.execute("INSERT INTO payment_requests (user_id, phone_number, amount, payment_method) VALUES (?, ?, ?, ?)",
             (user_id, payment_info, 2.0, method))
    
    # Send to admin channel for approval
    user_info = get_user_info(user_id)
    admin_msg = f"""
🆕 **طلب اشتراك جديد!**

👤 **المستخدم:** {user_info[0]}
🆔 **ID:** {user_id}
💰 **المبلغ:** 2$
💳 **الطريقة:** {method}
📱 **المعلومات:** {payment_info}
🔗 **كود الإحالة:** {generate_referral_code(user_id)}

👇 **اختر الإجراء:**
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_{user_id}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")
    )
    
    bot.send_message(ORDER_CHANNEL, admin_msg, reply_markup=markup)
    
    # Notify user
    bot.send_message(user_id, 
                    "✅ **تم استلام طلبك!**\n\n"
                    "📬 جاري مراجعة طلبك من قبل الإدارة...\n"
                    "⏳ ستصلك رسالة تأكيد خلال 24 ساعة.\n\n"
                    "شكراً لثقتك بنا! 🙏",
                    reply_markup=get_main_menu_markup('free'))

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def handle_admin_decision(call):
    """معالجة قرار الإدارة"""
    try:
        action, user_id = call.data.split("_")
        user_id = int(user_id)
        
        if action == "approve":
            # Upgrade user to paid
            c.execute("UPDATE users SET user_type = 'paid', has_purchased = 1 WHERE user_id = ?", (user_id,))
            
            # Send confirmation to user
            try:
                bot.send_message(user_id,
                               "🎉 **مبروك! تم تفعيل اشتراكك بنجاح!**\n\n"
                               "✅ **الآن يمكنك:**\n"
                               "• استخدام جميع الخدمات بدون قيود\n"
                               "• جني 0.10$ لكل إحالة جديدة\n"
                               "• الوصول للميزات المميزة\n\n"
                               "🔗 **شارك رابطك وابدأ الربح الآن!**\n"
                               f"`https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}`\n\n"
                               "🚀 **ابدأ باستخدام الخدمات من القائمة الرئيسية!**",
                               parse_mode='Markdown',
                               reply_markup=get_main_menu_markup('paid'))
            except Exception as e:
                logging.error(f"Message sending failed: {e}")
            
            bot.answer_callback_query(call.id, "تم قبول الطلب ✅")
        else:
            # Reject request
            try:
                bot.send_message(user_id,
                               "❌ **تم رفض طلبك**\n\n"
                               "يرجى التحقق من المعلومات والمحاولة مرة أخرى.\n"
                               "إذا كنت تعتقد أن هذا خطأ، تواصل مع الدعم.",
                               reply_markup=get_main_menu_markup('free'))
            except Exception as e:
                logging.error(f"Message sending failed: {e}")
            
            bot.answer_callback_query(call.id, "تم رفض الطلب ❌")
        
        # Update request status
        c.execute("UPDATE payment_requests SET status = ? WHERE user_id = ? AND status = 'pending'",
                 ('approved' if action == 'approve' else 'rejected', user_id))
        conn.commit()
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logging.error(f"Admin decision error: {e}")

# ==============================
# REELS MAKER - صانع الريلز الإسلامية
# ==============================
class IslamicReelsMaker:
    """صانع الريلز الإسلامية"""
    
    def __init__(self):
        self.user_sessions = {}
        self.VIDEO_DURATION = 17
        
    def handle_reels_request(self, message):
        """معالجة طلب صنع الريلز"""
        user_id = message.from_user.id
        
        if not can_use_service(user_id, 'reels'):
            bot.send_message(user_id,
                           "❌ **لقد استنفذت استخداماتك المجانية!**\n\n"
                           "🚀 **اشترك الآن للحصول على استخدام غير محدود!**\n"
                           "استخدم زر '🚀 شراء اشتراك' في القائمة الرئيسية.",
                           reply_markup=get_main_menu_markup('free'))
            return
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📤 رفع صورة", "📝 إضافة نص")
        markup.row("🎬 إنشاء ريلز", "💾 حفظ الكل")
        markup.row("🔙 القائمة الرئيسية")
        
        bot.send_message(user_id,
                       "🎬 **مرحباً بك في صانع الريلز الإسلامية!**\n\n"
                       "📌 **كيفية الاستخدام:**\n"
                       "1. ارفع صورة أو فيديو\n"
                       "2. أضف النص الإسلامي\n"
                       "3. أنشئ الريلز\n"
                       "4. احفظ النتيجة\n\n"
                       "👇 **اختر الإجراء:**",
                       reply_markup=markup)
    
    def handle_upload_photo(self, message):
        """معالجة رفع الصور"""
        user_id = message.from_user.id
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {'photos': [], 'texts': [], 'processed': []}
        
        bot.send_message(user_id,
                       "📤 **ارفع صورة الآن:**\n"
                       "يمكنك رفع عدة صور واحدة تلو الأخرى.\n"
                       "عند الانتهاء، اضغط '📝 إضافة نص'")
    
    def handle_add_text(self, message):
        """معالجة إضافة النصوص"""
        user_id = message.from_user.id
        
        if user_id not in self.user_sessions or not self.user_sessions[user_id]['photos']:
            bot.send_message(user_id,
                           "❌ **الرجاء رفع صورة أولاً!**",
                           reply_markup=get_services_markup())
            return
        
        bot.send_message(user_id,
                       "📝 **أرسل النص الإسلامي الآن:**\n"
                       "يمكنك إرسال عدة نصوص (كل نص في سطر)\n"
                       "مثال:\n"
                       "سُبْحَانَ اللَّهِ\n"
                       "الْحَمْدُ لِلَّهِ\n"
                       "اللَّهُ أَكْبَرُ")
        
        bot.register_next_step_handler(message, self.process_texts)
    
    def process_texts(self, message):
        """معالجة النصوص"""
        user_id = message.from_user.id
        
        if user_id not in self.user_sessions:
            return
        
        texts = [t.strip() for t in message.text.split('\n') if t.strip()]
        self.user_sessions[user_id]['texts'] = texts
        
        # Log service usage
        log_service_usage(user_id, 'reels')
        
        bot.send_message(user_id,
                       f"✅ **تم حفظ {len(texts)} نص!**\n\n"
                       f"📷 الصور: {len(self.user_sessions[user_id]['photos'])}\n"
                       f"📝 النصوص: {len(texts)}\n\n"
                       "🎬 **اضغط 'إنشاء ريلز' لبدء الصنع!**",
                       reply_markup=self.get_reels_markup())
    
    def get_reels_markup(self):
        """لوحة صانع الريلز"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🎬 إنشاء ريلز", "💾 حفظ الكل")
        markup.row("🔄 بدء من جديد", "🔙 القائمة الرئيسية")
        return markup
    
    def create_reels(self, message):
        """إنشاء الريلز"""
        user_id = message.from_user.id
        
        if user_id not in self.user_sessions:
            bot.send_message(user_id, "❌ لم تقم بتحميل أي بيانات!", reply_markup=get_services_markup())
            return
        
        session = self.user_sessions[user_id]
        
        if not session['photos'] or not session['texts']:
            bot.send_message(user_id, "❌ تحتاج إلى صور ونصوص!", reply_markup=get_services_markup())
            return
        
        bot.send_message(user_id, "⏳ **جاري إنشاء الريلز...**\nقد يستغرق ذلك دقيقة...")
        
        # Create reels (simplified version - in production add actual image processing)
        try:
            # Create sample reel
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            
            # Create a simple image with text
            img = Image.new('RGB', (1080, 1350), color=(30, 60, 90))
            draw = ImageDraw.Draw(img)
            
            # Add Arabic text
            if session['texts']:
                text = session['texts'][0]
                arabic_text = arabic_reshaper.reshape(text)
                bidi_text = get_display(arabic_text)
                
                # Try to use font
                try:
                    font = ImageFont.truetype("fonts/arial.ttf", 60)
                except:
                    font = ImageFont.load_default()
                
                draw.text((540, 675), bidi_text, font=font, fill=(255, 255, 255), anchor="mm")
            
            img.save(temp_file.name, quality=95)
            
            # Send to user
            with open(temp_file.name, 'rb') as f:
                bot.send_photo(user_id, f,
                             caption="🎬 **ريلك الإسلامي الأول**\n"
                                     "✅ تم الإنشاء بنجاح!\n\n"
                                     "💾 يمكنك حفظه أو مشاركته مباشرة!")
            
            # Clean up
            os.unlink(temp_file.name)
            
            session['processed'].append(temp_file.name)
            
            bot.send_message(user_id,
                           "✅ **تم إنشاء الريلز بنجاح!**\n\n"
                           "🎬 **لإنشاء المزيد:**\n"
                           "1. أضف صور/نصوص جديدة\n"
                           "2. اضغط 'إنشاء ريلز' مرة أخرى\n\n"
                           "💾 **لحفظ الكل:** استخدم زر '💾 حفظ الكل'",
                           reply_markup=self.get_reels_markup())
            
        except Exception as e:
            logging.error(f"Reel creation error: {e}")
            bot.send_message(user_id, "❌ حدث خطأ أثناء الإنشاء!", reply_markup=get_services_markup())

# ==============================
# VIDEO DOWNLOADER - محمل الفيديوهات
# ==============================
class VideoDownloader:
    """محمل الفيديوهات"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        self.downloading_users = {}
    
    def handle_download_request(self, message):
        """معالجة طلب التحميل"""
        user_id = message.from_user.id
        
        if not can_use_service(user_id, 'download'):
            bot.send_message(user_id,
                           "❌ **لقد استنفذت استخداماتك المجانية!**\n\n"
                           "🚀 **اشترك الآن للحصول على تحميل غير محدود!**\n"
                           "استخدم زر '🚀 شراء اشتراك' في القائمة الرئيسية.",
                           reply_markup=get_main_menu_markup('free'))
            return
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("📥 يوتيوب", "📥 انستغرام", "📥 تيك توك")
        markup.row("📚 تحميل جماعي", "🔙 القائمة الرئيسية")
        
        bot.send_message(user_id,
                       "📥 **أهلاً بك في محمل الفيديوهات!**\n\n"
                       "✨ **المدعومة:**\n"
                       "• YouTube\n• Instagram\n• TikTok\n• Facebook\n"
                       "• Twitter/X\n• Reddit\n• والمزيد!\n\n"
                       "👇 **اختر المنصة أو أرسل الرابط مباشرة:**",
                       reply_markup=markup)
    
    def process_video_url(self, message):
        """معالجة رابط الفيديو"""
        user_id = message.from_user.id
        url = message.text.strip()
        
        # Check if it's a valid URL
        if not re.match(r'https?://\S+', url):
            bot.send_message(user_id, "❌ رابط غير صحيح!", reply_markup=get_services_markup())
            return
        
        # Check if supported platform
        supported = any(domain in url.lower() for domain in SUPPORTED_DOMAINS)
        if not supported:
            bot.send_message(user_id,
                           "❌ **المنصة غير مدعومة حالياً!**\n\n"
                           "📋 **المدعومة:**\n"
                           "YouTube, Instagram, TikTok, Facebook,\n"
                           "Twitter/X, Reddit, Pinterest, Vimeo",
                           reply_markup=get_services_markup())
            return
        
        # Log service usage
        log_service_usage(user_id, 'download')
        
        bot.send_message(user_id, "🔍 **جاري تحليل الرابط...**")
        
        # Download in background
        Thread(target=self.download_video, args=(user_id, url)).start()
    
    def download_video(self, user_id, url):
        """تحميل الفيديو"""
        try:
            self.downloading_users[user_id] = True
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Check file size
                file_size = os.path.getsize(filename)
                if file_size > 50 * 1024 * 1024:  # 50MB limit for Telegram
                    bot.send_message(user_id,
                                   f"📁 **الفيديو كبير جداً ({file_size//1024//1024}MB)**\n"
                                   "تليجرام لا يسمح برفع ملفات أكبر من 50MB\n\n"
                                   "💡 **يمكنك:**\n"
                                   "1. استخدام خدمة أخرى\n"
                                   "2. تحميل فيديو أقصر\n"
                                   "3. الاتصال بالدعم للحصول على حل")
                    os.remove(filename)
                    return
                
                # Send to user
                with open(filename, 'rb') as f:
                    bot.send_video(user_id, f,
                                 caption=f"✅ **تم التحميل بنجاح!**\n\n"
                                         f"🎬 **{info.get('title', 'فيديو')}**\n"
                                         f"⏱️ المدة: {info.get('duration', 0)} ثانية\n"
                                         f"📦 الحجم: {file_size//1024//1024}MB")
                
                # Clean up
                os.remove(filename)
                
                # Save download history
                c.execute("INSERT INTO download_history (user_id, url, platform) VALUES (?, ?, ?)",
                         (user_id, url, self.get_platform(url)))
                conn.commit()
                
        except Exception as e:
            logging.error(f"Download error: {e}")
            bot.send_message(user_id, f"❌ **حدث خطأ أثناء التحميل!**\n{str(e)[:100]}...")
        
        finally:
            if user_id in self.downloading_users:
                del self.downloading_users[user_id]
    
    def get_platform(self, url):
        """التعرف على المنصة"""
        url_lower = url.lower()
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'instagram.com' in url_lower or 'instagr.am' in url_lower:
            return 'instagram'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        return 'other'

# ==============================
# INITIALIZE SERVICES - تهيئة الخدمات
# ==============================
reels_maker = IslamicReelsMaker()
video_downloader = VideoDownloader()

# ==============================
# MESSAGE HANDLERS - معالجات الرسائل
# ==============================
@bot.message_handler(func=lambda message: message.text in ["🎬 صنع الريلز الإسلامية", "🎬 صنع ريلز إسلامية"])
def handle_reels_service(message):
    """خدمة صنع الريلز"""
    reels_maker.handle_reels_request(message)

@bot.message_handler(func=lambda message: message.text in ["📥 تحميل الفيديوهات", "📥 تحميل فيديو"])
def handle_download_service(message):
    """خدمة تحميل الفيديوهات"""
    video_downloader.handle_download_request(message)

@bot.message_handler(func=lambda message: message.text == "📤 رفع صورة")
def handle_upload_photo(message):
    """رفع صورة للريلز"""
    reels_maker.handle_upload_photo(message)

@bot.message_handler(func=lambda message: message.text == "📝 إضافة نص")
def handle_add_text(message):
    """إضافة نص للريلز"""
    reels_maker.handle_add_text(message)

@bot.message_handler(func=lambda message: message.text == "🎬 إنشاء ريلز")
def handle_create_reels(message):
    """إنشاء الريلز"""
    reels_maker.create_reels(message)

@bot.message_handler(func=lambda message: message.text in ["📥 يوتيوب", "📥 انستغرام", "📥 تيك توك"])
def handle_platform_selection(message):
    """اختيار المنصة"""
    platform = message.text.replace("📥 ", "")
    bot.send_message(message.chat.id,
                   f"📥 **أرسل رابط {platform} الآن:**\n"
                   "انسخ الرابط وأرسله هنا مباشرة...",
                   reply_markup=types.ReplyKeyboardRemove())
    
    bot.register_next_step_handler(message, video_downloader.process_video_url)

@bot.message_handler(func=lambda message: re.match(r'https?://\S+', message.text))
def handle_direct_url(message):
    """معالجة الرابط المباشر"""
    video_downloader.process_video_url(message)

@bot.message_handler(func=lambda message: message.text == "💰 سحب الأرباح")
def handle_withdraw(message):
    """سحب الأرباح"""
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    if balance < 2.0:
        bot.send_message(user_id,
                       f"❌ **الحد الأدنى للسحب هو 2$**\n\n"
                       f"💰 رصيدك الحالي: {balance:.2f}$\n\n"
                       f"📈 **لزيادة رصيدك:**\n"
                       f"1. انشر رابط إحالتك\n"
                       f"2. احصل على 0.10$ لكل مشترك جديد\n"
                       f"3. استخدم الخدمات المميزة\n\n"
                       f"🔗 **رابط إحالتك:**\n"
                       f"`https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}`",
                       parse_mode='Markdown',
                       reply_markup=get_main_menu_markup(get_user_info(user_id)[1]))
        return
    
    # Generate verification code
    withdraw_code = get_withdraw_code(user_id)
    
    bot.send_message(user_id,
                   f"📤 **لسحب الأرباح:**\n\n"
                   f"🔐 **كود التحقق:** `{withdraw_code}`\n\n"
                   f"💰 **المبلغ:** {balance:.2f}$\n\n"
                   f"📝 **أرسل كود التحقق لتأكيد السحب:**",
                   parse_mode='Markdown',
                   reply_markup=types.ReplyKeyboardRemove())
    
    bot.register_next_step_handler(message, verify_withdraw_code)

def verify_withdraw_code(message):
    """تأكيد كود السحب"""
    user_id = message.from_user.id
    correct_code = get_withdraw_code(user_id)
    user_input = message.text.strip()
    
    if user_input == correct_code:
        # Generate new code
        new_code = generate_withdraw_code(user_id)
        c.execute("UPDATE users SET withdraw_code = ? WHERE user_id = ?", (new_code, user_id))
        
        bot.send_message(user_id,
                       "✅ **تم التحقق بنجاح!**\n\n"
                       "💰 **اختر طريقة السحب:**",
                       reply_markup=get_withdraw_methods_markup())
    else:
        bot.send_message(user_id,
                       "❌ **كود التحقق غير صحيح!**\n\n"
                       "الرجاء المحاولة مرة أخرى.",
                       reply_markup=get_main_menu_markup(get_user_info(user_id)[1]))

@bot.message_handler(func=lambda message: message.text in ["💳 زين العراق", "💳 آسيا سيل", "💳 باي بال", "💳 كريبتو", "💳 ويسترن يونيون"])
def handle_withdraw_method(message):
    """طريقة السحب"""
    user_id = message.from_user.id
    method = message.text.replace("💳 ", "")
    balance = get_user_balance(user_id)
    
    bot.send_message(user_id,
                   f"📤 **طريقة السحب:** {method}\n\n"
                   f"💰 **المبلغ:** {balance:.2f}$\n\n"
                   f"📝 **أرسل معلومات {method} (رقم هاتف/حساب):**",
                   reply_markup=types.ReplyKeyboardRemove())
    
    bot.register_next_step_handler(message, lambda m: process_withdraw_details(m, method, balance))

def process_withdraw_details(message, method, amount):
    """معالجة تفاصيل السحب"""
    user_id = message.from_user.id
    account_info = message.text.strip()
    
    # Register withdrawal request
    c.execute("INSERT INTO withdrawal_requests (user_id, amount, method, account_info) VALUES (?, ?, ?, ?)",
             (user_id, amount, method, account_info))
    
    # Deduct from balance
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    
    # Generate new withdraw code
    new_code = generate_withdraw_code(user_id)
    c.execute("UPDATE users SET withdraw_code = ? WHERE user_id = ?", (new_code, user_id))
    
    # Send to admin
    user_info = get_user_info(user_id)
    admin_msg = f"""
📌 **طلب سحب جديد!**

👤 **المستخدم:** {user_info[0]}
🆔 **ID:** {user_id}
💰 **المبلغ:** {amount:.2f}$
💳 **الطريقة:** {method}
📱 **المعلومات:** {account_info}
🔐 **كود التحقق:** {new_code}
    """
    
    bot.send_message(ORDER_CHANNEL, admin_msg)
    
    # Notify user
    bot.send_message(user_id,
                   "✅ **تم استلام طلب السحب!**\n\n"
                   "⏳ **جاري المعالجة خلال 24-48 ساعة**\n"
                   "📬 **سيتم إعلامك عند الانتهاء**\n\n"
                   "شكراً لاستخدامك خدماتنا! 🙏",
                   reply_markup=get_main_menu_markup(get_user_info(user_id)[1]))
    
    conn.commit()

@bot.message_handler(func=lambda message: message.text == "📊 إحصائياتي")
def handle_stats(message):
    """إحصائيات المستخدم"""
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    name, user_type, balance = user_info
    total_refs, active_refs = get_referral_stats(user_id)
    
    c.execute("SELECT joined_date FROM users WHERE user_id = ?", (user_id,))
    join_date = c.fetchone()[0][:10] if c.fetchone() else "غير معروف"
    
    stats_text = f"""
📊 **إحصائيات حسابك:**

👤 **الاسم:** {name}
🎯 **النوع:** {'🆓 مجاني' if user_type == 'free' else '⭐ مميز' if user_type == 'paid' else '👑 وكيل'}
💰 **الرصيد:** {balance:.2f}$

📈 **الإحالات:**
👥 **الإجمالي:** {total_refs}
✅ **النشطة:** {active_refs}
💵 **الأرباح:** {active_refs * 0.10:.2f}$

📅 **تاريخ الانضمام:** {join_date}
🔗 **حالة الحساب:** {'✅ نشط' if user_type != 'free' else '🆓 مجاني'}

🔗 **رابط الإحالة:**
`https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}`

📌 **شارك الرابط واكسب 0.10$ لكل إحالة!**
    """
    
    bot.send_message(user_id, stats_text, 
                     parse_mode='Markdown',
                     reply_markup=get_main_menu_markup(user_type))

@bot.message_handler(func=lambda message: message.text in ["👥 الإحالات", "👥 فريق الإحالات"])
def handle_referrals(message):
    """عرض الإحالات"""
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    user_type = user_info[1]
    
    total_refs, active_refs = get_referral_stats(user_id)
    earnings = active_refs * 0.10
    
    referrals_text = f"""
👥 **نظام الإحالات والأرباح**

💰 **سعر الإحالة:** 0.10$ لكل مشترك جديد
👤 **إحالاتك:** {active_refs} نشطة من {total_refs}
💵 **أرباحك:** {earnings:.2f}$

🎯 **كيفية الربح:**
1. شارك رابط إحالتك
2. كل شخص يسجل عبر رابطك
3. تحصل على 0.10$ تلقائياً
4. اسحب أموالك عند وصولها لـ2$

🔗 **رابط إحالتك:**
`https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}`

📌 **نصائح للترويج:**
• شارك في مجموعات التليجرام
• انشر على وسائل التواصل
• شارك مع الأصدقاء والمعارف
• استخدم وسوم جذابة

🚀 **ابدأ الربح الآن!**
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 مشاركة الرابط", 
                                          url=f"https://t.me/share/url?url=https://t.me/{bot.get_me().username}?start={generate_referral_code(user_id)}&text=انضم%20إلى%20بوت%20الربح%20من%20الإنترنت%20واحصل%20على%200.10$%20لكل%20إحالة!%20🚀"))
    
    bot.send_message(user_id, referrals_text,
                     parse_mode='Markdown',
                     reply_markup=markup)
    
    bot.send_message(user_id,
                     "👇 **استخدم الأزرار أدناه للعودة:**",
                     reply_markup=get_main_menu_markup(user_type))

@bot.message_handler(func=lambda message: message.text == "🆓 خدمات مجانية")
def handle_free_services(message):
    """الخدمات المجانية"""
    user_id = message.from_user.id
    
    free_services_text = """
🆓 **الخدمات المجانية المتاحة:**

1️⃣ **صنع الريلز الإسلامية:**
   • 3 ريلز مجانية
   • إضافة نصوص عربية/إنجليزية
   • خلفيات إسلامية

2️⃣ **تحميل الفيديوهات:**
   • 3 تحميلات مجانية
   • من جميع المنصات
   • جودة عالية

3️⃣ **نظام الإحالات:**
   • ربح 0.10$ لكل إحالة
   • متاح للجميع
   • سحب عند 2$

🚀 **لرفع القيود:**
اشترك بمبلغ 2$ فقط واحصل على:
• استخدام غير محدود
• ميزات متقدمة
• دعم فني مميز

💰 **استخدم زر '🚀 شراء اشتراك'**
    """
    
    bot.send_message(user_id, free_services_text,
                     reply_markup=get_main_menu_markup(get_user_info(user_id)[1]))

@bot.message_handler(func=lambda message: message.text == "🆘 المساعدة")
def handle_help(message):
    """المساعدة"""
    user_id = message.from_user.id
    
    help_text = """
🆘 **مركز المساعدة**

❓ **كيفية الاستخدام:**
1. انضم للقنوات المطلوبة
2. استخدم الخدمات من القائمة
3. انشر رابط إحالتك للربح
4. اسحب أموالك عند 2$

💰 **نظام الإحالات:**
• احصل على 0.10$ لكل مشترك جديد
• المبلغ يضاف تلقائياً لرصيدك
• الحد الأدنى للسحب: 2$

🎬 **صنع الريلز:**
1. ارفع صور/فيديوهات
2. أضف النصوص الإسلامية
3. أنشئ الريلز
4. احفظ النتائج

📥 **تحميل الفيديوهات:**
• أرسل رابط الفيديو
• اختر الجودة المطلوبة
• احصل على الفيديو مباشرة

💳 **المدفوعات:**
• الدفع: 2$ للاشتراك المميز
• السحب: متاح بعد جمع 2$
• الطرق: زين، آسيا سيل، كريبتو

📞 **الدعم الفني:**
@intorders (قناة الطلبات)
    """
    
    bot.send_message(user_id, help_text,
                     reply_markup=get_main_menu_markup(get_user_info(user_id)[1]))

@bot.message_handler(func=lambda message: message.text == "🔙 القائمة الرئيسية")
def handle_back_to_main(message):
    """العودة للقائمة الرئيسية"""
    user_id = message.from_user.id
    user_info = get_user_info(user_id)
    show_welcome_message(message)

# ==============================
# FLASK ROUTES - مسارات فلاسك
# ==============================
@app.route('/' + TOKEN, methods=['POST'])
def bot_webhook():
    """ويبهوك البوت"""
    try:
        json_data = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "Error", 500

@app.route('/')
def set_webhook():
    """إعداد الويبهوك"""
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f'https://invite2earnn-h0v1.onrender.com/{TOKEN}'
        bot.set_webhook(url=webhook_url)
        return "✅ Webhook setup successfully!", 200
    except Exception as e:
        logging.error(f"Webhook setup error: {e}")
        return "❌ Webhook setup failed", 500

# ==============================
# KEEP ALIVE - إبقاء البوت نشط
# ==============================
import threading

def keep_alive():
    """إبقاء البوت نشط"""
    while True:
        try:
            requests.get(f'https://invite2earnn-h0v1.onrender.com/')
            print(f"✅ Ping at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Ping failed: {e}")
        time.sleep(300)  # كل 5 دقائق

# ==============================
# MAIN - التشغيل الرئيسي
# ==============================
if __name__ == '__main__':
    # إنشاء مجلد التحميلات
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    # بدء إبقاء البوت نشط
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    print("=" * 50)
    print("🚀 **بوت الربح من الإنترنت يعمل الآن!**")
    print("💰 **نظام الإحالات: 0.10$ لكل مشترك**")
    print("🎬 **صنع الريلز الإسلامية**")
    print("📥 **تحميل الفيديوهات من جميع المنصات**")
    print("👑 **التحكم من خلال القناة: @intorders**")
    print("=" * 50)
    
    try:
        # تشغيل البوت
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f'https://invite2earnn-h0v1.onrender.com/{TOKEN}'
        bot.set_webhook(url=webhook_url)
        
        # تشغيل تطبيق فلاسك
        app.run(host="0.0.0.0", port=5000, debug=False)
        
    except Exception as e:
        logging.error(f"Main error: {e}")
        print(f"❌ Error: {e}")
