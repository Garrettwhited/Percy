"""Gate receipt: binds a PayPal capture to the pocket decision that
authorized it.

When the gated create runs, the pocket's decision is written to a
local receipt file (never committed - it is in .gitignore):

    {order_id, invoice_id, agent_id, amount_cents, decision,
     percent_used, cap, gate_time_utc, create_request_id}

The capture command then refuses to run unless:
- a receipt exists, and
- the order ID being captured matches the receipt exactly, and
- the amount verified against PayPal is the receipt's amount -
  not a constant in the script.

The capture idempotency key is derived from the order ID, so each
order has its own key and a retry of the same capture is safe.
"""
import json
from datetime import datetime, timezone

RECEIPT_PATH = ".percy-gate-receipt.json"


def capture_request_id(order_id):
    """Per-order idempotency key for the capture call.

    Matches what paypal_pocket.capture_order sends when it is given
    the order ID as its request_id: "capture-" + order_id.
    """
    return "capture-" + order_id


def write_receipt(path, *, order_id, gate_result, amount_cents, create_request_id):
    if gate_result["decision"] == "BLOCKED":
        raise ValueError("A blocked decision has no receipt and no order")
    receipt = {
        "order_id": order_id,
        "invoice_id": gate_result["invoice_id"],
        "agent_id": gate_result["agent_id"],
        "board_checkin_id": gate_result.get("board_checkin_id"),
        "amount_cents": int(amount_cents),
        "decision": gate_result["decision"],
        "percent_used": gate_result["percent_used"],
        "cap": gate_result["cap"],
        "gate_time_utc": datetime.now(timezone.utc).isoformat(),
        "create_request_id": create_request_id,
        "capture_request_id": capture_request_id(order_id),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    return receipt


def load_receipt(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verify_binding(receipt, order_id):
    """Raise unless this capture belongs to the recorded gate decision."""
    if receipt.get("order_id") != order_id:
        raise ValueError(
            "Capture refused: order ID does not match the gate receipt. "
            "This order was not the one the pocket authorized here."
        )
    if receipt.get("decision") not in ("APPROVED", "WARNED"):
        raise ValueError("Capture refused: gate receipt is not an approval")
    return receipt["amount_cents"]
