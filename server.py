"""Web app: chat with the SettleUp agent and watch its usage live."""

from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from settle_agent.agent import HAS_KEY, root_agent

ROOT = Path(__file__).parent
DB = ROOT / "usage.db"
APP_NAME = "settleup"

runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
app = FastAPI(title="SettleUp Agent")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, ts REAL, session_id TEXT, prompt TEXT, reply TEXT,
        latency_ms REAL, llm_calls INT, prompt_tokens INT, output_tokens INT,
        tools TEXT, model TEXT, ok INT)""")
    return conn


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.post("/api/chat")
async def chat(body: ChatIn):
    user_id = "web"
    session_id = body.session_id
    if not session_id or not await runner.session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    ):
        session = await runner.session_service.create_session(app_name=APP_NAME, user_id=user_id)
        session_id = session.id

    started = time.perf_counter()
    reply, tools, llm_calls, p_tok, o_tok, model, ok = [], [], 0, 0, 0, "", True
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=body.message)]),
        ):
            if event.usage_metadata:
                llm_calls += 1
                p_tok += event.usage_metadata.prompt_token_count or 0
                o_tok += event.usage_metadata.candidates_token_count or 0
                model = event.model_version or model
            for part in (event.content.parts if event.content else None) or []:
                if part.function_call:
                    tools.append({"name": part.function_call.name, "args": dict(part.function_call.args or {})})
                elif part.text and not part.thought and event.is_final_response():
                    reply.append(part.text)
    except Exception as exc:  # surfaced in the UI and the usage log
        ok, reply = False, [f"Agent error: {exc}"]

    latency_ms = (time.perf_counter() - started) * 1000
    text = "\n".join(reply).strip()
    row = {
        "id": uuid.uuid4().hex, "ts": time.time(), "session_id": session_id,
        "prompt": body.message, "reply": text, "latency_ms": round(latency_ms, 1),
        "llm_calls": llm_calls, "prompt_tokens": p_tok, "output_tokens": o_tok,
        "tools": json.dumps([t["name"] for t in tools]),
        "model": model or str(getattr(root_agent.model, "model", root_agent.model)), "ok": int(ok),
    }
    with db() as conn:
        conn.execute(f"INSERT INTO requests VALUES ({','.join('?' * len(row))})", tuple(row.values()))

    session = await runner.session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    return {**row, "tools": tools, "expenses": session.state.get("expenses", [])}


@app.get("/api/usage")
def usage():
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM requests ORDER BY ts DESC LIMIT 50")]
        agg = dict(conn.execute("""SELECT COUNT(*) requests, COUNT(DISTINCT session_id) sessions,
            COALESCE(SUM(prompt_tokens),0) prompt_tokens, COALESCE(SUM(output_tokens),0) output_tokens,
            COALESCE(AVG(latency_ms),0) avg_latency_ms, COALESCE(SUM(llm_calls),0) llm_calls,
            COALESCE(SUM(1-ok),0) errors FROM requests""").fetchone())
    tool_counts: dict[str, int] = {}
    for r in rows:
        r["tools"] = json.loads(r["tools"])
        for t in r["tools"]:
            tool_counts[t] = tool_counts.get(t, 0) + 1
    lat = sorted(r["latency_ms"] for r in rows)
    agg["p95_latency_ms"] = lat[max(0, math.ceil(len(lat) * 0.95) - 1)] if lat else 0
    return {"summary": agg, "tool_counts": tool_counts, "recent": rows,
            "model": str(getattr(root_agent.model, "model", root_agent.model)), "live_model": HAS_KEY}


@app.post("/api/usage/reset")
def reset_usage():
    with db() as conn:
        conn.execute("DELETE FROM requests")
    return {"status": "cleared"}
