"""Cap engine for Percy — PayPal AI Hackathon entry.

Rules:
- Authorize BEFORE any payment goes through.
- WARN at >= 80% of cap.
- BLOCK the payment that would pass the cap, cold. Log it, notify the owner.
- Meter reconciled to the cent. Owner raising the cap is a deliberate,
  owner-only act — the agent cannot raise its own cap.

No PayPal API call lives here. This is the cap behavior only, so the
PayPal sandbox wiring can land at exactly one seam later, from the
official PayPal docs, once a sandbox app exists. Standard library only.
Sandbox logic only — no real money.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class PaymentAttempt:
    invoice_id: str
    amount: Decimal
    decision: str  # APPROVED / WARNED / BLOCKED
    meter_before: Decimal
    meter_after: Decimal
    reason: str


@dataclass
class RedButton:
    cap: Decimal
    owner: str = "owner"
    spent: Decimal = Decimal("0.00")
    log: list = field(default_factory=list)

    def __post_init__(self):
        self.cap = _money(self.cap)
        self.spent = _money(self.spent)

    @property
    def percent_used(self) -> Decimal:
        if self.cap == 0:
            return Decimal("0")
        return (self.spent / self.cap * 100).quantize(Decimal("0.01"))

    def authorize(self, invoice_id: str, amount) -> PaymentAttempt:
        amount = _money(amount)
        before = self.spent
        if before + amount > self.cap:
            attempt = PaymentAttempt(invoice_id, amount, "BLOCKED", before, before,
                                     f"BLOCKED: ${amount} would pass cap ${self.cap} "
                                     f"(spent ${before}, {self.percent_used}% used). "
                                     f"Owner notified; payment NOT executed.")
            self.log.append(attempt)
            return attempt
        after = before + amount
        self.spent = after
        warned = after >= (self.cap * Decimal("0.80"))
        decision = "WARNED" if warned else "APPROVED"
        reason = (f"{decision}: ${amount} approved, meter ${before} -> ${after} "
                  f"({self.percent_used}% of ${self.cap})."
                  + (" WARN: at or over 80% of cap." if warned else ""))
        attempt = PaymentAttempt(invoice_id, amount, decision, before, after, reason)
        self.log.append(attempt)
        return attempt

    def raise_cap(self, new_cap, by: str = "owner") -> str:
        """Owner-only cap raise. The agent cannot call this for itself."""
        if by != "owner":
            raise PermissionError("Only the owner can raise the cap.")
        new_cap = _money(new_cap)
        if new_cap < self.spent:
            raise ValueError("New cap cannot be below amount already spent.")
        old = self.cap
        self.cap = new_cap
        return f"Cap raised by owner: ${old} -> ${new_cap}. Spent stays ${self.spent}."
