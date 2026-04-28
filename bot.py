import os, time, asyncio
from threading import Thread
from flask import Flask

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME
from helper import progress, compress, thumbnail

DOWNLOAD = "downloads/"
COMPRESS = "compress/"
THUMB = "thumbs/"

os.makedirs(DOWNLOAD, exist_ok=True)
os.makedirs(COMPRESS, exist_ok=True)
os.makedirs(THUMB, exist_ok=True)

# ========= WEB =========
web = Flask(__name__)

@web.route("/")
def home():
    return "Bot running"

def run_web():
    web.run("0.0.0.0", 10000)

Thread(target=run_web).start()

# ========= BOT =========
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

QUEUE = asyncio.Queue()
WORKERS = 2

user_files = {}
user_thumbs = {}
active_jobs = {}

# ========= WORKER =========
async def worker(worker_id):
    while True:
        msg, file, target, user_id = await QUEUE.get()

        try:
            out = f"{COMPRESS}/{time.time()}.mp4"

            thumb_path = user_thumbs.get(user_id)
            if not thumb_path:
                thumb_path = f"{THUMB}/{time.time()}.jpg"
                await thumbnail(file, thumb_path)

            await msg.edit(f"⚙️ Worker {worker_id} processing...")

            active_jobs[user_id] = msg

            await compress(file, out, target, msg)

            active_jobs.pop(user_id, None)

            up = await msg.edit("📤 Uploading...")
            start = time.time()

            await msg.reply_video(
                out,
                thumb=thumb_path if os.path.exists(thumb_path) else None,
                caption=f"✅ Done\n🤖 {BOT_NAME}",
                progress=progress,
                progress_args=(up, start, "📤 Uploading...")
            )

            await up.delete()

            os.remove(file)
            os.remove(out)

        except Exception as e:
            active_jobs.pop(user_id, None)
            await msg.edit(f"❌ Error: {e}")

        QUEUE.task_done()

# ========= COMMANDS =========

@app.on_message(filters.command("start"))
async def start(_, m):
    await m.reply("👋 Send video")

@app.on_message(filters.command("help"))
async def help_cmd(_, m):
    await m.reply("/start /queuelist /stats /cancel /setthumbnail /removethumbnail")

@app.on_message(filters.command("stats"))
async def stats(_, m):
    await m.reply(f"Active: {len(active_jobs)} | Queue: {QUEUE.qsize()}")

@app.on_message(filters.command("queuelist"))
async def ql(_, m):
    await m.reply(f"Queue: {QUEUE.qsize()}")

@app.on_message(filters.command("cancel"))
async def cancel(_, m):
    uid = m.from_user.id
    if uid in active_jobs:
        active_jobs.pop(uid, None)
        return await m.reply("Stopping job...")

    await m.reply("No active job")

@app.on_message(filters.command("setthumbnail"))
async def setthumb(_, m):
    user_thumbs[m.from_user.id] = "WAIT"
    await m.reply("Send photo")

@app.on_message(filters.photo)
async def save_thumb(_, m):
    if user_thumbs.get(m.from_user.id) != "WAIT":
        return
    path = await m.download(file_name=THUMB)
    user_thumbs[m.from_user.id] = path
    await m.reply("Saved")

@app.on_message(filters.command("removethumbnail"))
async def removethumb(_, m):
    user_thumbs.pop(m.from_user.id, None)
    await m.reply("Removed")

# ========= RECEIVE =========

@app.on_message(filters.video | filters.document)
async def recv(_, m):

    msg = await m.reply("📥 Downloading...")
    start = time.time()

    file = await m.download(
        file_name=DOWNLOAD,
        progress=progress,
        progress_args=(msg, start, "📥 Downloading...")
    )

    user_files[m.from_user.id] = file

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("50MB","50"),
         InlineKeyboardButton("100MB","100")]
    ])

    await msg.edit("Select size:", reply_markup=kb)

# ========= CALLBACK =========

@app.on_callback_query()
async def cb(_, q):

    file = user_files.get(q.from_user.id)

    if not file:
        return await q.answer("Missing", show_alert=True)

    await q.message.edit(f"Added to queue: {QUEUE.qsize()+1}")

    await QUEUE.put((q.message, file, int(q.data), q.from_user.id))

# ========= RUN =========

if __name__ == "__main__":
    app.start()

    loop = asyncio.get_event_loop()

    for i in range(WORKERS):
        loop.create_task(worker(i+1))

    loop.run_forever()
