import asyncio, time, os

async def progress(current, total, message, start, text):
    diff = time.time() - start
    if diff < 1:
        return

    percent = current * 100 / total
    speed = current / diff
    eta = (total - current) / speed if speed else 0

    bar = "█"*int(percent/10)+"░"*(10-int(percent/10))

    try:
        await message.edit(
            f"{text}\n\n"
            f"[{bar}] {percent:.2f}%\n"
            f"⚡ {speed/1024/1024:.2f} MB/s\n"
            f"⏳ ETA: {int(eta)}s"
        )
    except:
        pass


async def thumbnail(input_file, output):
    cmd = f'ffmpeg -y -i "{input_file}" -ss 00:00:03 -vframes 1 "{output}"'
    await asyncio.create_subprocess_shell(cmd)


async def compress(input_file, output_file, target_mb, message):

    probe = await asyncio.create_subprocess_shell(
        f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{input_file}"',
        stdout=asyncio.subprocess.PIPE
    )
    out, _ = await probe.communicate()

    duration = float(out.decode().strip())
    bitrate = int((target_mb * 1024 * 1024 * 8) / duration)

    cmd = [
        "ffmpeg","-y",
        "-i", input_file,
        "-b:v", str(bitrate),
        "-preset","ultrafast",
        "-c:v","libx264",
        "-c:a","aac","-b:a","96k",
        output_file
    ]

    process = await asyncio.create_subprocess_exec(*cmd)

    start = time.time()

    while True:
        if process.returncode is not None:
            break

        elapsed = int(time.time() - start)

        try:
            await message.edit(
                f"⚙️ Compressing...\n\n"
                f"⏱ {elapsed}s\n"
                f"🔄 Processing..."
            )
        except:
            pass

        await asyncio.sleep(3)

    await process.wait()

    if not os.path.exists(output_file):
        raise Exception("Compression failed")
