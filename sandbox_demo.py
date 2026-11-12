"""Percy + PayPal sandbox: two commands, nothing else to set up.

Setup (once): create the sandbox app named Percy in the PayPal
Developer Dashboard, then put its Client ID and Secret in your
environment (names in .env.example). Never in this repo or a form.

Command 1 - create (the pocket gate decides first):
    python3 sandbox_demo.py
Prints the gate decision, the sandbox order id, and the buyer
approval link. A blocked spend never reaches PayPal.

Then: open the approval link and approve as the SANDBOX buyer
(the Personal test account from Dashboard > Sandbox > Accounts).

Command 2 - capture and verify the receipt:
    python3 sandbox_demo.py --capture ORDER_ID
Prints the verified capture receipt (id, amount, status, time).

Without credentials in the environment, both commands print BLOCKED
and exactly what is missing. Nothing is faked.
"""
import os
import sys
from decimal import Decimal

from pocket import PercyPocket
from paypal_pocket import PayPalSandbox, gated_create_order

AMOUNT = "60.00"
AMOUNT_CENTS = 6000


def _credentials_missing():
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
        if _credentials_missing():
            return _blocked()
        order_id = argv[idx + 1]
        paypal = PayPalSandbox()
        receipt = paypal.capture_order(order_id, AMOUNT_CENTS, "percy-capture-001")
        print("CAPTURE VERIFIED - sandbox receipt:")
        print("  capture_id:", receipt["capture_id"])
        print("  order_id:  ", receipt["order_id"])
        print("  status:    ", receipt["status"])
        print("  amount:    ", f"${receipt['amount_cents'] / 100:.2f}", receipt["currency"])
        print("  time:      ", receipt["create_time"])
        return 0

    if _credentials_missing():
        return _blocked()
    pocket = PercyPocket(cap=Decimal("200.00"))
    paypal = PayPalSandbox()
    result, order = gated_create_order(
        pocket, paypal,
        agent_id="agent-board-01", purpose="supplier invoice",
        invoice_id="INV-001", amount=AMOUNT, request_id="percy-demo-001",
    )
    print("Gate decision:", result["decision"], "-", result["reason"])
    if order is None:
        print("Blocked at the gate. PayPal was never called.")
        return 0
    print("Sandbox order created:", order["order_id"], order["status"])
    print("1. Open this link and approve as the SANDBOX buyer:")
    print("  ", order["approve_url"])
    print("2. Then run:")
    print(f"   python3 sandbox_demo.py --capture {order['order_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
