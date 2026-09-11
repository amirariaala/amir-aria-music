#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amir Aria Music Bot
--------------------
یک ربات تلگرام که با گرفتن لینک پست/ریلز اینستاگرام، ویدیو را دانلود
می‌کند، صدای آن (موزیک، AI، ریمیکس و غیره) را استخراج می‌کند و به صورت
فایل صوتی MP3 برای کاربر ارسال می‌کند.

نیازمندی‌ها:
    pip install python-telegram-bot==21.6 yt-dlp
    نصب ffmpeg روی سیستم (برای استخراج صدا)

اجرا:
    export BOT_TOKEN="توکن ربات شما از @BotFather"
    python3 bot.py
"""

import os
import re
import logging
import tempfile
import shutil

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import yt_dlp

# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # توکن رو از متغیر محیطی می‌خونه
BOT_NAME = "Amir Aria Music"

INSTAGRAM_URL_RE = re.compile(
    r"(https?://)?(www\.)?instagram\.com/(reel|p|tv|stories)/[A-Za-z0-9_\-/]+",
    re.IGNORECASE,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(BOT_NAME)

MAX_TELEGRAM_AUDIO_MB = 50  # محدودیت تلگرام برای بات‌های معمولی (~50MB)


# ---------------------------------------------------------------------------
# توابع کمکی
# ---------------------------------------------------------------------------

def extract_instagram_url(text: str) -> str | None:
    """اولین لینک اینستاگرام معتبر داخل متن رو پیدا می‌کنه."""
    match = INSTAGRAM_URL_RE.search(text)
    if not match:
        return None
    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    return url


def download_audio_from_instagram(url: str, out_dir: str) -> str:
    """
    با yt-dlp ویدیوی اینستاگرام رو دانلود و صداشو به mp3 تبدیل می‌کنه.
    مسیر فایل mp3 نهایی رو برمی‌گردونه.
    """
    out_template = os.path.join(out_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        # اگر پست اینستاگرام پرایوت باشه و نیاز به لاگین داشته باشه،
        # می‌تونی کوکی مرورگرت رو اینجا اضافه کنی:
        # "cookiefile": "instagram_cookies.txt",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id")

    mp3_path = os.path.join(out_dir, f"{video_id}.mp3")
    if not os.path.exists(mp3_path):
        # بعضی وقتا پسوند فرق می‌کنه، دنبال هر فایلی با همون id بگرد
        for f in os.listdir(out_dir):
            if f.startswith(video_id):
                mp3_path = os.path.join(out_dir, f)
                break

    return mp3_path, info


# ---------------------------------------------------------------------------
# هندلرهای ربات
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"سلام! 👋 من ربات {BOT_NAME} هستم.\n\n"
        "فقط کافیه لینک ریلز یا پست اینستاگرام رو برام بفرستی، "
        "من موزیک/صدای اون کلیپ رو (حتی اگه ریمیکس یا AI باشه) "
        "برات به‌صورت فایل MP3 دانلود می‌کنم و می‌فرستم. 🎵\n\n"
        "مثال:\n"
        "https://www.instagram.com/reel/xxxxxxxxx/"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "راهنما:\n"
        "1) لینک ریلز/پست اینستاگرام رو کپی کن.\n"
        "2) همون‌جا برام بفرست.\n"
        "3) صبر کن تا موزیکشو استخراج کنم و برات بفرستم.\n\n"
        "نکته: پست باید عمومی (Public) باشه، وگرنه دسترسی ندارم."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    url = extract_instagram_url(text)

    if not url:
        await update.message.reply_text(
            "یه لینک معتبر اینستاگرام (ریلز یا پست) برام بفرست تا موزیکشو برات بیارم. 🙏"
        )
        return

    status_msg = await update.message.reply_text("⏳ در حال دانلود و استخراج موزیک...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VOICE)

    tmp_dir = tempfile.mkdtemp(prefix="aam_")
    try:
        mp3_path, info = download_audio_from_instagram(url, tmp_dir)

        if not os.path.exists(mp3_path):
            await status_msg.edit_text("❌ نتونستم صدا رو از این لینک استخراج کنم.")
            return

        size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        if size_mb > MAX_TELEGRAM_AUDIO_MB:
            await status_msg.edit_text(
                f"❌ حجم فایل ({size_mb:.1f}MB) بیشتر از محدودیت تلگرام ({MAX_TELEGRAM_AUDIO_MB}MB) هست."
            )
            return

        title = info.get("title") or "Amir Aria Music"
        uploader = info.get("uploader") or ""

        with open(mp3_path, "rb") as audio_file:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=audio_file,
                title=title[:60],
                performer=uploader or BOT_NAME,
                caption=f"🎧 استخراج شده توسط {BOT_NAME}",
            )

        await status_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.warning(f"DownloadError: {e}")
        await status_msg.edit_text(
            "❌ نتونستم این لینک رو دانلود کنم.\n"
            "ممکنه پست پرایوت باشه، لینک اشتباه باشه یا اینستاگرام موقتاً بلاک کرده باشه."
        )
    except Exception as e:
        logger.exception("خطای غیرمنتظره")
        await status_msg.edit_text(f"❌ یه خطای غیرمنتظره پیش اومد: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# اجرای ربات
# ---------------------------------------------------------------------------

def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "توکن ربات ست نشده! ابتدا متغیر محیطی BOT_TOKEN رو ست کن:\n"
            "  export BOT_TOKEN='توکن شما از @BotFather'"
        )

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"{BOT_NAME} در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
