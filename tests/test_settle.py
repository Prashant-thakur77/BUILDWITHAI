from fastapi.testclient import TestClient

from settle_agent import ledger
from settle_agent.offline_model import _parse_expenses


def test_balances_sum_to_zero_and_split_cents():
    exp = [{"payer": "A", "amount": 100, "participants": ["A", "B", "C"], "description": "x"}]
    bal = ledger.balances(exp)
    assert round(sum(bal.values()), 2) == 0
    assert bal == {"A": 66.66, "B": -33.33, "C": -33.33}


def test_settle_clears_every_balance_in_few_payments():
    exp = [
        {"payer": "Arjun", "amount": 1200, "participants": ["Arjun", "Kabir", "Me", "Riya"], "description": "d"},
        {"payer": "Riya", "amount": 600, "participants": ["Kabir", "Me", "Riya"], "description": "c"},
        {"payer": "Me", "amount": 900, "participants": ["Arjun", "Kabir", "Me", "Riya"], "description": "h"},
    ]
    pays = ledger.settle(exp)
    bal = ledger.balances(exp)
    for p in pays:
        bal[p["from"]] += p["amount"]
        bal[p["to"]] -= p["amount"]
    assert all(abs(v) < 0.01 for v in bal.values())
    assert len(pays) <= len(bal) - 1


def test_parser_resolves_everyone_after_all_names_seen():
    text = ("Arjun paid 1200 for dinner for everyone, Riya paid 600 for the cab "
            "split with Kabir and me, and I paid 900 for hotel snacks for all")
    out = _parse_expenses(text, known=[])
    assert [e["payer"] for e in out] == ["Arjun", "Riya", "Me"]
    assert out[0]["participants"] == ["Arjun", "Kabir", "Me", "Riya"]
    assert out[1]["participants"] == ["Kabir", "Me", "Riya"]
    assert out[2]["amount"] == 900


def test_chat_endpoint_runs_agent_and_logs_usage():
    import server

    c = TestClient(server.app)
    r = c.post("/api/chat", json={"message": "Riya paid 300 for coffee split with Arjun"}).json()
    assert [t["name"] for t in r["tools"]] == ["add_expense"]
    r = c.post("/api/chat", json={"message": "who owes whom?", "session_id": r["session_id"]}).json()
    assert "Arjun -> Riya: 150.00" in r["reply"]
    assert c.get("/api/usage").json()["summary"]["requests"] >= 2
