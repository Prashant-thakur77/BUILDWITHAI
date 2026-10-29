"""Every number the film says or shows, read at build time from the repo and the recorded live run. None typed in.

    python video/facts.py  ->  ~/Videos/settleup/build/facts.json
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BUILD, CLIPS, ROOT  # noqa: E402

sys.path.insert(0, ROOT)
from settle_agent import ledger  # noqa: E402


def main() -> dict:
    usage = json.load(open(f"{CLIPS}/product.usage.json"))
    recent = sorted(usage["recent"], key=lambda r: r["ts"])
    add, ask = recent[0], recent[-1]
    pays = re.findall(r"(\w+) -> (\w+): ([\d,.]+)", ask["reply"])
    tests = subprocess.run([f"{ROOT}/.venv/bin/python", "-m", "pytest", "-q", "-p", "no:warnings"], cwd=ROOT,
                           capture_output=True, text=True)
    passed = int(re.search(r"(\d+) passed", tests.stdout).group(1))
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", tests.stdout)) else 0
    # The same expenses the live agent recorded, re-run through the ledger, to check the film's payments.
    expenses = [
        {"payer": "Arjun", "amount": 1200, "participants": ["Arjun", "Kabir", "Me", "Riya"], "description": "dinner"},
        {"payer": "Riya", "amount": 600, "participants": ["Kabir", "Me", "Riya"], "description": "cab"},
        {"payer": "Me", "amount": 900, "participants": ["Arjun", "Kabir", "Me", "Riya"], "description": "hotel snacks"},
    ]
    check = [(p["from"], p["to"], f"{p['amount']:.2f}") for p in ledger.settle(expenses)]
    assert check == [(a, b, c.replace(",", "")) for a, b, c in pays], (check, pays)
    people = len(ledger.balances(expenses))
    facts = {
        "model": add["model"],
        "tools_first": len(add["tools"]),
        "tool_first_name": add["tools"][0],
        "total_spent": f"{sum(e['amount'] for e in expenses):,.0f}",
        "payments": len(pays),
        "people": people,
        "pays": [{"from": a, "to": b, "amount": c} for a, b, c in pays],
        "latency_add_s": round(add["latency_ms"] / 1000, 1),
        "latency_ask_s": round(ask["latency_ms"] / 1000, 1),
        "tokens_total": usage["summary"]["prompt_tokens"] + usage["summary"]["output_tokens"],
        "requests": usage["summary"]["requests"],
        "tool_calls": sum(usage["tool_counts"].values()),
        "errors": usage["summary"]["errors"],
        "tests_passed": passed,
        "tests_failed": failed,
        "tools_defined": len(__import__("settle_agent.agent", fromlist=["root_agent"]).root_agent.tools),
    }
    os.makedirs(BUILD, exist_ok=True)
    json.dump(facts, open(f"{BUILD}/facts.json", "w"), indent=1)
    return facts


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
