"""Cuts the film: every scene to the narration timeline, the voice over one ducked piano theme with a few effects,
word-by-word captions, loudness at -14 LUFS.

Inputs, all under ~/Videos/settleup: build/timeline.json, build/facts.json, audio/lines/*.wav, audio/words.json,
clips/*.mp4 with *.marks.json (video/record.py), music/theme.wav (music.py), sfx/*.wav (sfx.py).

    python video/assemble.py [--audio-only] [--check-audio]

Writes SettleUp-film.mp4 (captions burned in, for anyone watching muted), SettleUp-film-clean.mp4 with
SettleUp-film.srt (for YouTube: upload the clean one with the .srt, never the burned one with it), and a 720p copy
small enough to send to a phone. Copies the finished files to ~/Downloads.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import AUDIO, BUILD, CLIPS, OUT  # noqa: E402

FPS, SR = 30, 48000
TL = json.load(open(f"{BUILD}/timeline.json"))
SC = {s["name"]: s for s in TL["scenes"]}
FACTS = json.load(open(f"{BUILD}/facts.json"))
WORDS = json.load(open(f"{AUDIO}/words.json"))
PARTS = f"{OUT}/parts"
FONT = os.path.expanduser("~/.local/share/fonts/suresay/AtkinsonHyperlegible-Bold.ttf")
FONTDIR = os.path.dirname(FONT)
ENC = ["-an", "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS)]
MODEL = "Claude Opus 5.5" if FACTS["model"] == "claude-opus-5-5" else FACTS["model"]
CHAPTER = {"talk": "Live demo", "settle": "Live demo", "dash": "Usage, measured live"}
GDRAWN = {"story", "turn", "proof", "recap", "close"}


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def cue(lid: str) -> float:
    """When line *lid* starts, in seconds from the start of its scene."""
    for s in TL["scenes"]:
        for ln in s["lines"]:
            if ln["id"] == lid:
                return ln["start"] - s["start"]
    raise KeyError(lid)


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def chip(text: str, x: str, y: str, enable: str = "1", size: int = 30, fg: str = "0x1f2430", bg: str = "white@0.94") -> str:
    return (f"drawtext=fontfile={FONT}:text='{esc(text)}':x={x}:y={y}:fontsize={size}:fontcolor={fg}:box=1:boxcolor={bg}"
            f":boxborderw=16:enable='{enable}'")


# ---------- picture ----------

def part(src: str, a: float, b: float, dur: float, out: str, *, push=None, labels=(), tag: bool = True) -> float:
    """src[a, b] fitted into *dur* seconds: sped up (never past 3x) or slowed (never under 0.55x, then held), optionally
    pushed in on (x, y, zoom) with an eased move, labelled with drawtext filters. Returns the speed used."""
    speed = max(0.55, min(3.0, (b - a) / dur))
    vf = [f"setpts=(PTS-STARTPTS)/{speed:.4f}", f"fps={FPS}", "scale=1920:1080:flags=lanczos", "setsar=1",
          f"tpad=stop_mode=clone:stop_duration={dur + 1:.3f}", f"trim=duration={dur:.3f}"]
    if push:
        x, y, z = push
        n = max(1, int(min(dur, 1.6) * FPS))
        vf.append(f"scale=3840:2160:flags=lanczos,zoompan=z='1+{z - 1}*(1-pow(1-min(1,on/{n}),3))'"
                  f":x='max(0,min(iw-iw/zoom,{2 * x}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,{2 * y}-ih/zoom/2))'"
                  f":d=1:s=1920x1080:fps={FPS}")
    vf += list(labels)
    if tag and speed > 1.05:
        vf.append(chip(f"sped up ×{speed:.1f}", "w-tw-60", "26", size=26, fg="white", bg="0x1f2430@0.85"))
    vf.append("scale=out_range=tv,format=yuv420p")
    run("-ss", f"{max(0.0, a):.3f}", "-to", f"{b:.3f}", "-i", src, "-vf", ",".join(vf), *ENC, "-t", f"{dur:.3f}", out)
    return speed


def product_plan() -> list[tuple]:
    """(scene, src a, src b, film start in scene, dur, push, labels) for the live product, plus click times."""
    m = json.load(open(f"{CLIPS}/product.marks.json"))
    mk, bx = m["marks"], m["boxes"]
    center = lambda b, dx=0, dy=0: (b[0] + b[2] / 2 + dx, b[1] + b[3] / 2 + dy)  # noqa: E731
    plan = []
    talk, settle, dash = SC["talk"]["dur"], SC["settle"]["dur"], SC["dash"]["dur"]
    live = {k: chip(f"{v.upper()} · real output · {MODEL} via Google ADK", "(w-tw)/2", "26", size=26, fg="white", bg="0x1f2430@0.88")
            for k, v in CHAPTER.items()}
    persona = chip("Persona · You. Paid 900 for snacks. Want it settled tonight.", "(w-tw)/2", "96", "lt(t,5.5)", size=28)
    # talk: typing (d1), the wait while Claude calls the tools (d2, sped up), the reply (d3) pushed in
    t_d2, t_d3 = cue("d2"), cue("d3") - 0.3
    plan.append(("talk", mk["start"] + 1.2, mk["sent"] + 0.4, 0.0, t_d2, (470, 860, 1.25), [live["talk"], persona]))
    plan.append(("talk", mk["sent"] + 0.4, mk["reply"], t_d2, t_d3 - t_d2, None, [live["talk"]]))
    plan.append(("talk", mk["reply"], mk["reply"] + 3.0, t_d3, talk - t_d3, (*center(bx["reply"]), 1.45), [live["talk"]]))
    # settle: the click on "Who owes whom?" and the wait (e1), then the three payments, pushed in (e2)
    t_e2 = cue("e2") - 0.2
    plan.append(("settle", mk["ask"] - 0.9, mk["settled"], 0.0, t_e2, None, [live["settle"]]))
    plan.append(("settle", mk["settled"], mk["settled"] + 3.4, t_e2, settle - t_e2, (*center(bx["settle"], 120), 1.7), [live["settle"]]))
    # dash: the live counters (u1), then the request log with its latency (u2)
    t_u2 = cue("u2") - 0.2
    plan.append(("dash", mk["settled"] + 3.6, mk["reqs"], 0.0, t_u2, (*center(bx["kpis"]), 1.45), [live["dash"]]))
    plan.append(("dash", mk["reqs"], mk["end"], t_u2, dash - t_u2, (*center(bx["reqs"], -40), 1.6), [live["dash"]]))
    clicks = [("talk", 0, mk["sent"]), ("settle", 3, mk["ask"])]
    return plan, clicks


def picture() -> dict[str, float]:
    """Renders every scene to parts/<scene>.mp4 at its exact length; returns film times of the product's clicks."""
    os.makedirs(PARTS, exist_ok=True)
    plan, clicks = product_plan()
    speeds = {}
    src = f"{CLIPS}/product.mp4"
    for i, (scene, a, b, at, dur, push, labels) in enumerate(plan):
        speeds[i] = part(src, a, b, dur, f"{PARTS}/{scene}-{i}.mp4", push=push, labels=labels)
        print(f"{scene:7s} part {i}: src {a:5.1f}-{b:5.1f}s -> {dur:4.1f}s  x{speeds[i]:.2f}", flush=True)
    for scene in ("talk", "settle", "dash"):
        ids = [i for i, p in enumerate(plan) if p[0] == scene]
        concat([f"{PARTS}/{scene}-{i}.mp4" for i in ids], f"{PARTS}/{scene}.mp4", SC[scene]["dur"])
    for scene in GDRAWN | {"arch"}:
        clip = f"{CLIPS}/gfx-{scene}.mp4"
        start = json.load(open(f"{CLIPS}/gfx-{scene}.marks.json"))["marks"]["start"]
        part(clip, start, start + SC[scene]["dur"], SC[scene]["dur"], f"{PARTS}/{scene}.mp4", tag=False)
    order = [s["name"] for s in TL["scenes"]]
    concat([f"{PARTS}/{s}.mp4" for s in order], f"{PARTS}/picture.mp4", TL["total"])
    times = {}
    for scene, idx, t in clicks:
        _, a, _, at, _, _, _ = plan[idx]
        times[f"click-{scene}"] = SC[scene]["start"] + at + (t - a) / speeds[idx]
    json.dump(times, open(f"{BUILD}/clicks.json", "w"))
    return times


def concat(parts: list[str], out: str, dur: float) -> None:
    """Joins *parts* with the concat filter (it rebuilds timestamps), held or trimmed to exactly *dur* seconds."""
    inputs = [x for p in parts for x in ("-i", p)]
    chain = "".join(f"[{i}:v]" for i in range(len(parts)))
    fc = f"{chain}concat=n={len(parts)}:v=1:a=0,tpad=stop_mode=clone:stop_duration=4,trim=duration={dur:.3f},setpts=PTS-STARTPTS[v]"
    run(*inputs, "-filter_complex", fc, "-map", "[v]", *ENC, out)


# ---------- sound ----------

def read(path: str) -> np.ndarray:
    """Any audio file as float32 mono at 48 kHz."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def write(path: str, x: np.ndarray) -> None:
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def place(track: np.ndarray, clip: np.ndarray, t: float, gain_db: float = 0.0) -> None:
    i = int(t * SR)
    if i >= len(track):
        return
    seg = clip[: len(track) - i] * 10 ** (gain_db / 20)
    track[max(0, i): i + len(seg)] += seg[max(0, -i):]


def envelope(x: np.ndarray, attack: float = 0.15, release: float = 0.9) -> np.ndarray:
    """0..1, how much someone is speaking: 20 ms RMS over a gate, smoothed with the compressor's attack and release."""
    hop = int(0.02 * SR)
    n = len(x) // hop + 1
    rms = np.sqrt(np.add.reduceat(np.pad(x, (0, n * hop - len(x))) ** 2, np.arange(0, n * hop, hop)) / hop)
    on = (rms > 10 ** (-45 / 20)).astype(float)
    out, level = np.zeros(n), 0.0
    a, r = np.exp(-0.02 / attack), np.exp(-0.02 / release)
    for i, v in enumerate(on):
        level = (a if v > level else r) * level + (1 - (a if v > level else r)) * v
        out[i] = level
    return np.repeat(out, hop)[: len(x)]


def sound(clicks: dict[str, float]) -> dict[str, np.ndarray]:
    total = TL["total"]
    n = int((total + 0.5) * SR)
    voice = np.zeros(n, dtype=np.float32)
    for s in TL["scenes"]:
        for ln in s["lines"]:
            x = read(f"{AUDIO}/lines/{ln['id']}.wav")
            x *= 10 ** (-19 / 20) / max(1e-6, float(np.sqrt(np.mean(x[np.abs(x) > 0.01] ** 2))))  # each line to -19 dBFS RMS
            place(voice, x, ln["start"])
    # the music: one theme, the 2.5 kHz band dipped to leave room for speech, shaped by scene, ducked under the voice
    run("-i", f"{OUT}/music/theme.wav", "-af", "equalizer=f=2500:t=q:w=1.2:g=-4", "-ar", str(SR), "-ac", "1", f"{BUILD}/theme-eq.wav")
    music = read(f"{BUILD}/theme-eq.wav")[:n]
    music = np.pad(music, (0, n - len(music)))
    t = np.arange(n) / SR
    turn, recap, close = SC["turn"]["start"], SC["recap"]["start"], SC["close"]["start"]
    endcard = close + cue("c2") - 0.2
    shape = np.ones(n)
    shape = np.where(t > turn, 1 - 0.3 * np.clip((t - turn) / 4, 0, 1), shape)  # eased down once the narration runs on
    shape = np.where(t > recap - 1.5, 0.7 - 0.2 * np.clip((t - recap + 1.5) / 1.5, 0, 1), shape)  # the theme itself lifts here
    shape = np.where(t > close, 0.6, shape)
    shape = np.where(t > endcard, 0.6 + 0.35 * np.clip((t - endcard) / 1.0, 0, 1), shape)  # up on the end card
    shape *= np.clip(t / 2.0, 0, 1) * np.clip((total + 0.5 - t) / 3.5, 0, 1)  # fade in 2 s, out over the last few
    duck = 1 - 0.72 * envelope(voice)  # about 11 dB down while someone speaks
    music_out = music * shape * duck * 10 ** (2 / 20)
    # effects, one track in numpy
    fx = {k: read(f"{OUT}/sfx/{k}.wav") for k in ("whoosh", "click", "riser", "hit")}
    sfx = np.zeros(n, dtype=np.float32)
    for s in TL["scenes"][1:]:
        place(sfx, fx["whoosh"], s["start"] - 0.3, -16)
    for v in clicks.values():
        place(sfx, fx["click"], v, -10)
    r1 = SC["recap"]["start"] + cue("r1")
    place(sfx, fx["riser"], r1 - 1.5, -12)
    for lid in ("r1", "r2", "r3", "r4", "r5"):
        place(sfx, fx["hit"], SC["recap"]["start"] + cue(lid), -14)
    place(sfx, fx["hit"], SC["proof"]["start"] + cue("p1") + 0.2, -16)
    place(sfx, fx["hit"], endcard, -12)
    return {"voice": voice, "music": music_out.astype(np.float32), "sfx": sfx}


def mix(stems: dict[str, np.ndarray]) -> str:
    for k, v in stems.items():
        write(f"{BUILD}/stem-{k}.wav", v)
    write(f"{BUILD}/mix-raw.wav", stems["voice"] + stems["music"] + stems["sfx"])
    # two-pass loudness: measure, then a linear gain to -14 LUFS, true peak under -1.5 dBTP
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", f"{BUILD}/mix-raw.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(re.findall(r"\{[^{}]*\}", m)[-1])
    out = f"{BUILD}/mix.wav"
    run("-i", f"{BUILD}/mix-raw.wav", "-af",
        f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
        f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,alimiter=limit=0.79:level=false",
        "-ar", str(SR), "-ac", "2", f"{BUILD}/mix-lin.wav")
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", f"{BUILD}/mix-lin.wav", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    j = json.loads(re.findall(r"\{[^{}]*\}", m)[-1])
    gain = min(-14 - float(j["input_i"]), -1.5 - float(j["input_tp"]))
    run("-i", f"{BUILD}/mix-lin.wav", "-af", f"volume={gain:.2f}dB", out)
    print(f"mix: {j['input_i']} LUFS, true peak {j['input_tp']} dBTP; +{gain:.2f} dB")
    return out


def check_audio(stems: dict[str, np.ndarray]) -> None:
    """How far the music sits under the voice, per scene, while someone is speaking."""
    env = envelope(stems["voice"])
    print("scene    voice dBFS  music dBFS  gap dB")
    for s in TL["scenes"]:
        a, b = int(s["start"] * SR), int((s["start"] + s["dur"]) * SR)
        speaking = env[a:b] > 0.8
        if speaking.sum() < SR // 2:
            continue
        v = db(float(np.sqrt(np.mean(stems["voice"][a:b][speaking] ** 2))))
        mu = db(float(np.sqrt(np.mean(stems["music"][a:b][speaking] ** 2))))
        print(f"{s['name']:8s} {v:9.1f}  {mu:10.1f}  {v - mu:6.1f}")


# ---------- captions ----------

def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def caption_words(ln: dict, scene_start: float) -> list[tuple[str, float, float]]:
    """The caption's own words (real spelling), timed by Whisper's words on the spoken take via difflib."""
    cap = ln["caption"].split()
    heard = WORDS.get(ln["id"], [])
    sm = difflib.SequenceMatcher(None, [norm(w) for w in cap], [norm(w) for w, *_ in heard], autojunk=False)
    times: list[float | None] = [None] * len(cap)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = heard[blk.b + k][1]
    # unmatched words (numbers said in words, "SettleUp" heard as two) share the gap between matched neighbours
    end = ln["dur"]
    for i in range(len(cap)):
        if times[i] is None:
            j = i
            while j < len(cap) and times[j] is None:
                j += 1
            lo = times[i - 1] if i else 0.0
            hi = times[j] if j < len(cap) else end - 0.2
            for k in range(i, j):
                times[k] = lo + (hi - lo) * (k - i + (1 if i else 0)) / (j - i + 1)
    times = [max(0.0, min(end, t)) for t in times]
    for i in range(1, len(times)):
        times[i] = max(times[i], times[i - 1] + 0.04)
    base = ln["start"]
    return [(w, base + t, base + (times[i + 1] if i + 1 < len(cap) else end)) for i, (w, t) in enumerate(zip(cap, times))]


def phrases(words: list[tuple[str, float, float]]) -> list[list[tuple[str, float, float]]]:
    """2-7 words a phrase, broken at punctuation, about 30 characters at most."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x[0] for x in cur)
        if (re.search(r"[.,:;?!]$", w[0]) and len(cur) >= 2) or len(cur) >= 7 or len(text) >= 30:
            out.append(cur)
            cur = []
    if cur:
        if out and len(cur) == 1:
            out[-1].extend(cur)
        else:
            out.append(cur)
    return out


def ts(t: float, srt: bool = False) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",") if srt else f"{int(h)}:{int(m):02d}:{s:05.2f}"


def captions() -> tuple[str, str]:
    """A karaoke .ass (the spoken word in the accent colour with a small pop; no box) and a phrase .srt."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Atkinson Hyperlegible,64,&H00FFFFFF,&H00FFFFFF,&H66000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,120,120,78,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    accent = "&H00F48542&"  # #4285f4 as ASS BGR
    ass, srt, k = [head], [], 1
    for s in TL["scenes"]:
        for ln in s["lines"]:
            burn = s["name"] != "turn"
            ps = phrases(caption_words(ln, s["start"]))
            for pi, p in enumerate(ps):
                end = ps[pi + 1][0][1] if pi + 1 < len(ps) else p[-1][2] + 0.25
                srt.append(f"{k}\n{ts(p[0][1], True)} --> {ts(end, True)}\n{' '.join(w for w, *_ in p)}\n")
                k += 1
                for wi, (w, a, _) in enumerate(p):
                    b = p[wi + 1][1] if wi + 1 < len(p) else end
                    text = " ".join(
                        (f"{{\\c{accent}\\fscx108\\fscy108}}{x}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}" if j == wi else x)
                        for j, (x, *_) in enumerate(p))
                    if burn:
                        ass.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{text}\n")
    a_path, s_path = f"{BUILD}/captions.ass", f"{OUT}/SettleUp-film.srt"
    open(a_path, "w").write("".join(ass))
    open(s_path, "w").write("\n".join(srt))
    return a_path, s_path


# ---------- the film ----------

def main(audio_only: bool, check: bool) -> None:
    if not os.path.exists(f"{OUT}/grad.png"):
        # a soft dark gradient along the bottom keeps white captions readable over the light UI
        run("-f", "lavfi", "-i", "color=black@0:s=1920x340,format=rgba", "-vf",
            "geq=r=0:g=0:b=0:a='170*pow(Y/340,1.6)'", "-frames:v", "1", f"{OUT}/grad.png")
    clicks = json.load(open(f"{BUILD}/clicks.json")) if audio_only else picture()
    stems = sound(clicks)
    if check:
        check_audio(stems)
    mixed = mix(stems)
    ass, srt = captions()
    pic = f"{PARTS}/picture.mp4"
    final, clean = f"{OUT}/SettleUp-film.mp4", f"{OUT}/SettleUp-film-clean.mp4"
    total = f"{TL['total'] + 0.5:.3f}"
    grad = f"[0:v]tpad=stop_mode=clone:stop_duration=1[p];[p][2:v]overlay=0:H-h:enable='not(between(t,{SC['turn']['start']},{SC['turn']['start'] + SC['turn']['dur']}))'"
    common = ["-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "film", "-pix_fmt", "yuv420p",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
              "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", total]
    run("-i", pic, "-i", mixed, "-loop", "1", "-i", f"{OUT}/grad.png", "-filter_complex",
        f"{grad},ass={ass}:fontsdir={FONTDIR},format=yuv420p[v]", *common, final)
    run("-i", pic, "-i", mixed, "-filter_complex", "[0:v]tpad=stop_mode=clone:stop_duration=1,format=yuv420p[v]", *common, clean)
    small = f"{OUT}/SettleUp-film-720p.mp4"
    run("-i", final, "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", small)
    dl = os.path.expanduser("~/Downloads")
    for f in (final, small, srt):
        shutil.copy(f, dl)
    for f in (final, clean, small):
        print(f"{os.path.basename(f)}: {os.path.getsize(f) / 1e6:.1f} MB")


if __name__ == "__main__":
    main("--audio-only" in sys.argv, "--check-audio" in sys.argv)
