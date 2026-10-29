"""Pure expense math: balances and a minimal set of settlement payments."""

from __future__ import annotations


def _cents(amount: float) -> int:
    return round(amount * 100)


def balances(expenses: list[dict]) -> dict[str, float]:
    """Net balance per person. Positive = is owed money, negative = owes."""
    net: dict[str, int] = {}
    for e in expenses:
        people = e["participants"]
        total = _cents(e["amount"])
        share, remainder = divmod(total, len(people))
        net[e["payer"]] = net.get(e["payer"], 0) + total
        for i, p in enumerate(people):
            # Spread leftover cents over the first few participants.
            net[p] = net.get(p, 0) - share - (1 if i < remainder else 0)
    return {p: c / 100 for p, c in sorted(net.items())}


def settle(expenses: list[dict]) -> list[dict]:
    """Greedy largest-creditor/largest-debtor matching.

    Produces at most n-1 payments for n people, which is what people want
    when settling a trip: few transfers, each one easy to understand.
    """
    net = {p: _cents(v) for p, v in balances(expenses).items()}
    creditors = sorted(((c, p) for p, c in net.items() if c > 0), reverse=True)
    debtors = sorted(((-c, p) for p, c in net.items() if c < 0), reverse=True)
    payments = []
    i = j = 0
    while i < len(creditors) and j < len(debtors):
        owed, creditor = creditors[i]
        owes, debtor = debtors[j]
        pay = min(owed, owes)
        payments.append({"from": debtor, "to": creditor, "amount": pay / 100})
        creditors[i] = (owed - pay, creditor)
        debtors[j] = (owes - pay, debtor)
        if creditors[i][0] == 0:
            i += 1
        if debtors[j][0] == 0:
            j += 1
    return payments
