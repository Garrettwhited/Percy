"""Tests for server.py: the pocket gate as a deployable HTTP service.

Starts the real server on an ephemeral port and talks to it over
HTTP with the standard library only.
"""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server as server_module


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestPercyService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
        cls.base = "http://127.0.0.1:" + str(cls.httpd.server_address[1])
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_health(self):
        status, body = _get(self.base, "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_demo_sequence(self):
        status, body = _get(self.base, "/demo")
        self.assertEqual(status, 200)
        decisions = [s["decision"] for s in body["steps"] if "decision" in s]
        # Retry after the owner raise lands at $220/$250 = 88% -> WARNED,
        # and it does execute (only BLOCKED stops a payment).
        self.assertEqual(
            decisions, ["APPROVED", "APPROVED", "WARNED", "BLOCKED", "WARNED"]
        )
        retry = [s for s in body["steps"] if s.get("decision") == "WARNED"][-1]
        self.assertTrue(retry["execute_payment"])

    def test_pocket_post_progression(self):
        # Unique invoice ids; the shared pocket starts empty in a fresh
        # test process run order-independent amounts are small.
        status, body = _post(
            self.base,
            "/pocket",
            {
                "agent_id": "agent-test",
                "invoice_id": "T-INV-1",
                "purpose": "supplier invoice",
                "amount": "10.00",
                "board_checkin_id": "checkin-test-1",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["tool"], "pocket")
        self.assertEqual(body["board_checkin_id"], "checkin-test-1")
        self.assertIn(body["decision"], ("APPROVED", "WARNED", "BLOCKED"))
        self.assertEqual(body["execute_payment"], body["decision"] != "BLOCKED")

    def test_pocket_post_over_cap_blocks(self):
        status, body = _post(
            self.base,
            "/pocket",
            {
                "agent_id": "agent-test",
                "invoice_id": "T-INV-BIG",
                "purpose": "equipment",
                "amount": "99999.00",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["decision"], "BLOCKED")
        self.assertFalse(body["execute_payment"])

    def test_pocket_post_missing_fields_400(self):
        status, _ = _post(self.base, "/pocket", {"agent_id": "agent-test"})
        self.assertEqual(status, 400)

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            _get(self.base, "/nope")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
