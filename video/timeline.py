"""Where every line starts and how long every scene runs, computed from the chosen takes' real durations.

    python video/timeline.py  ->  ~/Videos/settleup/build/timeline.json
    {"scenes": [{name, start, dur, lines: [{id, start, dur, caption}]}], "total"}
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from narration import load  # noqa: E402
from paths import AUDIO, BUILD  # noqa: E402

# scene: (lead-in before its first line, gap between its lines, hold after its last line)
PACING = {
    "story": (1.0, 0.7, 0.6),   # the night: room to breathe
    "turn": (0.3, 0.5, 1.2),    # the wordmark lands, then holds
    "talk": (0.3, 0.55, 0.8),
    "settle": (0.2, 0.6, 1.8),  # hold on the three payments
    "dash": (0.3, 0.6, 0.9),
    "arch": (0.6, 0.55, 2.2),   # the result chip glows before the cut
    "proof": (0.4, 0.65, 1.4),
    "recap": (1.5, 0.55, 0.5),  # the riser lands on the first line
    "close": (0.6, 0.8, 5.0),   # the end card holds with the music
}
# extra room after a line, where the picture carries the moment
EXTRA_AFTER = {"s2": 0.3, "d2": 0.4, "e1": 0.6}


def main() -> dict:
    durs = {k: v["s"] for k, v in json.load(open(f"{AUDIO}/lines.json")).items()}
    lines = load()
    scenes, t = [], 0.0
    for name in dict.fromkeys(scene for scene, *_ in lines):
        lead, gap, hold = PACING[name]
        start, out = t, []
        t += lead
        for scene, lid, caption, *_ in lines:
            if scene != name:
                continue
            out.append({"id": lid, "start": round(t, 3), "dur": durs[lid], "caption": caption})
            t += durs[lid] + gap + EXTRA_AFTER.get(lid, 0.0)
        t += hold - gap
        scenes.append({"name": name, "start": round(start, 3), "dur": round(t - start, 3), "lines": out})
    os.makedirs(BUILD, exist_ok=True)
    timeline = {"scenes": scenes, "total": round(t, 3)}
    json.dump(timeline, open(f"{BUILD}/timeline.json", "w"), indent=1)
    return timeline


if __name__ == "__main__":
    tl = main()
    for s in tl["scenes"]:
        print(f"{s['name']:7s} {s['start']:6.1f}s  {s['dur']:5.1f}s")
    print(f"total {tl['total']:.1f}s")
