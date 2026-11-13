"""Percy sandbox-only recipient wallet grants. Tokens grant scoped requests,
NOT stored value, PayPal wallets, card tokens, or cryptocurrency. No payments
or network calls occur. Host MUST supply a real identity verifier; default
is fail-closed. Prototype is in-memory only, not for production use.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from threading import RLock
from uuid import uuid4
from pocket import PercyPocket

class WalletError(ValueError): pass

def digest(s): return sha256(s.encode()).hexdigest()

def money(v):
    try: n = Decimal(str(v))
    except (ValueError, InvalidOperation): raise WalletError("Invalid amount") from None
    if isinstance(v, bool) or not n.is_finite() or n <= 0 or n != n.quantize(Decimal(".01")):
        raise WalletError("Amount must be positive exact USD cents")
    return n

@dataclass
class Grant:
    id: str
    recipient: str
    purposes: frozenset
    expires: datetime
    pocket: PercyPocket
    invitation_hash: str
    access_hash: str = ""
    revoked: bool = False
    used_invoice_ids: set = field(default_factory=set)

class TokenizedWallets:
    def __init__(self, *, issuer_secret, verify_recipient=None, clock=None):
        if not isinstance(issuer_secret, str) or len(issuer_secret) < 32:
            raise WalletError("Issuer secret must have 32 or more characters")
        self._owner_hash = digest(issuer_secret)
        self._verify = verify_recipient
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._grants, self._invitations, self._access = {}, {}, {}
        self.audit = []  # no plaintext tokens or secrets

    def _now(self):
        current = self._clock()
        if current.tzinfo is None or current.utcoffset() is None:
            raise WalletError("Clock requires timezone")
        return current.astimezone(timezone.utc)

    def _event(self, action, wallet, outcome):
        self.audit.append(dict(action=action, wallet_id=wallet, outcome=outcome,
                               at=self._now().isoformat()))

    def _owner(self, secret):
        if not isinstance(secret, str) or not compare_digest(digest(secret), self._owner_hash):
            raise PermissionError("Issuer authentication required")

    def _identity(self, proof):
        if self._verify is None:
            raise WalletError("Recipient identity verifier is not configured")
        try: subject = self._verify(proof)
        except Exception: raise WalletError("Identity verification failed") from None
        if not isinstance(subject, str) or not subject: raise WalletError("Identity not verified")
        return subject

    def _active(self, grant):
        if grant.revoked: raise WalletError("Grant revoked")
        if self._now() >= grant.expires: raise WalletError("Grant expired")

    def issue(self, *, issuer_secret, recipient, cap, purposes, ttl_seconds=3600):
        """Issuer creates a single-use invite. Deliver securely; never log it."""
        with self._lock:
            self._owner(issuer_secret)
            if not isinstance(recipient, str) or not recipient.strip(): raise WalletError("Recipient required")
            if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 30*86400:
                raise WalletError("Invalid lifetime")
            if not isinstance(purposes, (list, tuple, set)) or not purposes:
                raise WalletError("Purpose scope required")
            if any(not isinstance(p, str) or not p.strip() for p in purposes):
                raise WalletError("Invalid purpose")
            scopes = frozenset(p.strip().casefold() for p in purposes)
            amount = money(cap)
            ident, invitation = "percy-" + uuid4().hex, token_urlsafe(32)
            record = Grant(ident, recipient, scopes,
                           self._now()+timedelta(seconds=ttl_seconds),
                           PercyPocket(cap=amount), digest(invitation))
            self._grants[ident] = record
            self._invitations[record.invitation_hash] = ident
            self._event("ISSUE", ident, "PENDING_CLAIM")
            return dict(wallet_id=ident, invitation_token=invitation, recipient=recipient,
                        cap=str(amount), purposes=sorted(scopes),
                        expires_at=record.expires.isoformat(), sandbox_only=True)

    def claim(self, *, invitation_token, identity_proof):
        """Claim requires a trusted, independently authenticated recipient proof."""
        with self._lock:
            if not isinstance(invitation_token, str): raise WalletError("Invalid invite")
            ident = self._invitations.get(digest(invitation_token))
            if ident is None: raise WalletError("Unknown or used invitation")
            record = self._grants[ident]
            try:
                self._active(record)
                if self._identity(identity_proof) != record.recipient:
                    raise WalletError("Wrong recipient")
            except WalletError:
                self._event("CLAIM", ident, "DENIED")
                raise
            access = token_urlsafe(32)
            record.access_hash = digest(access)
            self._invitations.pop(record.invitation_hash)
            self._access[record.access_hash] = ident
            self._event("CLAIM", ident, "CLAIMED")
            return dict(wallet_id=ident, access_token=access, sandbox_only=True)

    def authorize(self, *, access_token, identity_proof, agent_id, invoice_id, amount, purpose):
        """Pass through Percy gate only; no actual PayPal payment is executed."""
        with self._lock:
            if not isinstance(access_token, str): raise WalletError("Invalid access token")
            ident = self._access.get(digest(access_token))
            if ident is None: raise WalletError("Invalid access token")
            record = self._grants[ident]
            try:
                self._active(record)
                if self._identity(identity_proof) != record.recipient: raise WalletError("Wrong recipient")
                if not isinstance(purpose, str) or purpose.strip().casefold() not in record.purposes:
                    raise WalletError("Purpose outside scope")
                if not isinstance(agent_id, str) or not agent_id.strip(): raise WalletError("Agent required")
                if not isinstance(invoice_id, str) or not invoice_id.strip(): raise WalletError("Invoice required")
                value = money(amount)
                if invoice_id in record.used_invoice_ids:
                    raise WalletError("Invoice already authorized in this wallet")
            except WalletError:
                self._event("AUTHORIZE", ident, "DENIED")
                raise
            decision = record.pocket.pocket(agent_id=agent_id, invoice_id=invoice_id,
                                            amount=value, purpose=purpose)
            if decision["decision"] != "BLOCKED":
                record.used_invoice_ids.add(invoice_id)
            self._event("AUTHORIZE", ident, decision["decision"])
            return dict(wallet_id=ident, decision=decision["decision"],
                        invoice_id=decision["invoice_id"], meter_after=decision["meter_after"],
                        cap=decision["cap"], payment_executed=False,
                        paypal_order_created=False, sandbox_only=True)

    def revoke(self, *, issuer_secret, wallet_id):
        with self._lock:
            self._owner(issuer_secret)
            record = self._grants[wallet_id]
            record.revoked = True
            self._invitations.pop(record.invitation_hash, None)
            if record.access_hash: self._access.pop(record.access_hash, None)
            self._event("REVOKE", wallet_id, "REVOKED")
            return dict(wallet_id=wallet_id, status="REVOKED")

    def status(self, *, issuer_secret, wallet_id):
        with self._lock:
            self._owner(issuer_secret)
            record = self._grants[wallet_id]
            state = ("REVOKED" if record.revoked else
                     "EXPIRED" if self._now() >= record.expires else
                     "CLAIMED" if record.access_hash else "PENDING_CLAIM")
            return dict(wallet_id=wallet_id, status=state, cap=str(record.pocket.cap),
                        spent=str(record.pocket.spent), sandbox_only=True,
                        audit=[x.copy() for x in self.audit if x["wallet_id"] == wallet_id])
