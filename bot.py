import os
import time
import math
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

# Kalitlar Render environment variables'dan avtomatik olinadi
API_ID = int(os.environ.get("30154083"))
API_HASH = os.environ.get("5007eb6dd3a2ccd1bcbc16c2a1cfa7a5")
BOT_TOKEN = os.environ.get("8766736272:AAHy5uq8w3QUq7epO8kGH8ikFP1QA5jvvNo")

app = Client("ultra_render_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

last_update = {}
MAX_SIZE_BYTES = 1950 * 1024 * 1024  # Telegram uchun 1.95 GB chegara

async def progress(current, total, message: Message, part_info=""):
    msg_id = message.id
    now = time.time()
    if msg_id in last_update and (now - last_update[msg_id]) < 4:
        return
    last_update[msg_id] = now
    percent = round(current / total * 100, 1)
    try:
        await message.edit_text(f"🚀 Telegram'ga yuborilmoqda {part_info}: **{percent}%**")
    except Exception:
        pass

def get_video_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

def split_video(file_path):
    file_size = os.path.getsize(file_path)
    if file_size <= MAX_SIZE_BYTES:
        return [file_path]

    total_duration = get_video_duration(file_path)
    parts_count = math.ceil(file_size / MAX_SIZE_BYTES)
    part_duration = math.floor(total_duration / parts_count)

    split_files = []
    base_name, ext = os.path.splitext(file_path)

    for i in range(parts_count):
        output_file = f"{base_name}_part{i+1}{ext}"
        start_time = i * part_duration
        
        cmd = [
            "ffmpeg", "-y", "-ss", str(start_time),
            "-i", file_path, "-t", str(part_duration),
            "-c", "copy", output_file
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_file):
            split_files.append(output_file)

    return split_files

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text("⚡️ **Ultra Premium Media Bot (Render Server)!**\n\nMenga istalgan video havolasini yuboring. Katta hajmdagi videolar bo'lsa avtomatik bo'lib yuboriladi.")

@app.on_message(filters.text & filters.private)
async def downloader(client, message: Message):
    url = message.text.strip()
    if url.startswith("/"):
        return

    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply_text("❌ Noto'g'ri havola!")
        return

    msg = await message.reply_text("⚡️ Serverga yuklanmoqda...")

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
    }

    file_path = None
    parts = []

    try:
        loop = asyncio.get_event_loop()
        def extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, extract)

        if not os.path.exists(file_path):
            base, _ = os.path.splitext(file_path)
            if os.path.exists(f"{base}.mp4"):
                file_path = f"{base}.mp4"

        file_size_gb = round(os.path.getsize(file_path) / (1024 ** 3), 2)

        if file_size_gb > 1.95:
            await msg.edit_text(f"✂️ Fayl hajmi **{file_size_gb} GB**. Video 2 GB bo'laklarga bo'linmoqda...")
            parts = await loop.run_in_executor(None, split_video, file_path)
        else:
            parts = [file_path]

        total_parts = len(parts)
        for idx, part in enumerate(parts, 1):
            part_info = f"({idx}/{total_parts}-qism)" if total_parts > 1 else ""
            await msg.edit_text(f"📤 Telegram'ga yuborilmoqda {part_info}...")

            ext = os.path.splitext(part)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                await client.send_photo(chat_id=message.chat.id, photo=part)
            else:
                await client.send_video(
                    chat_id=message.chat.id,
                    video=part,
                    caption=f"✅ Video yuklandi {part_info}",
                    supports_streaming=True,
                    progress=progress,
                    progress_args=(msg, part_info)
                )

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Xatolik yuz berdi: `{e}`")

    finally:
        if msg.id in last_update:
            del last_update[msg.id]
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        for p in parts:
            if os.path.exists(p):
                os.remove(p)

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run()
