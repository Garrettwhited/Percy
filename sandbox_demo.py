"""Percy + PayPal sandbox, ready-check and gated order create.

Without sandbox credentials in the environment, this prints exactly
what is missing and exits - it does not fake a PayPal call.
With credentials, it runs the pocket gate first, then creates one
sandbox order and prints the buyer approval link. Capture happens in
demo flow after the buyer approves (see README).
"""
import os
import sys
from decimal import Decimal

from pocket import PercyPocket
from paypal_pocket import PayPalSandbox, gated_create_order


def main():
    if not os.getenv("PAYPAL_CLIENT_ID") or not os.getenv("PAYPAL_CLIENT_SECRET"):
        print("BLOCKED: PayPal sandbox credentials are not in the environment.")
        print("Setup: PayPal Developer Dashboard > Apps & Credentials > Sandbox")
        print("  1. Create App named: Percy")
        print("  2. Copy its Client ID and Secret into your secret manager / shell env:")
        print("     PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET")
        print("  3. Re-run: python3 sandbox_demo.py")
        print("Local gate demo still runs without credentials: python3 demo.py")
        return 2
    pocket = PercyPocket(cap=Decimal("200.00"))
    paypal = PayPalSandbox()
    result, order = gated_create_order(
        pocket, paypal,
        agent_id="agent-board-01", purpose="supplier invoice",
        invoice_id="INV-001", amount="60.00", request_id="percy-demo-001",
    )
    print("Gate decision:", result["decision"], "-", result["reason"])
    if order is None:
        print("Blocked at the gate. PayPal was never called.")
        return 0
    print("Sandbox order created:", order["order_id"], order["status"])
    print("Buyer approval link (sandbox buyer only):", order["approve_url"])
    print("After the sandbox buyer approves, capture with paypal_pocket.capture_order")
    print("using the same order id and the gated amount of 6000 cents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
