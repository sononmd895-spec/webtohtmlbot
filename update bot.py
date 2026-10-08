import re
import html
import aiohttp
import asyncio
import sqlite3
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from bs4 import BeautifulSoup

# ==========================================
# 🛠️ কনফিগারেশন
# ==========================================
BOT_TOKEN = "8868220230:AAFmlM2IhkZz-oHQB3VarBEYB5_8p2revc4"
ADMIN_ID = 6953927815

# ==========================================
# ✨ প্রিমিয়াম ইমোজি ম্যাপিং
# ==========================================
PREMIUM_EMOJIS = {
    "success": "4956719506027185156",
    "file": "4956721670690702265",
    "stats": "6138646462382216591",
    "warning": "6053056504431387487",
    "admin": "4956611513369494230",
    "link": "6138559798532118897",
    "shield": "5327975757538929455",
    "broadcast": "6338964016240530893",
    "lock": "6084484519597969993",
    "pin": "4956552088201986883",
    "point_down": "6084728177387639178",
    "sparkle": "5323336750477616586",
    "globe": "5296369303661067030",
    "earth": "5253742260054409879",
    "gear": "5224736245665511429",
    "hourglass": "4956560549287560231",
    "check": "6269255258212404947",
    "folder": "6260264603171689263",
    "box": "4958479549265347295",
    "python": "5224736245665511429"
}

# ==========================================
# 📦 ডাটাবেজ সেটআপ
# ==========================================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, joined_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, url TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def log_usage(user_id, url):
    conn = sqlite3.connect("bot_database.db")
    c = conn.cursor()
    c.execute("INSERT INTO usage (user_id, url, timestamp) VALUES (?, ?, ?)",
              (user_id, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

admin_states = {}

# ==========================================
# 🛡️ কোর ডিকোডিং ইঞ্জিন
# ==========================================
def remove_obfuscation(html_text: str) -> str:
    try:
        decoded_html = re.sub(
            r'\\x([0-9A-Fa-f]{2})',
            lambda m: chr(int(m.group(1), 16)),
            html_text
        )
        decoded_html = re.sub(
            r'\\u([0-9A-Fa-f]{4})',
            lambda m: chr(int(m.group(1), 16)),
            decoded_html
        )
        decoded_html = re.sub(
            r'base64,([A-Za-z0-9+/=]+)',
            lambda m: 'base64,' + m.group(1),
            decoded_html
        )
        eval_match = re.search(r'eval\(["\'](.+?)["\']\)', decoded_html, re.DOTALL)
        if eval_match:
            inner_code = eval_match.group(1)
            decoded_html = inner_code

        soup = BeautifulSoup(decoded_html, 'html.parser')
        return soup.prettify()
    except Exception as e:
        return f"❌ Failed to decode: {str(e)}"

async def fetch_and_decode(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return f"❌ Website unreachable: Status code {response.status}"
                raw_html = await response.text()
                return remove_obfuscation(raw_html)
    except asyncio.TimeoutError:
        return "❌ Timeout: Website is responding too slowly."
    except Exception as e:
        return f"❌ Fetch error: {str(e)}"

# ==========================================
# ⌨️ রিপ্লে কীবোর্ড (🎨 COLORED BUTTONS)
# ==========================================
def get_main_keyboard(is_admin=False, broadcast_mode=False):
    keyboard = [
        [
            KeyboardButton("🔗 URL to HTML", style="primary"),   # 🔵 Blue
            KeyboardButton("📊 Stats", style="success"),          # 🟢 Green
        ]
    ]
    if broadcast_mode:
        keyboard.append([
            KeyboardButton("❌ Cancel Broadcast", style="danger")  # 🔴 Red
        ])
    elif is_admin:
        keyboard.append([
            KeyboardButton("👥 Admin Panel", style="primary"),      # 🔵 Blue
            KeyboardButton("📢 Send Broadcast", style="success"),   # 🟢 Green
        ])
    # BOT OWNER বাটন সব সময় থাকবে
    keyboard.append([
        KeyboardButton("👑 BOT OWNER", style="danger")            # 🔴 Red
    ])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==========================================
# 📨 হ্যান্ডলারসমূহ
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    is_admin = (user.id == int(ADMIN_ID))

    welcome_text = (
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👋</tg-emoji> <b>Welcome, {user.first_name}!</b>\n\n"
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">⚡</tg-emoji> <b>I extract any website URL into clean HTML source code.</b>\n\n"
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['lock']}\">🔒</tg-emoji> <b>Advanced extraction – clean, readable HTML in seconds.</b>\n\n"
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['pin']}\">📌</tg-emoji> <b>Click the</b> <b>🔗 URL to HTML</b> <b>button to start!</b>"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(is_admin, False)
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    is_admin = (user.id == int(ADMIN_ID))

    if text == "🔗 URL to HTML":
        await update.message.reply_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['globe']}\">🌐</tg-emoji> <b>URL TO HTML BOT</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['sparkle']}\">✨</tg-emoji> <b>FEATURES:</b>\n"
            f"• <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['earth']}\">🌍</tg-emoji> <b>Fast URL Fetch</b>\n"
            f"• <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['folder']}\">📄</tg-emoji> <b>Clean HTML Export</b>\n"
            f"• <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">⚡</tg-emoji> <b>Instant Processing</b>\n"
            f"• <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['lock']}\">🔒</tg-emoji> <b>Secure Extraction</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['pin']}\">📌</tg-emoji> <b>SEND A WEBSITE URL TO START!</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['link']}\">🔗</tg-emoji> <b>Example:</b>\n<code>https://example.com</code>",
            parse_mode="HTML"
        )

    elif text == "📊 Stats":
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM usage")
        total_usage = c.fetchone()[0]
        conn.close()

        stats_text = (
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['stats']}\">📊</tg-emoji> <b>BOT STATISTICS</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👥</tg-emoji> <b>Total Users:</b> <code>{total_users}</code>\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['link']}\">🔄</tg-emoji> <b>Total Usage:</b> <code>{total_usage}</code>"
        )
        await update.message.reply_text(stats_text, parse_mode="HTML")

    elif text == "👥 Admin Panel":
        if not is_admin:
            await update.message.reply_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">⛔</tg-emoji> <b>Access Denied!</b>",
                parse_mode="HTML"
            )
            return

        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM usage")
        total_usage = c.fetchone()[0]
        c.execute("""SELECT u.username, u.first_name, COUNT(us.id) as usage_count 
                     FROM usage us JOIN users u ON us.user_id = u.user_id 
                     GROUP BY us.user_id ORDER BY usage_count DESC LIMIT 10""")
        top_users = c.fetchall()
        conn.close()

        user_list = ""
        for idx, (username, first_name, count) in enumerate(top_users, 1):
            display = f"@{username}" if username else first_name
            user_list += f"\n#{idx} <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👤</tg-emoji> {display} — <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['folder']}\">📁</tg-emoji> {count} files"

        admin_text = (
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👥</tg-emoji> <b>ADMIN PANEL</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['stats']}\">📊</tg-emoji> <b>Total Users:</b> <code>{total_users}</code>\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['link']}\">🔄</tg-emoji> <b>Total Usage:</b> <code>{total_usage}</code>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">🏆</tg-emoji> <b>Top Users:</b>\n{user_list}"
        )
        await update.message.reply_text(admin_text, parse_mode="HTML")

    elif text == "📢 Send Broadcast":
        if not is_admin:
            await update.message.reply_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">⛔</tg-emoji> <b>Access Denied!</b>",
                parse_mode="HTML"
            )
            return

        admin_states[user.id] = "WAITING_FOR_BROADCAST"
        await update.message.reply_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['broadcast']}\">📢</tg-emoji> <b>Broadcast Mode Activated</b>\n\nSend the message to broadcast.\nTo cancel, click '❌ Cancel Broadcast'.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(is_admin, True)
        )

    elif text == "❌ Cancel Broadcast":
        if admin_states.get(user.id) == "WAITING_FOR_BROADCAST":
            admin_states.pop(user.id, None)
            await update.message.reply_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">❌</tg-emoji> <b>Broadcast Cancelled.</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard(is_admin, False)
            )
        else:
            await update.message.reply_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">ℹ️</tg-emoji> <b>No active broadcast.</b>",
                parse_mode="HTML"
            )

    elif text == "👑 BOT OWNER":
        owner_info = (
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👑</tg-emoji> <b>BOT OWNER</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['admin']}\">👤</tg-emoji> <b>Name:</b> SIYAM BHAI\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['link']}\">🔗</tg-emoji> <b>Username:</b> @SIYAM_BHAI_OWNER\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">🛡️</tg-emoji> <b>Role:</b> Developer & Administrator\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">✅</tg-emoji> <b>Status:</b> Active\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['sparkle']}\">✨</tg-emoji> <i>For any queries or support, feel free to contact.</i>"
        )
        await update.message.reply_text(owner_info, parse_mode="HTML")

# ==========================================
# 🌐 ইউআরএল ও ব্রডকাস্ট হ্যান্ডলার
# ==========================================
async def handle_url_or_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = (user.id == int(ADMIN_ID))

    # --- Broadcast Mode ---
    if admin_states.get(user.id) == "WAITING_FOR_BROADCAST":
        if update.message.text == "/cancel":
            admin_states.pop(user.id, None)
            await update.message.reply_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">❌</tg-emoji> <b>Cancelled.</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard(is_admin, False)
            )
            return

        admin_states.pop(user.id, None)
        status_msg = await update.message.reply_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['hourglass']}\">⏳</tg-emoji> <b>Broadcasting...</b>",
            parse_mode="HTML"
        )

        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()

        success, failed = 0, 0
        for (u_id,) in users:
            try:
                await context.bot.copy_message(chat_id=u_id, from_chat_id=user.id, message_id=update.message.message_id)
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1

        await status_msg.edit_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">✅</tg-emoji> <b>Broadcast Complete!</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['check']}\">🟢</tg-emoji> Sent: <code>{success}</code>\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">🔴</tg-emoji> Failed: <code>{failed}</code>",
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">✅</tg-emoji> <b>Done.</b>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(is_admin, False)
        )
        return

    # --- URL Decoding ---
    url = update.message.text.strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">❌</tg-emoji> <b>Invalid URL!</b> Include <code>http://</code> or <code>https://</code>",
            parse_mode="HTML"
        )
        return

    add_user(user.id, user.username, user.first_name)
    log_usage(user.id, url)

    processing_msg = await update.message.reply_text(
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['hourglass']}\">⏳</tg-emoji> <b>Connecting...</b>",
        parse_mode="HTML"
    )
    await asyncio.sleep(0.5)
    await processing_msg.edit_text(
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">🛡️</tg-emoji> <b>Bypassing protection...</b>",
        parse_mode="HTML"
    )
    await asyncio.sleep(0.5)
    await processing_msg.edit_text(
        f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['gear']}\">⚙️</tg-emoji> <b>Extracting & cleaning...</b>",
        parse_mode="HTML"
    )

    try:
        decoded_html = await fetch_and_decode(url)
        if decoded_html.startswith("❌"):
            await processing_msg.edit_text(
                f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">⚠️</tg-emoji> <b>Failed:</b>\n{decoded_html}",
                parse_mode="HTML"
            )
            return

        file_name = f"source_code_{user.id}.html"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(decoded_html)

        caption = (
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">✅</tg-emoji> <b>HTML EXTRACTION COMPLETE!</b>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['folder']}\">📁</tg-emoji> <b>File Name:</b>\n<code>Sʜᴀᴅᴏᴡ × Sɪʏᴀᴍ_.html</code>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['box']}\">📦</tg-emoji> <b>Size:</b>\n<code>{os.path.getsize(file_name) / 1024:.1f} KB</code>\n\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">⚡</tg-emoji> <b>Extracted Features:</b>\n"
            f"  • <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['earth']}\">🌍</tg-emoji> <b>Live URL Fetch</b>\n"
            f"  • <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['folder']}\">📄</tg-emoji> <b>Clean HTML Export</b>\n"
            f"  • <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">⚡</tg-emoji> <b>Fast Processing</b>\n"
            f"  • <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['lock']}\">🔒</tg-emoji> <b>Secure Extraction</b>\n"
            f"  • <tg-emoji emoji-id=\"{PREMIUM_EMOJIS['shield']}\">🛡️</tg-emoji> <b>Anti‑Decode System</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['success']}\">✅</tg-emoji> <b>Your HTML file is ready!</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        with open(file_name, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="Sʜᴀᴅᴏᴡ ×.html",
                caption=caption,
                parse_mode="HTML"
            )

        await processing_msg.delete()
        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        await processing_msg.edit_text(
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJIS['warning']}\">❌</tg-emoji> <b>Error:</b>\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )

# ==========================================
# 🚀 মেইন ফাংশন
# ==========================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.Regex('^(🔗 URL to HTML|📊 Stats|👥 Admin Panel|📢 Send Broadcast|❌ Cancel Broadcast|👑 BOT OWNER)$'),
        handle_buttons
    ))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_url_or_broadcast))

    print("🤖 Premium Bot is RUNNING (Only Reply Keyboard + BOT OWNER button)!")
    app.run_polling()

if __name__ == "__main__":
    main()