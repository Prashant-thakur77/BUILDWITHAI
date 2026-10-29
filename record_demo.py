"""Records a demo of the running app with Playwright + Chromium.

Usage: python record_demo.py [base_url] [output.mp4]
Needs the server running (uvicorn server:app --port 8765) and ffmpeg for mp4.
"""

import asyncio
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path.home() / "Downloads" / "settleup-agent-demo.mp4")
SIZE = {"width": 1440, "height": 900}

SCRIPT = [
    "Arjun paid 1200 for dinner for everyone, Riya paid 600 for the cab split with Kabir and me, "
    "and I paid 900 for hotel snacks for all",
    "Kabir paid 450 for movie tickets split with Riya and Arjun",
    "Who owes whom?",
]
SECOND_SESSION = [
    "Meera paid 3000 for groceries split with Dev and Sana",
    "Dev paid 1500 for electricity split with Meera and Sana",
    "settle up",
]


async def say(page, text, replies_before):
    await page.click("#input")
    await page.keyboard.type(text, delay=28)
    await page.wait_for_timeout(300)
    await page.click("#send")
    await page.wait_for_function(f"document.querySelectorAll('.meta').length > {replies_before}")
    await page.wait_for_timeout(1800)


async def main():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/usage/reset", method="POST"))
    tmp = Path(tempfile.mkdtemp())
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport=SIZE, record_video_dir=tmp, record_video_size=SIZE)
        page = await ctx.new_page()
        await page.goto(BASE)
        await page.wait_for_timeout(2500)

        for i, msg in enumerate(SCRIPT):
            await say(page, msg, i)
        await page.wait_for_timeout(2500)

        # A second group in a fresh session, so the dashboard shows multiple sessions.
        await page.reload()
        await page.wait_for_timeout(1500)
        for i, msg in enumerate(SECOND_SESSION):
            await say(page, msg, i)

        await page.hover("#lat rect >> nth=-1")
        await page.wait_for_timeout(1500)
        await page.hover("table.reqs")
        await page.wait_for_timeout(3500)
        video = await page.video.path()
        await ctx.close()
        await browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.suffix == ".mp4" and shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(OUT)], check=True)
    else:
        shutil.copy(video, OUT.with_suffix(".webm"))
    print(f"saved {OUT}")


asyncio.run(main())
