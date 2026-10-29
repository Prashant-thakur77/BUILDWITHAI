# SettleUp film: storyboard

One row per beat. The narration lines themselves live in `narration.py` (numbers filled from `facts.json`); this
table is the plan for what is on screen, how it moves, which words pop, and what the sound does.

| # | Scene | Narration (short) | On screen | Motion | Caption emphasis | Sound |
|---|---|---|---|---|---|---|
| 1 | story | "It's the last night of a Goa trip. Four friends, one group chat, and a pile of bills." | Warm night, string-light bokeh, a phone with the "Goa trip" group chat; place and time in mono at top left | Slow push 1.00→1.05, bubbles rise in (12 px + fade) | Goa, Four | Piano alone, sparse, minor-leaning |
| 2 | story | "Who paid for dinner? Who owes for the cab? Is it 675, or 725?" | Kabir asks what he owes; a notes card of sums; the sums get crossed out in red | Card rises, strikes draw on left to right | 675, 725 | Same theme |
| 3 | story | "Today's apps want a form for every single bill." | Three "Add an expense" forms fan out over the notes | Staggered rise, 0.25 s apart | form | Same |
| 4 | story | "And the worst part: the friend who paid the most is the one who has to ask." | Room dims to 45%; Arjun "typing…", then "hey guys… so, about the money" | Dim over 1.2 s | worst, ask | A beat of music after the line |
| 5 | turn | "This is SettleUp. Say who paid, in plain English. Get the fewest payments that settle everyone." | Kinetic type, one word per spoken word; the four-dot wordmark | Each word lands as it is said; phrases replace each other | SettleUp, plain English, fewest payments | Theme turns major (C G Am F), moving eighths |
| 6 | talk | "You type the whole trip as one sentence…" | The live app (1920×1080), persona chip "You. Paid 900 for snacks", LIVE chip | Eased push 1.0→1.25 on the input as the sentence is typed | one sentence | Click on Send |
| 7 | talk | "Underneath, a Google ADK agent hands it to Claude, which calls one tool per expense." | The wait for Claude, sped up with a "sped up ×N" tag | Speed ramp over the dead wait only | Google ADK, Claude, one tool | |
| 8 | talk | "3 expenses, logged. And Claude tells you how it read 'everyone'." | Claude's real reply with the add_expense ×3 chip; the ledger fills | Push 1.0→1.45 on the reply | 3 expenses, everyone | |
| 9 | settle | "Then ask who owes whom." / "Plain code does the maths… Three payments settle all 2,700." | Click on "Who owes whom?", the real settle_up reply | Push 1.0→1.7 on the three payments | to the cent, Three payments | Click; reveal |
| 10 | dash | "Every request is measured live…" / "That first reply took 7.3 seconds… Speed is the next thing to fix." | The live usage dashboard: KPIs, then the request log | Push on KPIs, then cut to a push on the request log | measured live, 7.3 seconds | |
| 11 | arch | "Under the hood": FastAPI → ADK Runner → Claude → Tools → Ledger, a −500 packet refused | `three.html`: exploded 3D stack, packets rising, satellites (Anthropic API, session state, usage log) | Each slab rises on its word; slow ~20° orbit; red packet stops at Tools | FastAPI, Agent Development Kit, Claude, refused, exact cents | Whoosh in |
| 12 | proof | "4 of 4 tests pass…" / "Four people, three payments…" | Three stat cards that count up (with their source), a who-pays-whom diagram drawn on | Cards pop one at a time; arrows draw on (stroke-dashoffset) | 4 of 4, three payments | Soft hit as the first card lands |
| 13 | recap | Five short lines, the last one the number | Lines stack on the left (current one blue, earlier ones 40%); a real screenshot from the film behind each, pushing in 8%; bars for the payments on the last line | 70 ms white flash per line | each line's key words | Riser into it, a soft hit per line, the theme doubles to sixteenths and an octave up |
| 14 | close | "Same night. One sentence, three payments, and nobody has to ask." | The same night and phone, now resolved: the SettleUp card in the chat, "sent 725", "that was easy" | Same slow push as the opening | nobody has to ask | Theme settles back |
| 15 | close | "SettleUp. Built with Google's Agent Development Kit and Claude." | End card: wordmark, tagline, "Built with Google ADK + Claude Opus 5.5", "Working prototype · runs locally", call to action | Fade up, held ~5 s | SettleUp | Music up 1–4 dB, long resolving chord, hit on the card |

Honesty on screen: the live scenes carry a "LIVE · real output" chip; the persona is labelled "Persona"; speed-ups are
tagged; the drawn chat in the story is an illustration, not a product screen.
