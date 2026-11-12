"""Percy pocket — tool call `pocket`, for the agent board.

Percy is the pocket. The pocket is the spend gate.
An agent (or a board check-in) does not pay directly. It calls
`pocket(...)` first, and Percy authorizes before any payment goes
through — the Red Button cap engine underneath.

Rules carried over from red_button.py, unchanged:
- Authorize BEFORE any payment goes through.
- WARN at >= 80% of cap.
- BLOCK the payment that would pass the cap, cold. Log it, notify owner.
- Meter reconciled to the cent. Owner raising the cap is a deliberate,
  owner-only act — the agent cannot raise its own cap.

Check-in tie:
- A pocket call carries the calling agent and, when there is one,
  an optional check-in reference, so the spend is traceable to that
  check-in.
- A check-in reference is a reference only. It is not a payment.
  This file sets no price, no fee, and no default for any of them.

No PayPal API call lives in this file. The PayPal sandbox wiring is
the one seam beside it: paypal_pocket.py, from the official PayPal
docs. Sandbox only, standard library only, no real money.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from red_button import RedButton


@dataclass
class PercyPocket:
    """One pocket. One owner, one cap, one meter, one audit log."""

    cap: Decimal
    owner: str = "owner"
    _button: RedButton = field(init=False, repr=False)

    def __post_init__(self):
        self._button = RedButton(cap=self.cap, owner=self.owner)

    @property
    def spent(self) -> Decimal:
        return self._button.spent

    @property
    def percent_used(self) -> Decimal:
        return self._button.percent_used

    @property
    def log(self):
        return self._button.log

    def pocket(self, agent_id: str, invoice_id: str, amount,
               purpose: str, board_checkin_id: str | None = None) -> dict:
        """Tool call `pocket`.

        Call this before any payment. Returns a plain dict so an agent
        tool-caller can read the decision without importing internals.

        A BLOCKED call means: do not execute the payment. Meter unchanged.
        """
        if not agent_id or not str(agent_id).strip():
            raise ValueError("pocket needs agent_id — who is asking to spend.")
        if not invoice_id or not str(invoice_id).strip():
            raise ValueError("pocket needs invoice_id — what is being paid.")
        if not purpose or not str(purpose).strip():
            raise ValueError("pocket needs purpose — why is this being paid.")
        attempt = self._button.authorize(str(invoice_id), amount)
        return {
            "tool": "pocket",
            "pocket": "Percy",
            "agent_id": str(agent_id),
            "board_checkin_id": board_checkin_id,
            "purpose": str(purpose),
            "invoice_id": attempt.invoice_id,
            "amount": str(attempt.amount),
            "decision": attempt.decision,  # APPROVED / WARNED / BLOCKED
            "meter_before": str(attempt.meter_before),
            "meter_after": str(attempt.meter_after),
            "percent_used": str(self._button.percent_used),
            "cap": str(self._button.cap),
            "execute_payment": attempt.decision != "BLOCKED",
            "reason": attempt.reason,
        }

    def raise_cap(self, new_cap, by: str = "owner") -> str:
        """Owner-only cap raise. The agent cannot call this for itself."""
        return self._button.raise_cap(new_cap, by=by)
