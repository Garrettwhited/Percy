"""Percy's AI advisor: the agent proposes, the server disposes.

The advisor recommends WHICH invoice to pay first, choosing only from
a server-built list of eligible candidates (each already checked to
fit the pocket cap). The model can never invent an invoice, change an
amount, or widen its own menu:

- Server builds the eligible list first (amount fits the cap).
- If a model is configured, it gets exactly those candidates and must
  answer with one of their invoice IDs. Any other answer is rejected.
- The pocket gate then independently authorizes the chosen invoice
  before any PayPal call. The AI never touches the gate or PayPal.

Modes, reported honestly in every run:
- AI_MODEL: a real model call returned an eligible invoice ID.
- LOCAL_RULE_AGENT: no model configured, or the model was
  unavailable/invalid, so a deterministic local rule chose instead
  (smallest eligible amount first). No AI inference is claimed in
  this mode.

Model access is opt-in and env-only: ENABLE_AI=1 plus a provider key -
GEMINI_API_KEY (Google AI Studio) or OPENAI_API_KEY - never in this
repo, a screenshot, or a form. If both keys are set, Gemini is used.
One bounded call, standard library only.
"""
import json
import os
import urllib.request
from decimal import Decimal


def eligible_candidates(candidates, cap):
    """Server-side filter: only invoices whose amount fits the cap."""
    cap = Decimal(str(cap))
    out = []
    for cand in candidates:
        amount = Decimal(str(cand["amount"]))
        if Decimal("0") < amount <= cap:
            out.append({**cand, "amount": str(amount)})
    return out


def local_rule_pick(eligible):
    """Deterministic fallback: smallest eligible amount first."""
    if not eligible:
        return None
    return min(eligible, key=lambda c: Decimal(str(c["amount"])))


def openai_recommend(eligible):
    """One bounded model call. Returns an invoice_id string.

    Sends only invoice IDs, purposes, and amounts - no account data,
    no credentials, no personal information.
    """
    if os.getenv("ENABLE_AI") != "1" or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("AI not configured")
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Percy's payment advisor. Choose exactly one "
                    "invoice ID from the eligible list provided. Pay the "
                    "most routine supplier obligation first. Never invent "
                    "an ID or an amount. Reply JSON only: "
                    '{"invoice_id": "<one eligible id>"}'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "eligible": [
                            {
                                "invoice_id": c["invoice_id"],
                                "purpose": c["purpose"],
                                "amount": c["amount"],
                            }
                            for c in eligible
                        ]
                    }
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 60,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    return json.loads(data["choices"][0]["message"]["content"])["invoice_id"]


def gemini_recommend(eligible):
    """One bounded Google AI Studio (Gemini) call. Same contract as the
    OpenAI path: returns an invoice_id string, sends only invoice IDs,
    purposes, and amounts - no account data, no credentials, no
    personal information.
    """
    if os.getenv("ENABLE_AI") != "1" or not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("AI not configured")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are Percy's payment advisor. Choose exactly one "
                        "invoice ID from the eligible list provided. Pay the "
                        "most routine supplier obligation first. Never invent "
                        "an ID or an amount. Reply JSON only: "
                        '{"invoice_id": "<one eligible id>"}'
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "eligible": [
                                    {
                                        "invoice_id": c["invoice_id"],
                                        "purpose": c["purpose"],
                                        "amount": c["amount"],
                                    }
                                    for c in eligible
                                ]
                            }
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 60,
            "temperature": 0,
        },
    }
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent",
        json.dumps(payload).encode(),
        headers={
            "x-goog-api-key": os.environ["GEMINI_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        data = json.load(response)
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)["invoice_id"]


def recommend(candidates, cap, ai_client=None):
    """Return (chosen_candidate, receipt_dict).

    The receipt states the mode truthfully, so a demo or a judge can
    see whether a live model actually ran.
    """
    eligible = eligible_candidates(candidates, cap)
    if not eligible:
        return None, {"mode": "blocked", "reason": "No candidate fits the cap"}
    model_label = "injected_ai_client"
    if ai_client is None and os.getenv("ENABLE_AI") == "1":
        if os.getenv("GEMINI_API_KEY"):
            ai_client = gemini_recommend
            model_label = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        elif os.getenv("OPENAI_API_KEY"):
            ai_client = openai_recommend
            model_label = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if ai_client is not None:
        try:
            pick_id = ai_client(eligible)
            found = next((c for c in eligible if c["invoice_id"] == pick_id), None)
            if found is not None:
                return found, {
                    "mode": "AI_MODEL",
                    "model": model_label,
                    "reason": "Model recommended an eligible invoice; server verified eligibility",
                }
            return local_rule_pick(eligible), {
                "mode": "LOCAL_RULE_AGENT",
                "reason": "AI pick was not eligible; strict local rule retained",
            }
        except Exception:
            return local_rule_pick(eligible), {
                "mode": "LOCAL_RULE_AGENT",
                "reason": "AI unavailable; strict local rule retained",
            }
    return local_rule_pick(eligible), {
        "mode": "LOCAL_RULE_AGENT",
        "reason": "No AI configured (ENABLE_AI / provider API key not set); no live AI inference claimed",
    }
