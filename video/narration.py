"""The film's narration as data, every number read from facts.json.

Each line: (scene, id, caption, spoken, exaggeration, cfg_weight). The caption is what the screen shows; the spoken
text is what the voice reads (numbers in words, "A D K", "Fast A P I"). The story reads slower (lower cfg); the
product is brisker; the recap is the most energetic.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BUILD  # noqa: E402

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n: int) -> str:
    """A whole number below a million as the voice should say it."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + words(rest))
    rest = n % 1000
    return words(n // 1000) + " thousand" + ("" if rest == 0 else (" and " if rest < 100 else " ") + words(rest))


def decimal(x: float) -> str:
    whole, frac = f"{x:.1f}".split(".")
    return words(int(whole)) + ("" if frac == "0" else " point " + ONES[int(frac)])


STORY = (0.6, 0.3)
PRODUCT = (0.7, 0.4)
RECAP = (0.9, 0.32)


def load() -> list[tuple[str, str, str, str, float, float]]:
    f = json.load(open(f"{BUILD}/facts.json"))
    n, pays, total = f["people"], f["payments"], int(f["total_spent"].replace(",", ""))
    first = int(float(f["pays"][0]["amount"]))
    debtor = f["pays"][0]["from"]
    owed = int(sum(float(p["amount"]) for p in f["pays"] if p["from"] == debtor))
    model = "Claude Opus 5.5" if f["model"] == "claude-opus-5-5" else f["model"]
    model_spoken = "Claude Opus five point five" if f["model"] == "claude-opus-5-5" else f["model"]
    N, P = words(n).capitalize(), words(pays).capitalize()
    return [
        # 1. The opening: one night, one group, the problem, done by about 0:30
        ("story", "s1", f"It’s the last night of a Goa trip. {N} friends, one group chat, and a pile of bills.",
         f"It's the last night of a Goa trip. {N} friends, one group chat, and a pile of bills.", *STORY),
        ("story", "s2", f"Who paid for dinner? Who owes for the cab? Is it {first}, or {owed}?",
         f"Who paid for dinner? Who owes for the cab? Is it {words(first)}, or {words(owed)}?", *STORY),
        ("story", "s3", "Today’s apps want a form for every single bill.",
         "Today's apps want a form, for every single bill.", *STORY),
        ("story", "s4", "And the worst part: the friend who paid the most is the one who has to ask.",
         "And the worst part? The friend who paid the most, is the one who has to ask.", *STORY),
        # 2. The turn
        ("turn", "t1", "This is SettleUp. Say who paid, in plain English. Get the fewest payments that settle everyone.",
         "This is Settle Up. Say who paid, in plain English. Get the fewest payments that settle everyone.", *PRODUCT),
        # 3. The live product, simple to surprising
        ("talk", "d1", "You type the whole trip as one sentence, the way you’d text a friend.",
         "You type the whole trip as one sentence, the way you'd text a friend.", *PRODUCT),
        ("talk", "d2", "Underneath, a Google ADK agent hands it to Claude, which calls one tool per expense.",
         "Underneath, a Google A D K agent hands it to Claude, which calls one tool per expense.", *PRODUCT),
        ("talk", "d3", f"{f['tools_first']} expenses, logged. And Claude tells you how it read “everyone”.",
         f"{words(f['tools_first']).capitalize()} expenses, logged. And Claude tells you how it read the word, everyone.", *PRODUCT),
        ("settle", "e1", "Then ask who owes whom.", "Then, ask who owes whom.", *PRODUCT),
        ("settle", "e2", f"Plain code does the maths, to the cent. {P} payments settle all {f['total_spent']}.",
         f"Plain code does the maths, to the cent. {P} payments settle all {words(total)}.", *PRODUCT),
        ("dash", "u1", "Every request is measured live: how long it took, the tokens, and every tool it called.",
         "Every request is measured live. How long it took, the tokens, and every tool it called.", *PRODUCT),
        ("dash", "u2", f"That first reply took {f['latency_add_s']} seconds on {model}. Speed is the next thing to fix.",
         f"That first reply took {decimal(f['latency_add_s'])} seconds on {model_spoken}. Speed is the next thing to fix.", *PRODUCT),
        # 4. Under the hood: the 3D stack
        ("arch", "a1", "Your sentence reaches a small FastAPI server, which times every request.",
         "Your sentence reaches a small Fast A P I server, which times every request.", *PRODUCT),
        ("arch", "a2", "Google’s Agent Development Kit runs the agent, and keeps the ledger in its session.",
         "Google's Agent Development Kit runs the agent, and keeps the ledger in its session.", *PRODUCT),
        ("arch", "a3", "Claude reads the words and picks the tools. It never does the arithmetic.",
         "Claude reads the words, and picks the tools. It never does the arithmetic.", *PRODUCT),
        ("arch", "a4", "A bad amount, like minus 500, is refused by the tool. Nothing is recorded.",
         "A bad amount, like minus five hundred, is refused by the tool. Nothing is recorded.", *PRODUCT),
        ("arch", "a5", "Only then does the ledger do the maths, in exact cents, and find the fewest payments.",
         "Only then does the ledger do the maths, in exact cents, and find the fewest payments.", *PRODUCT),
        # 5. Proof in numbers
        ("proof", "p1", f"{f['tests_passed']} of {f['tests_passed'] + f['tests_failed']} tests pass, including the full chat loop on the live model.",
         f"{words(f['tests_passed']).capitalize()} of {words(f['tests_passed'] + f['tests_failed'])} tests pass, including the full chat loop on the live model.", *PRODUCT),
        ("proof", "p2", f"{N} people, {words(pays)} payments. A group never needs more than one fewer payment than it has people.",
         f"{N} people, {words(pays)} payments. A group never needs more than one fewer payment than it has people.", *PRODUCT),
        # 6. The fast recap
        ("recap", "r1", "One sentence in. Every expense logged.", "One sentence in. Every expense, logged.", *RECAP),
        ("recap", "r2", "Claude picks the tools. Code does the maths.", "Claude picks the tools. Code does the maths.", *RECAP),
        ("recap", "r3", "Fewest payments, exact to the cent.", "Fewest payments, exact to the cent.", *RECAP),
        ("recap", "r4", "Every request measured, live.", "Every request, measured live.", *RECAP),
        ("recap", "r5", f"{P} payments. Everyone settled.", f"{P} payments. Everyone, settled.", *RECAP),
        # 7. Back to the same night
        ("close", "c1", f"Same night. One sentence, {words(pays)} payments, and nobody has to ask.",
         f"Same night. One sentence, {words(pays)} payments, and nobody has to ask.", *STORY),
        ("close", "c2", "SettleUp. Built with Claude and Google’s Agent Development Kit.",
         "Settle Up. Built with Claude, and Google's Agent Development Kit.", *PRODUCT),
    ]


def _at(words_: dict, cues: dict, lid: str, pattern: str, after: float = 0.0) -> float:
    """Scene time of the first word in *lid* matching *pattern*; the line's start (+after) if Whisper missed it."""
    for w, t in words_.get(lid, []):
        if re.fullmatch(pattern, re.sub(r"[^a-z0-9]", "", w.lower())):
            return t
    return cues[lid] + after


def arch_cues(cues: dict, words_: dict) -> dict:
    """The 3D stack's beats, each landing on the word that names it."""
    return {
        "l1": cues["a1"],
        "l2": _at(words_, cues, "a1", r"fast|api|a", 1.6),
        "l3": cues["a2"],
        "sat": _at(words_, cues, "a2", r"session", 3.5),
        "l4": _at(words_, cues, "a3", r"claude"),
        "l5": _at(words_, cues, "a3", r"tools", 1.6),
        # the red packet rises for about 1.86 s before it hits the Tools slab: land the hit on "refused"
        "danger": _at(words_, cues, "a4", r"refused", 2.2) - 1.86,
        "l6": _at(words_, cues, "a5", r"ledger", 0.6),
        "result": _at(words_, cues, "a5", r"fewest", 3.0),
    }


if __name__ == "__main__":
    lines = load()
    wc = sum(len(spoken.split()) for _, _, _, spoken, *_ in lines)
    for scene, lid, caption, *_ in lines:
        print(f"{scene:7s} {lid:3s} {caption}")
    print(f"{len(lines)} lines, {wc} spoken words (~{wc / 2.6:.0f} s of voice)")
