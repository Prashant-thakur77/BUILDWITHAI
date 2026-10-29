"""Records the film's footage as crisp frames (Chrome's CDP screencast, JPEG q92) and writes an exact-timed MP4, plus
the moments the editor cuts on (wall-clock marks, in seconds from the first frame) and the boxes it zooms into.

    python video/record.py product      the live app, driven like a visitor: one sentence, then "Who owes whom?"
    python video/record.py gfx-<scene>  a drawn scene from graphics.html (or three.html for arch), timed to the voice

The product flow talks to the real running server (uvicorn server:app --port 8765), which calls Claude through
Google ADK. Nothing is mocked: the replies, ledger and usage numbers are whatever the live agent returned.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import AUDIO, BUILD, CLIPS, SITE, VIDEO  # noqa: E402

SENTENCE = ("Arjun paid 1200 for dinner for everyone, Riya paid 600 for the cab split with Kabir and me, "
            "and I paid 900 for hotel snacks for all")
ASK = "Who owes whom?"
SCALE = 1.25  # the app's 1536x864 desktop layout rendered into exactly 1920x1080 pixels

CURSOR_CSS = """#rec-cursor{position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
background:rgba(66,133,244,.30);box-shadow:0 0 0 2px rgba(66,133,244,.9),0 0 24px 6px rgba(66,133,244,.25);
pointer-events:none;z-index:2147483647;transition:transform 120ms cubic-bezier(.16,1,.3,1)}
#rec-cursor.down{transform:scale(.75)}
.rec-ripple{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:2px solid rgba(66,133,244,.9);
pointer-events:none;z-index:2147483646;animation:rec-ripple 600ms cubic-bezier(.16,1,.3,1) forwards}
@keyframes rec-ripple{to{transform:scale(4);opacity:0}}"""
CURSOR_JS = """() => {
  const dot = Object.assign(document.createElement('div'), { id: 'rec-cursor' });
  document.body.append(dot);
  addEventListener('mousemove', (e) => (dot.style.translate = `${e.clientX}px ${e.clientY}px`), true);
  addEventListener('mousedown', (e) => {
    dot.classList.add('down');
    const r = Object.assign(document.createElement('div'), { className: 'rec-ripple' });
    r.style.left = `${e.clientX}px`; r.style.top = `${e.clientY}px`;
    document.body.append(r); setTimeout(() => r.remove(), 700);
  }, true);
  addEventListener('mouseup', () => dot.classList.remove('down'), true);
}"""


class Recorder:
    def __init__(self, page, cdp, frames_dir: str):
        self.page, self.cdp, self.dir = page, cdp, frames_dir
        self.frames: list[tuple[str, float]] = []
        self.t0: float | None = None
        self.marks: dict[str, float] = {}
        self.boxes: dict[str, list[float]] = {}
        self.mouse = (768.0, 600.0)
        cdp.on("Page.screencastFrame", self._frame)

    def _frame(self, f: dict) -> None:
        t = f["metadata"]["timestamp"]
        if self.t0 is None:
            self.t0 = t
        path = f"{self.dir}/{len(self.frames):05d}.jpg"
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(f["data"]))
        self.frames.append((path, t - self.t0))
        asyncio.ensure_future(self.cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]}))

    def mark(self, name: str) -> None:
        # Wall clock, not frame time: the screencast sends nothing while the page is still.
        self.marks[name] = 0.0 if self.t0 is None else time.time() - self.t0
        print(f"mark {name} {self.marks[name]:.2f}", flush=True)

    async def box(self, name: str, locator) -> None:
        b = await locator.bounding_box()
        self.boxes[name] = [round(v * SCALE, 1) for v in (b["x"], b["y"], b["width"], b["height"])]

    async def start(self) -> None:
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080,
                                                     "everyNthFrame": 1})
        await self.page.wait_for_timeout(400)
        self.mark("start")

    async def press(self, locator, click: bool = True) -> None:
        """Glides the cursor to the middle of *locator* on an eased path, then clicks it."""
        b = await locator.bounding_box()
        to = (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        x0, y0 = self.mouse
        for i in range(1, 25):
            k = 1 - (1 - i / 24) ** 3
            await self.page.mouse.move(x0 + (to[0] - x0) * k, y0 + (to[1] - y0) * k)
            await self.page.wait_for_timeout(14)
        self.mouse = to
        if click:
            await self.page.wait_for_timeout(120)
            await self.page.mouse.down()
            await self.page.wait_for_timeout(90)
            await self.page.mouse.up()

    def encode(self, out: str) -> None:
        """Each frame lasts until the next; the last one until the 'end' mark, so a still ending isn't cut short."""
        frames = sorted(self.frames, key=lambda f: f[1])
        last = max(frames[-1][1] + 0.5, self.marks.get("end", 0.0))
        lines = []
        for i, (path, t) in enumerate(frames):
            nxt = frames[i + 1][1] if i + 1 < len(frames) else last
            lines.append(f"file '{path}'\nduration {max(0.001, nxt - t):.4f}")
        lst = f"{self.dir}/list.txt"
        open(lst, "w").write("\n".join(lines) + f"\nfile '{frames[-1][0]}'\n")
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf",
                            "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "16",
                            "-preset", "medium", out])
        if r.returncode == 0:
            shutil.rmtree(self.dir, ignore_errors=True)  # kept when the encode fails, to see why
        print(f"{os.path.basename(out)}: {len(frames)} frames, {last:.1f} s, ffmpeg {r.returncode}")


async def product(rec: Recorder, page) -> None:
    urllib.request.urlopen(urllib.request.Request(f"{SITE}/api/usage/reset", method="POST"))
    await page.goto(SITE, wait_until="networkidle")
    await page.evaluate("document.fonts.ready")
    await page.add_style_tag(content=CURSOR_CSS)
    await page.evaluate(CURSOR_JS)
    await page.mouse.move(*rec.mouse)
    await rec.start()
    await page.wait_for_timeout(1500)
    box = page.locator("#input")
    await rec.press(box)
    rec.mark("typing")
    await page.keyboard.type(SENTENCE, delay=24)
    rec.mark("typed")
    await page.wait_for_timeout(500)
    await rec.press(page.locator("#send"))
    rec.mark("sent")
    await page.wait_for_function("document.querySelectorAll('.meta').length >= 1", timeout=120_000)
    rec.mark("reply")
    await rec.box("reply", page.locator(".msg.agent").last)
    await rec.box("ledger", page.locator("#ledger"))
    await page.wait_for_timeout(3000)
    await page.screenshot(path=f"{CLIPS}/shot-chat.png")
    await rec.press(page.locator("#suggest button", has_text=ASK))
    rec.mark("ask")
    await page.wait_for_function("document.querySelectorAll('.meta').length >= 2", timeout=120_000)
    rec.mark("settled")
    await page.wait_for_timeout(200)
    await rec.box("settle", page.locator(".msg.agent").last)
    await page.wait_for_timeout(3500)
    await page.screenshot(path=f"{CLIPS}/shot-settle.png")
    await page.evaluate("refreshUsage()")
    await page.wait_for_timeout(600)
    await rec.box("kpis", page.locator(".kpis"))
    await rec.box("dash", page.locator(".dash"))
    await rec.box("reqs", page.locator("table.reqs"))
    await rec.press(page.locator("#k-lat"), click=False)
    rec.mark("dash")
    await page.wait_for_timeout(2500)
    await rec.press(page.locator("table.reqs tbody tr").first, click=False)
    rec.mark("reqs")
    await page.wait_for_timeout(3500)
    await page.screenshot(path=f"{CLIPS}/shot-dash.png")
    rec.mark("end")
    state = json.load(urllib.request.urlopen(f"{SITE}/api/usage"))
    json.dump(state, open(f"{CLIPS}/product.usage.json", "w"), indent=1)


async def graphics(rec: Recorder, page, name: str) -> None:
    """A drawn scene, timed to its lines and their spoken words, recorded in real time."""
    tl = json.load(open(f"{BUILD}/timeline.json"))
    scene = next(s for s in tl["scenes"] if s["name"] == name)
    cues = {ln["id"]: round(ln["start"] - scene["start"], 3) for ln in scene["lines"]}
    allw = json.load(open(f"{AUDIO}/words.json"))
    words = {ln["id"]: [[w, round(a + ln["start"] - scene["start"], 3)] for w, a, _ in allw.get(ln["id"], [])]
             for ln in scene["lines"]}
    facts = open(f"{BUILD}/facts.json").read()
    if name == "arch":
        from narration import arch_cues

        q = urllib.parse.urlencode({"dur": scene["dur"], "cues": json.dumps(arch_cues(cues, words))})
        url = f"file://{VIDEO}/three.html?{q}"
    else:
        boxes = json.load(open(f"{CLIPS}/product.marks.json"))["boxes"]
        h = urllib.parse.urlencode({"scene": name, "dur": scene["dur"], "cues": json.dumps(cues), "words": json.dumps(words),
                                    "facts": facts, "shots": f"file://{CLIPS}", "boxes": json.dumps(boxes)})
        url = f"file://{VIDEO}/graphics.html?{h}"
    await page.goto(url)
    await page.evaluate("document.fonts.ready")
    await page.wait_for_function("window.__ready === true", timeout=30_000)
    await rec.start()
    await page.evaluate("window.__start()")
    await page.wait_for_timeout(int(scene["dur"] * 1000) + 300)
    rec.mark("end")


async def main(flow: str) -> None:
    os.makedirs(CLIPS, exist_ok=True)
    frames = f"{CLIPS}/frames-{flow}"
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames)
    async with async_playwright() as p:
        # The laptop GPU through ANGLE: the 3D scene renders at full rate (SwiftShader drags the screencast down).
        browser = await p.chromium.launch(args=["--use-angle=gl", "--enable-gpu", "--ignore-gpu-blocklist",
                                                "--allow-file-access-from-files"])
        drawn = flow.startswith("gfx-")
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080} if drawn else {"width": 1536, "height": 864},
            device_scale_factor=1 if drawn else SCALE, color_scheme="light")
        page = await ctx.new_page()
        page.on("console", lambda m: m.type == "error" and print("console:", m.text))
        cdp = await ctx.new_cdp_session(page)
        rec = Recorder(page, cdp, frames)
        if drawn:
            await graphics(rec, page, flow[4:])
        else:
            await product(rec, page)
        await cdp.send("Page.stopScreencast")
        await browser.close()
    rec.encode(f"{CLIPS}/{flow}.mp4")
    json.dump({"marks": rec.marks, "boxes": rec.boxes}, open(f"{CLIPS}/{flow}.marks.json", "w"), indent=1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
