# The demo film, built from code

Every part of the film is rebuilt from this folder: change a line of narration or a screen, rerun, done. Every number
it says comes from the live run and the repo at build time (`facts.py`). Outputs go to `~/Videos/settleup`, outside
the repo; the finished film is also copied to `~/Downloads`.

```sh
.venv/bin/uvicorn server:app --port 8765           # the app, on Claude (ANTHROPIC_API_KEY in .env)
.venv/bin/python video/record.py product           # the live take: one sentence, then "Who owes whom?"
.venv/bin/python video/facts.py                    # the numbers, from that run, the tests and ledger.py
python3 video/synth.py                             # the narration: Chatterbox, best of three takes by Whisper
.venv/bin/python video/timeline.py                 # where every line and scene falls, from the takes' real lengths
~/Videos/debrief/.venv-music/bin/python video/music.py   # the piano theme, composed to the timeline
python3 video/sfx.py                               # whoosh, click, riser, hit, synthesised
for s in story turn arch proof recap close; do .venv/bin/python video/record.py gfx-$s; done
.venv/bin/python video/assemble.py --check-audio   # the film, a clean copy with its .srt, and a 720p copy
```

`synth.py` needs a Python with `chatterbox-tts` and `faster-whisper` (the system `python3` here); the rest runs in the
project's `.venv`. The plan for every beat is in [storyboard.md](storyboard.md); what the film is made of, and the
licences, in [LICENSES.md](LICENSES.md).
