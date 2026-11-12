"""Percy + AI + PayPal sandbox: two commands, nothing else to set up.

Setup (once): create the sandbox app named Percy in the PayPal
Developer Dashboard, then put its Client ID and Secret in your
environment (names in .env.example). Never in this repo or a form.
For a live AI recommendation also set ENABLE_AI=1 and a provider key
- GEMINI_API_KEY (Google AI Studio) or OPENAI_API_KEY; without them
the advisor runs its deterministic local rule and says so - no live
AI inference is claimed in that mode.

Command 1 - create:
    python3 sandbox_demo.py
Flow: the AI advisor recommends one invoice from the server-eligible
list -> the pocket gate authorizes it -> a PayPal sandbox order is
created -> a gate receipt binds the order to that gate decision.

Then: open the approval link and approve as the SANDBOX buyer
(the Personal test account from Dashboard > Sandbox > Accounts).

Command 2 - capture, bound to the gate receipt:
    python3 sandbox_demo.py --capture ORDER_ID
Refuses any order the receipt does not name. The amount verified
against PayPal is the receipt's amount. Prints the verified capture
receipt plus the gate decision it belongs to.

Without PayPal credentials in the environment, both commands print
BLOCKED and exactly what is missing. Nothing is faked.
"""
import os
import sys
from decimal import Decimal

from ai_advisor import recommend
from gate_receipt import RECEIPT_PATH, load_receipt, verify_binding, write_receipt
from pocket import PercyPocket
from paypal_pocket import PayPalSandbox, gated_create_order

CAP = Decimal("200.00")
CANDIDATES = [
    {"invoice_id": "INV-001", "purpose": "supplier invoice", "amount": "60.00"},
    {"invoice_id": "INV-002", "purpose": "supplier invoice", "amount": "70.00"},
    {"invoice_id": "INV-003", "purpose": "equipment invoice", "amount": "250.00"},
]


def _paypal_credentials_missing():
    return not os.getenv("PAYPAL_CLIENT_ID") or not os.getenv("PAYPAL_CLIENT_SECRET")


def _blocked():
    print("BLOCKED: PayPal sandbox credentials are not in the environment.")
    print("Setup: PayPal Developer Dashboard > Apps & Credentials > Sandbox > app Percy")
    print("  Copy its Client ID and Secret into your environment:")
    print("    export PAYPAL_CLIENT_ID=...   (from the Percy app page)")
    print("    export PAYPAL_CLIENT_SECRET=...   (Secret key 1, same page)")
    print("Then re-run. Local gate demo runs without credentials: python3 demo.py")
    return 2


def main(argv):
    if "--capture" in argv:
        idx = argv.index("--capture")
        if idx + 1 >= len(argv):
            print("Usage: python3 sandbox_demo.py --capture ORDER_ID")
            return 2
        order_id = argv[idx + 1]
        try:
            receipt = load_receipt(RECEIPT_PATH)
            amount_cents = verify_binding(receipt, order_id)
        except FileNotFoundError:
            print("Capture refused: no gate receipt found. Run the create command first.")
            return 2
        except ValueError as exc:
            print(str(exc))
            return 2
        if _paypal_credentials_missing():
            return _blocked()
        paypal = PayPalSandbox()
        captured = paypal.capture_order(order_id, amount_cents, order_id)
        print("CAPTURE VERIFIED - sandbox receipt:")
        print("  capture_id:", captured["capture_id"])
        print("  order_id:  ", captured["order_id"])
        print("  status:    ", captured["status"])
        print("  amount:    ", f"${captured['amount_cents'] / 100:.2f}", captured["currency"])
        print("  time:      ", captured["create_time"])
        print("Bound to gate decision:")
        print("  invoice:   ", receipt["invoice_id"], "| agent:", receipt["agent_id"])
        print("  decision:  ", receipt["decision"], f"({receipt['percent_used']}% of cap ${receipt['cap']})")
        print("  gate_time: ", receipt["gate_time_utc"])
        return 0

    chosen, ai_receipt = recommend(CANDIDATES, CAP)
    if chosen is None:
        print("Advisor: no candidate fits the cap. Nothing to pay.")
        return 0
    print(f"AI advisor: recommends {chosen['invoice_id']} "
          f"(${chosen['amount']} {chosen['purpose']})")
    print(f"  mode: {ai_receipt['mode']} - {ai_receipt['reason']}")
    if _paypal_credentials_missing():
        return _blocked()
    pocket = PercyPocket(cap=CAP)
    paypal = PayPalSandbox()
    result, order = gated_create_order(
        pocket, paypal,
        agent_id="agent-board-01", purpose=chosen["purpose"],
        invoice_id=chosen["invoice_id"], amount=chosen["amount"],
        request_id="percy-" + chosen["invoice_id"],
    )
    print("Gate decision:", result["decision"], "-", result["reason"])
    if order is None:
        print("Blocked at the gate. PayPal was never called.")
        return 0
    amount_cents = int(Decimal(chosen["amount"]) * 100)
    receipt = write_receipt(
        RECEIPT_PATH,
        order_id=order["order_id"],
        gate_result=result,
        amount_cents=amount_cents,
        create_request_id="percy-" + chosen["invoice_id"],
    )
    print("Sandbox order created:", order["order_id"], order["status"])
    print("Gate receipt written:", RECEIPT_PATH, "| order bound to invoice",
          receipt["invoice_id"], "at", receipt["gate_time_utc"])
    print("1. Open this link and approve as the SANDBOX buyer:")
    print("  ", order["approve_url"])
    print("2. Then run:")
    print(f"   python3 sandbox_demo.py --capture {order['order_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
