import os
import asyncio
import yt_dlp
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
from motor.motor_asyncio import AsyncIOMotorClient

# ==================== CONFIG ====================
API_ID = 33798531
API_HASH = "5daa87783e064820a001056e97891e6e"
BOT_TOKEN = "8544699721:AAFR1w33OXLeGHjmjQfkRYOrEKk7lfIsPn4"
STRING_SESSION = "AQIDuYMAioNUsm7-o2eWd0RyaSG7hN27qzEj4crn5UO8eTxtNNYX4Pn5pU3rdihia9Pc0pxzdY7-FkoJRap90fus-xKVvljdOta3_7pGuzrDgT2H_yT0Uq6cgWsGJS1hOyIM2Rqqs4w74qe65hSx2IRGkxglZZJjgpep8NFKr8E9XH7NZHjV8DACmS1o5exGBtfBhM8OkCn3fJC6fD5QaFNtU-5KyyVzwhPcJFA8woiFXsLvj37P732BqhWq-HXQBDiMR1EYis-AEyJXlkn4Hv_NBHTB6y2YGu6S-ZJ6mn1-PRkj3B06x31dXCTPjlOY8u7-PEooEsMpRQWRDSPVhtk-TXsTTAAAAAHwxqJsAA"
MONGO_URL = "mongodb+srv://rj5706603:O95nvJYxapyDHfkw@cluster0.fzmckei.mongodb.net/?retryWrites=true&w=majority"
OWNER_ID = 7167704900

# ==================== INIT ====================
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_client = Client("user", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
call = PyTgCalls(user_client)

# MongoDB
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.music_bot
users_col = db.users

# Queues
queues = {}
current_playing = {}
loop_status = {}

# ==================== HELPERS ====================
async def download_audio(url):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            return filename, info['title'], info.get('duration', 0)
    except:
        return None, None, None

async def get_youtube_url(query):
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if 'youtube.com' in query or 'youtu.be' in query:
                info = ydl.extract_info(query, download=False)
                return query, info['title'], info.get('duration', 0)
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if info.get('entries'):
                    video = info['entries'][0]
                    return video['webpage_url'], video['title'], video.get('duration', 0)
    except:
        return None, None, None
    return None, None, None

async def play_song(chat_id, url, title, duration):
    try:
        audio_file, _, _ = await download_audio(url)
        if audio_file:
            await call.change_stream(chat_id, AudioPiped(audio_file))
            current_playing[chat_id] = {'title': title, 'duration': duration, 'url': url}
            return True
    except:
        return False
    return False

async def play_next(chat_id):
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].pop(0)
        await play_song(chat_id, next_song['url'], next_song['title'], next_song['duration'])
    else:
        current_playing.pop(chat_id, None)
        await call.leave_call(chat_id)

# ==================== COMMANDS ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    await users_col.update_one(
        {"user_id": message.from_user.id},
        {"$set": {"username": message.from_user.username, "last_active": datetime.now()}},
        upsert=True
    )
    await message.reply_text(
        "🎵 **Music Bot** 🎵\n\n"
        "**Commands:**\n"
        "• /play <song/url> - Play music\n"
        "• /pause - Pause\n"
        "• /resume - Resume\n"
        "• /skip - Skip\n"
        "• /stop - Stop\n"
        "• /queue - Show queue\n"
        "• /join - Join voice chat\n"
        "• /leave - Leave\n\n"
        "**Made by:** @ZenoRealWebs"
    )

@app.on_message(filters.command("play") & filters.group)
async def play_command(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check if user in voice chat
    try:
        user = await app.get_chat_member(chat_id, user_id)
        if not user.voice_chat:
            await message.reply_text("❌ Join a voice chat first!")
            return
    except:
        await message.reply_text("❌ Join a voice chat first!")
        return
    
    query = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else None
    if not query:
        await message.reply_text("❌ Usage: /play <song name or URL>")
        return
    
    await message.reply_text("⏳ Searching...")
    
    url, title, duration = await get_youtube_url(query)
    if not url:
        await message.reply_text("❌ Could not find the song!")
        return
    
    if chat_id in current_playing:
        if chat_id not in queues:
            queues[chat_id] = []
        queues[chat_id].append({'url': url, 'title': title, 'duration': duration})
        await message.reply_text(f"✅ Added to queue!\n\n🎧 {title}\n📍 Position: {len(queues[chat_id])}")
    else:
        await message.reply_text("⏳ Downloading...")
        success = await play_song(chat_id, url, title, duration)
        if success:
            await message.reply_text(f"🎵 **Now Playing:**\n{title}")

@app.on_message(filters.command("pause") & filters.group)
async def pause_command(client, message):
    await call.pause_stream(message.chat.id)
    await message.reply_text("⏸ **Paused**")

@app.on_message(filters.command("resume") & filters.group)
async def resume_command(client, message):
    await call.resume_stream(message.chat.id)
    await message.reply_text("▶️ **Resumed**")

@app.on_message(filters.command("skip") & filters.group)
async def skip_command(client, message):
    chat_id = message.chat.id
    if chat_id in current_playing:
        await play_next(chat_id)
        await message.reply_text("⏭ **Skipped**")

@app.on_message(filters.command("stop") & filters.group)
async def stop_command(client, message):
    chat_id = message.chat.id
    if chat_id in queues:
        queues[chat_id].clear()
    current_playing.pop(chat_id, None)
    await call.leave_call(chat_id)
    await message.reply_text("🗑 **Stopped**")

@app.on_message(filters.command("queue") & filters.group)
async def queue_command(client, message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        await message.reply_text("📜 **Queue is empty!**")
        return
    
    text = "📜 **Current Queue**\n\n"
    for i, song in enumerate(queues[chat_id][:10], 1):
        dur = song['duration']
        text += f"{i}. {song['title']} [{dur//60}:{dur%60:02d}]\n"
    await message.reply_text(text)

@app.on_message(filters.command("join") & filters.group)
async def join_command(client, message):
    try:
        await call.join_call(message.chat.id)
        await message.reply_text("✅ **Joined voice chat!**")
    except:
        await message.reply_text("❌ Could not join!")

@app.on_message(filters.command("leave") & filters.group)
async def leave_command(client, message):
    chat_id = message.chat.id
    try:
        await call.leave_call(chat_id)
        current_playing.pop(chat_id, None)
        if chat_id in queues:
            queues[chat_id].clear()
        await message.reply_text("👋 **Left voice chat!**")
    except:
        await message.reply_text("❌ Not in voice chat!")

@app.on_message(filters.command("ping") & filters.group)
async def ping_command(client, message):
    start = datetime.now()
    msg = await message.reply_text("🏓 Pinging...")
    end = datetime.now()
    ping = (end - start).microseconds / 1000
    await msg.edit_text(f"🏓 **Pong!**\n\nLatency: {ping:.2f}ms")

@call.on_stream_end()
async def on_stream_end(chat_id):
    await play_next(chat_id)

# ==================== RUN ====================
async def main():
    await user_client.start()
    await app.start()
    await call.start()
    print("🎵 Music Bot Started!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
