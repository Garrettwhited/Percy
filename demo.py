"""Demo: owner cap $200/week, fictional supplier invoices, fictional owner.
Sandbox logic only tonight — no PayPal call, no real money."""
from decimal import Decimal

from red_button import RedButton

if __name__ == "__main__":
    rb = RedButton(cap=Decimal("200.00"), owner="SMB owner (fictional)")
    print(f"Owner sets cap: ${rb.cap} / week")
    for invoice_id, amount in [
        ("INV-001 supplier", "60.00"),
        ("INV-002 supplier", "70.00"),
        ("INV-003 supplier", "40.00"),   # meter $170 = 85% -> WARNED
        ("INV-004 supplier", "50.00"),   # would pass $200 -> BLOCKED
    ]:
        a = rb.authorize(invoice_id, amount)
        print(f"- {a.invoice_id} ${a.amount}: {a.decision} — {a.reason}")
    print(f"Meter after block: ${rb.spent} / ${rb.cap} ({rb.percent_used}%)")
    print(rb.raise_cap(Decimal("250.00"), by="owner"))
    a = rb.authorize("INV-004 supplier (retry after owner raise)", "50.00")
    print(f"- {a.invoice_id} ${a.amount}: {a.decision} — {a.reason}")
    print(f"Final meter: ${rb.spent} / ${rb.cap} ({rb.percent_used}%)")
    print(f"Audit log entries: {len(rb.log)} (every attempt logged, blocked included)")
