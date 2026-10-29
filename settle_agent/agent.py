"""SettleUp: an ADK agent that splits group expenses and settles debts."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import ToolContext

from . import ledger

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

USE_CLAUDE = bool(os.getenv("ANTHROPIC_API_KEY"))
USE_GEMINI = not USE_CLAUDE and bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))
MODEL = os.getenv("SETTLE_MODEL", "claude-opus-5-5" if USE_CLAUDE else "gemini-3.5-flash")
HAS_KEY = USE_CLAUDE or USE_GEMINI


def _expenses(ctx: ToolContext) -> list[dict]:
    return list(ctx.state.get("expenses", []))


def add_expense(
    payer: str,
    amount: float,
    participants: list[str],
    description: str,
    tool_context: ToolContext,
) -> dict:
    """Records one shared expense, split equally.

    Args:
      payer: Name of the person who paid, capitalised (e.g. "Riya").
      amount: Total amount paid, as a number.
      participants: Everyone who shares this cost, INCLUDING the payer if they
        share it. Use full names, capitalised.
      description: Short label, e.g. "dinner" or "cab".
    """
    if amount <= 0 or not participants:
        return {"status": "error", "message": "amount must be > 0 with at least one participant"}
    expense = {
        "payer": payer.strip().title(),
        "amount": round(float(amount), 2),
        "participants": sorted({p.strip().title() for p in participants}),
        "description": description,
    }
    expenses = _expenses(tool_context) + [expense]
    tool_context.state["expenses"] = expenses
    return {"status": "ok", "expense": expense, "expense_count": len(expenses)}


def list_expenses(tool_context: ToolContext) -> dict:
    """Lists every recorded expense and each person's net balance
    (positive = is owed money, negative = owes money)."""
    expenses = _expenses(tool_context)
    return {"expenses": expenses, "balances": ledger.balances(expenses)}


def settle_up(tool_context: ToolContext) -> dict:
    """Computes the minimum set of payments that settles all debts."""
    expenses = _expenses(tool_context)
    return {
        "total_spent": round(sum(e["amount"] for e in expenses), 2),
        "balances": ledger.balances(expenses),
        "payments": ledger.settle(expenses),
    }


def reset_expenses(tool_context: ToolContext) -> dict:
    """Clears every recorded expense to start a new group or trip."""
    tool_context.state["expenses"] = []
    return {"status": "cleared"}


INSTRUCTION = """You are SettleUp, a fast, friendly assistant that splits group expenses.

- When the user describes spending, call add_expense once per expense.
  "split with X and Y" or "for X, Y and me" means the payer is included.
  "for everyone"/"for all" means every person mentioned so far in the conversation.
  Treat "I"/"me" as the user, named "Me", unless they told you their name.
- When they ask who owes whom, to settle, or for a summary, call settle_up.
- Never do the arithmetic yourself: always use the tools' numbers.
- Reply in 1-4 short lines. List payments as "A -> B: 450.00".
"""


def _model():
    if USE_CLAUDE:
        # ADK's AnthropicLlm calls Claude through the official anthropic SDK.
        from google.adk.models.anthropic_llm import AnthropicLlm

        return AnthropicLlm(model=MODEL, max_tokens=4096)
    if USE_GEMINI:
        return MODEL
    from .offline_model import OfflineSettleModel

    return OfflineSettleModel()


def _config():
    if not USE_CLAUDE:
        return None
    from google.adk.models.anthropic_llm import AnthropicGenerateContentConfig

    # Low effort: the tools do the maths, so the model only parses and replies. Fast.
    return AnthropicGenerateContentConfig(effort=os.getenv("SETTLE_EFFORT", "low"))


root_agent = Agent(
    name="settleup",
    description="Splits shared expenses and works out who owes whom.",
    model=_model(),
    instruction=INSTRUCTION,
    tools=[add_expense, list_expenses, settle_up, reset_expenses],
    generate_content_config=_config(),
)
