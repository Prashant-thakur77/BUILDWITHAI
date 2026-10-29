"""Where the film's files live. Everything heavy goes to ~/Videos/settleup, outside the repo."""

import os

VIDEO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(VIDEO)
OUT = os.path.expanduser("~/Videos/settleup")
BUILD = f"{OUT}/build"
AUDIO = f"{OUT}/audio"
CLIPS = f"{OUT}/clips"
SITE = os.environ.get("SETTLE_SITE", "http://127.0.0.1:8765")
