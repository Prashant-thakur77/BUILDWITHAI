"""Rule-based stand-in for Gemini, used only when no GOOGLE_API_KEY is set.

It speaks the same protocol as a real model (function calls in, function
responses back), so the ADK runner, tools, session state and usage tracking
all run for real. Only the language understanding is a regex.
"""

from __future__ import annotations

import re
from typing import AsyncGenerator

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

_START = re.compile(r"\b([A-Z][a-z]+|I)\s+(?:paid|spent|covered)\b")
_EXPENSE = re.compile(
    r"^(?P<payer>[A-Z][a-z]+|I)\s+(?:paid|spent|covered)\s+(?:rs\.?\s*|₹|\$)?"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?:rs|rupees|bucks)?\s*(?:for|on)\s+(?:the\s+|a\s+|an\s+)?"
    r"(?P<desc>[\w ]+?)"
    r"(?:\s*,?\s*(?:split\s+(?:with|between|among)|shared\s+with|for)\s+(?P<people>.+?))?[\s.,;!]*$",
    re.I,
)
_EVERYONE = re.compile(r"\b(everyone|everybody|all of us|all|the group)\b", re.I)


def _name(raw: str) -> str:
    raw = raw.strip(" .,!")
    return "Me" if raw.lower() in {"i", "me", "myself"} else raw.title()


def _known_people(contents: list[types.Content]) -> list[str]:
    people: set[str] = set()
    for c in contents:
        for p in c.parts or []:
            if p.function_call and p.function_call.name == "add_expense":
                args = p.function_call.args or {}
                people.add(args.get("payer", ""))
                people.update(args.get("participants", []))
    return sorted(people - {""})


def _parse_expenses(text: str, known: list[str]) -> list[dict]:
    starts = [m.start() for m in _START.finditer(text)]
    clauses = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    out, everyone = [], set(known)
    for clause in clauses:
        clause = re.sub(r"[\s,;.]*(and|then|also)?[\s,;.]*$", "", clause.strip(), flags=re.I)
        m = _EXPENSE.match(clause)
        if not m:
            continue
        payer = _name(m["payer"])
        people_raw = m["people"] or ""
        people = None  # None = "everyone", resolved once all names are known
        if people_raw and not _EVERYONE.search(people_raw):
            people = {_name(p) for p in re.split(r",|\band\b|&", people_raw) if p.strip()} | {payer}
            everyone |= people
        everyone.add(payer)
        out.append({
            "payer": payer,
            "amount": float(m["amount"].replace(",", "")),
            "participants": people,
            "description": m["desc"].strip().lower(),
        })
    for e in out:
        e["participants"] = sorted(e["participants"] or everyone)
    return out


def _money(x: float) -> str:
    return f"{x:,.2f}"


def _summarise(responses: list[types.FunctionResponse]) -> str:
    lines = []
    for r in responses:
        data = r.response or {}
        if r.name == "add_expense" and data.get("status") == "ok":
            e = data["expense"]
            lines.append(f"Logged {e['description']}: {e['payer']} paid {_money(e['amount'])}, "
                         f"split {len(e['participants'])} ways ({', '.join(e['participants'])}).")
        elif r.name == "settle_up":
            pays = data.get("payments", [])
            if not pays:
                lines.append("Everyone is square. Nothing to settle.")
            else:
                lines.append(f"Total spent: {_money(data['total_spent'])}. "
                             f"{len(pays)} payment{' settles' if len(pays) == 1 else 's settle'} everything:")
                lines += [f"{p['from']} -> {p['to']}: {_money(p['amount'])}" for p in pays]
        elif r.name == "list_expenses":
            for e in data.get("expenses", []):
                lines.append(f"- {e['description']}: {e['payer']} paid {_money(e['amount'])}")
            for person, bal in data.get("balances", {}).items():
                lines.append(f"{person}: {'+' if bal >= 0 else ''}{_money(bal)}")
            lines = lines or ["No expenses yet."]
        elif r.name == "reset_expenses":
            lines.append("Cleared. Ready for a new group.")
        else:
            lines.append(str(data.get("message", data)))
    return "\n".join(lines)


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _part_text(p: types.Part) -> str:
    if p.text:
        return p.text
    call = p.function_call or p.function_response
    return call.model_dump_json(exclude_none=True) if call else ""


class OfflineSettleModel(BaseLlm):
    model: str = "offline-demo (no API key)"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        contents = llm_request.contents or []
        last = contents[-1] if contents else types.Content(role="user", parts=[])
        responses = [p.function_response for p in last.parts or [] if p.function_response]
        user_text = " ".join(p.text for p in last.parts or [] if p.text)

        if responses:
            parts = [types.Part(text=_summarise(responses))]
        elif re.search(r"\b(settle|owe|owes|who pays|summary|split it|square)\b", user_text, re.I):
            parts = [types.Part(function_call=types.FunctionCall(name="settle_up", args={}))]
        elif re.search(r"\b(reset|clear|start over|new trip)\b", user_text, re.I):
            parts = [types.Part(function_call=types.FunctionCall(name="reset_expenses", args={}))]
        elif re.search(r"\b(list|show|balances?)\b", user_text, re.I):
            parts = [types.Part(function_call=types.FunctionCall(name="list_expenses", args={}))]
        else:
            expenses = _parse_expenses(user_text, _known_people(contents))
            parts = [types.Part(function_call=types.FunctionCall(name="add_expense", args=e))
                     for e in expenses] or [types.Part(text=(
                         'Tell me who paid what, e.g. "Riya paid 1200 for dinner for everyone", '
                         'then ask "who owes whom?".'))]

        # Rough chars/4 estimate so the dashboard has numbers; real tokens need Gemini.
        system = str(llm_request.config.system_instruction or "") if llm_request.config else ""
        prompt_tokens = _tokens(system + "".join(_part_text(p) for c in contents for p in c.parts or []))
        output_tokens = _tokens("".join(_part_text(p) for p in parts))
        yield LlmResponse(
            content=types.Content(role="model", parts=parts),
            model_version=self.model,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=prompt_tokens,
                candidates_token_count=output_tokens,
                total_token_count=prompt_tokens + output_tokens,
            ),
        )
