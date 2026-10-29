# SettleUp Agent

A small AI agent built with Google's Agent Development Kit (ADK). It solves a common problem: splitting group expenses (trips, dinners, flat bills).
Describe who paid what in plain English. The agent logs each expense with tools and works out the fewest payments that settle everyone up.

```
You:   Arjun paid 1200 for dinner for everyone, Riya paid 600 for the cab split with Kabir and me,
       and I paid 900 for hotel snacks for all
Agent: Logged dinner / cab / hotel snacks  (add_expense ×3)
You:   Who owes whom?
Agent: Kabir -> Arjun: 675.00, Kabir -> Me: 50.00, Riya -> Me: 125.00  (settle_up)
```

## Pieces

| Path | What it is |
|---|---|
| `settle_agent/agent.py` | ADK `Agent` (`root_agent`) + 4 tools: `add_expense`, `list_expenses`, `settle_up`, `reset_expenses`. Expenses live in ADK session state. |
| `settle_agent/ledger.py` | Exact math in cents: balances, plus greedy min-payment settlement (≤ n−1 payments). The LLM never does arithmetic. |
| `settle_agent/offline_model.py` | Rule-based `BaseLlm` used **only when no API key is set**, so the app still runs end to end. |
| `server.py` | FastAPI app. Runs the agent through ADK's `InMemoryRunner` and logs usage for every request (latency, model calls, tokens, tool calls) to SQLite. |
| `web/index.html` | The website: chat + ledger on the left, live usage dashboard on the right. |
| `record_demo.py` | Uses Playwright + Chromium to record a demo video to `~/Downloads/settleup-agent-demo.mp4`. |

## Run

```bash
uv venv .venv -p 3.11 && uv pip install --python .venv/bin/python -r requirements.txt
echo 'ANTHROPIC_API_KEY=your-key' > .env     # Claude (default when set), or GOOGLE_API_KEY=... for Gemini
.venv/bin/uvicorn server:app --port 8765    # open http://127.0.0.1:8765
```

- Model: with `ANTHROPIC_API_KEY`, `claude-opus-5-5` at low effort through ADK's `AnthropicLlm` (the official
  `anthropic` SDK); with `GOOGLE_API_KEY`, `gemini-3.5-flash`. Override with `SETTLE_MODEL=...` / `SETTLE_EFFORT=...`.
- Without any key, the header shows `offline-demo (no API key)` and a rule-based stand-in runs. Token counts are then estimates.
- The demo film is built entirely from code in [video/](video/README.md).
- ADK's own dev UI also works: `.venv/bin/adk web` from this folder, then pick `settle_agent`.
- Tests: `.venv/bin/python -m pytest -q`
- Re-record the video while the server is running: `.venv/bin/python record_demo.py`
