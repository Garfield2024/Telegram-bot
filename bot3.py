# -*- coding: utf-8 -*-
import sqlite3
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ====== تنظیمات شما ======
OWNER_ID = 7070881772
CHANNEL_ID = -1002043139652          # آیدی عددی کانال
CHANNEL_USERNAME = "confing_gari"    # بدون @
BOT_USERNAME = "Config_gari_bot"     # یوزرنیم ربات بدون @
BOT_TOKEN = "7898102329:AAEVWHVhYLQcakjq4oOt9JLjcqnPOxsfIHQ"
# =========================

# --- اتصال دیتابیس و جدول‌ها ---
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  ref_by INTEGER,
  blocked INTEGER DEFAULT 0,
  free_pass INTEGER DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS configs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT
)
""")
conn.commit()

# مهاجرت دفاعی (اگر قبلاً جدول قدیمی ساختی)
def ensure_column(table, col, coldef):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
        conn.commit()

ensure_column("users", "blocked", "INTEGER DEFAULT 0")
ensure_column("users", "free_pass", "INTEGER DEFAULT 0")


# ---------- کمک‌تابع‌ها ----------
def kb_main(user_id: int) -> InlineKeyboardMarkup:
    # منوی اصلی؛ مالک 10 دکمه می‌بیند، کاربر فقط دکمه‌های کاربری
    rows = [
        [InlineKeyboardButton("📩 دریافت کانفیگ", callback_data="get_config")],
        [InlineKeyboardButton("📊 آمار زیرمجموعه‌ها", callback_data="stats")],
        [InlineKeyboardButton("📎 لینک زیرمجموعه‌گیری", callback_data="ref_link")],
        [InlineKeyboardButton("✉ پیام به پشتیبانی", callback_data="support")],
        [InlineKeyboardButton("ℹ️ کانال اجباری", callback_data="force_channel")],
    ]
    if user_id == OWNER_ID:
        rows += [
            [InlineKeyboardButton("⚒ مدیریت کانفیگ", callback_data="manage_config")],
            [InlineKeyboardButton("📢 ارسال پیام عمومی", callback_data="broadcast")],
            [InlineKeyboardButton("🔒 بلاک کاربر", callback_data="block_user")],
            [InlineKeyboardButton("🔓 آزادسازی کاربر", callback_data="unblock_user")],
            [InlineKeyboardButton("🎫 معافیت کاربر", callback_data="freepass_user")],
        ]
    return InlineKeyboardMarkup(rows)

def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩ بازگشت", callback_data="back_to_main")]])

async def send_or_edit(to, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    # برای اینکه هم در start (message) و هم در دکمه‌ها (query) راحت رندر کنیم
    if hasattr(to, "message") and to.message:
        await to.message.reply_text(text, reply_markup=reply_markup)
    else:
        await to.edit_message_text(text, reply_markup=reply_markup)

async def show_main_menu(target, user_id: int):
    await send_or_edit(target, "📍 منوی اصلی:", kb_main(user_id))

async def check_join(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        # اگر کانال پرایوت یا دسترسی مشکل داشته باشه، بهتره اجازه ندیم
        return False


# ---------- استارت ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    ref_by = None
    if args:
        try:
            ref_by = int(args[0])
            if ref_by == user_id:
                ref_by = None   # خودارجاع نباشه
        except:
            ref_by = None

    cur.execute("INSERT OR IGNORE INTO users(user_id, ref_by) VALUES(?, ?)", (user_id, ref_by))
    conn.commit()

    # بلاک؟
    cur.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row and row[0] == 1:
        await update.message.reply_text("🚫 شما توسط پشتیبانی بلاک شده‌اید.")
        return

    # جوین اجباری
    if not await check_join(context, user_id):
        join_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ پیوستم (بازچک)", callback_data="recheck_join")]
        ])
        await update.message.reply_text(
            f"برای استفاده از ربات، لطفاً ابتدا در کانال زیر عضو شوید:\n\n@{CHANNEL_USERNAME}",
            reply_markup=join_kb
        )
        return

    await show_main_menu(update, user_id)


# ---------- هندل دکمه‌ها ----------
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    data = q.data

    # دکمه بازگشت
    if data == "back_to_main":
        context.user_data.clear()
        await show_main_menu(q, user_id)
        return

    # بازچک عضویت
    if data == "recheck_join":
        if await check_join(context, user_id):
            await show_main_menu(q, user_id)
        else:
            join_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
                [InlineKeyboardButton("✅ پیوستم (بازچک)", callback_data="recheck_join")],
                [InlineKeyboardButton("↩ بازگشت", callback_data="back_to_main")]
            ])
            await q.edit_message_text(
                f"❌ هنوز عضو نیستی. لطفاً عضو کانال بشو:\n\n@{CHANNEL_USERNAME}",
                reply_markup=join_kb
            )
        return

    # نمایش لینک کانال اجباری
    if data == "force_channel":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ پیوستم (بازچک)", callback_data="recheck_join")],
            [InlineKeyboardButton("↩ بازگشت", callback_data="back_to_main")]
        ])
        await q.edit_message_text(f"ℹ️ کانال اجباری:\n@{CHANNEL_USERNAME}", reply_markup=kb)
        return

    # آمار زیرمجموعه‌ها
    if data == "stats":
        cur.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (user_id,))
        cnt = cur.fetchone()[0]
        await q.edit_message_text(f"📊 تعداد زیرمجموعه‌های شما: {cnt}", reply_markup=kb_back())
        return

    # لینک زیرمجموعه‌گیری اختصاصی
    if data == "ref_link":
        ref = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        text = (
            "📎 لینک زیرمجموعه‌گیری اختصاصی شما:\n"
            f"{ref}\n\n"
            "هر نفر با این لینک استارت کنه، زیر مجموعه‌ی شما حساب میشه."
        )
        await q.edit_message_text(text, reply_markup=kb_back())
        return

    # دریافت کانفیگ
    if data == "get_config":
        # چک بلاک
        cur.execute("SELECT blocked, free_pass FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        blocked = r[0] if r else 0
        free_pass = r[1] if r else 0
        if blocked == 1:
            await q.edit_message_text("🚫 دسترسی شما مسدود است.", reply_markup=kb_back()); return

        # شرط
        cur.execute("SELECT COUNT(*) FROM users WHERE ref_by=?", (user_id,))
        refs = cur.fetchone()[0]
        eligible = (refs >= 2) or (free_pass == 1) or (user_id == OWNER_ID)

        if not eligible:
            msg = (
                "⚠️ برای دریافت کانفیگ باید حداقل ۲ زیرمجموعه بیاری.\n"
                "یا توسط پشتیبانی معاف بشی."
            )
            await q.edit_message_text(msg, reply_markup=kb_back()); return

        # آخرین کانفیگ
        cur.execute("SELECT text FROM configs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            await q.edit_message_text(f"📩 کانفیگ شما:\n{row[0]}", reply_markup=kb_back())
        else:
            await q.edit_message_text("❌ هنوز کانفیگی ثبت نشده.", reply_markup=kb_back())
        return

    # پیام به پشتیبانی (ورود به حالت)
    if data == "support":
        context.user_data.clear()
        context.user_data["mode"] = "support"
        await q.edit_message_text("✉ پیام خود را بنویسید و ارسال کنید:", reply_markup=kb_back())
        return

    # ------ دکمه‌های مخصوص مالک ------
    if user_id != OWNER_ID and data in {
        "manage_config","broadcast","block_user","unblock_user","freepass_user"
    }:
        await q.edit_message_text("⛔ این بخش فقط برای مالک ربات است.", reply_markup=kb_back())
        return

    if data == "manage_config":  # افزودن کانفیگ
        context.user_data.clear()
        context.user_data["mode"] = "add_config"
        await q.edit_message_text("⚒ متن کانفیگ جدید را ارسال کنید:", reply_markup=kb_back())
        return

    if data == "broadcast":
        context.user_data.clear()
        context.user_data["mode"] = "broadcast"
        await q.edit_message_text("📢 متن پیام عمومی را ارسال کنید:", reply_markup=kb_back())
        return

    if data == "block_user":
        context.user_data.clear()
        context.user_data["mode"] = "block"
        await q.edit_message_text("🔒 آیدی عددی کاربر برای بلاک را ارسال کنید:", reply_markup=kb_back())
        return

    if data == "unblock_user":
        context.user_data.clear()
        context.user_data["mode"] = "unblock"
        await q.edit_message_text("🔓 آیدی عددی کاربر برای آزادسازی را ارسال کنید:", reply_markup=kb_back())
        return

    if data == "freepass_user":
        context.user_data.clear()
        context.user_data["mode"] = "freepass"
        await q.edit_message_text("🎫 آیدی عددی کاربر برای معافیت را ارسال کنید:", reply_markup=kb_back())
        return


# ---------- متن‌ها (براساس state) ----------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    mode = context.user_data.get("mode")

    # اگر کاربر بلاک است، هیچ کاری نکنیم به جز پیام ثابت
    cur.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row and row[0] == 1 and user_id != OWNER_ID:
        await update.message.reply_text("🚫 دسترسی شما مسدود است.")
        return

    # حالت پشتیبانی
    if mode == "support":
        # پیام کاربر را برای مالک فوروارد/ارسال کن به همراه آیدی عددی
        try:
            # پیام به مالک
            await context.bot.send_message(
                OWNER_ID,
                f"📩 پیام جدید از کاربر {user_id}:\n\n{text}"
            )
        except:
            pass
        await update.message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.", reply_markup=kb_back())
        context.user_data.clear()
        return

    # حالت افزودن کانفیگ (فقط مالک)
    if mode == "add_config" and user_id == OWNER_ID:
        cur.execute("INSERT INTO configs(text) VALUES(?)", (text,))
        conn.commit()
        await update.message.reply_text("✅ کانفیگ ذخیره شد.", reply_markup=kb_back())
        context.user_data.clear()
        return

    # حالت برودکست (فقط مالک)
    if mode == "broadcast" and user_id == OWNER_ID:
        cur.execute("SELECT user_id FROM users WHERE blocked=0")
        users = [r[0] for r in cur.fetchall()]
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(uid, f"📢 پیام عمومی:\n{text}")
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ پیام برای {sent} کاربر ارسال شد.", reply_markup=kb_back())
        context.user_data.clear()
        return

    # حالت بلاک/آزادسازی/معافیت (فقط مالک)
    if user_id == OWNER_ID and mode in ("block", "unblock", "freepass"):
        if not text.isdigit():
            await update.message.reply_text("❗ لطفاً فقط آیدی عددی کاربر را بفرست.", reply_markup=kb_back())
            return
        target = int(text)

        # مطمئن شو کاربر در جدول هست
        cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (target,))
        if mode == "block":
            cur.execute("UPDATE users SET blocked=1 WHERE user_id=?", (target,))
            msg = f"🔒 کاربر {target} بلاک شد."
            # خبر بده به کاربر (ممکنه نشه)
            try: await context.bot.send_message(target, "🚫 دسترسی شما توسط پشتیبانی مسدود شد.")
            except: pass
        elif mode == "unblock":
            cur.execute("UPDATE users SET blocked=0 WHERE user_id=?", (target,))
            msg = f"🔓 کاربر {target} آزاد شد."
            try: await context.bot.send_message(target, "✅ دسترسی شما آزاد شد.")
            except: pass
        else:  # freepass
            cur.execute("UPDATE users SET free_pass=1 WHERE user_id=?", (target,))
            msg = f"🎫 کاربر {target} معاف شد (بدون نیاز به زیرمجموعه)."
            try: await context.bot.send_message(target, "🎫 شما معاف شدید؛ می‌توانید کانفیگ را دریافت کنید.")
            except: pass

        conn.commit()
        await update.message.reply_text(f"✅ {msg}", reply_markup=kb_back())
        context.user_data.clear()
        return

    # اگر هیچ حالتی فعال نبود، چیزی انجام نده (یا راهنمای سریع بده)
    # می‌تونیم منو را هم برگردونیم:
    await update.message.reply_text("برای استفاده از دکمه‌ها، از منوی شیشه‌ای استفاده کن.", reply_markup=kb_main(user_id))


# ---------- ثبت هندلرها ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling()

if __name__ == "__main__":
    main()