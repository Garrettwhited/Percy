import unittest
from datetime import datetime,timedelta,timezone
from tokenized_wallet import TokenizedWallets,WalletError
SECRET='a'*48
class TestWallet(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,12,tzinfo=timezone.utc)
        self.svc=TokenizedWallets(issuer_secret=SECRET,
             verify_recipient=lambda proof:{'alice-proof':'alice','bob-proof':'bob'}.get(proof),
             clock=lambda:self.now)
    def issue(self,**kw):
        return self.svc.issue(issuer_secret=SECRET,recipient='alice',cap='250.00',purposes=['supplies'],**kw)
    def claim(self,w): return self.svc.claim(invitation_token=w['invitation_token'],identity_proof='alice-proof')
    def spend(self,auth,**kw):
        params=dict(access_token=auth['access_token'],identity_proof='alice-proof',
                    agent_id='agent1',invoice_id='INV-1',amount='25.00',purpose='supplies')
        params.update(kw)
        return self.svc.authorize(**params)
    def test_issue_claim(self):
        wallet=self.issue(); auth=self.claim(wallet); result=self.spend(auth)
        self.assertEqual(result['decision'],'APPROVED')
        self.assertEqual(result['meter_after'],'25.00')
        self.assertFalse(result['payment_executed'])
    def test_invite_single_use(self):
        w=self.issue(); self.claim(w)
        with self.assertRaises(WalletError): self.claim(w)
    def test_wrong_recipient_rejected(self):
        w=self.issue()
        with self.assertRaises(WalletError):
            self.svc.claim(invitation_token=w['invitation_token'],identity_proof='bob-proof')
        self.claim(w)
    def test_revalidate_identity(self):
        auth=self.claim(self.issue())
        with self.assertRaises(WalletError): self.spend(auth,identity_proof='bob-proof')
        self.assertEqual(self.spend(auth)['meter_after'],'25.00')
    def test_unconfigured_verifier_fails_closed(self):
        svc=TokenizedWallets(issuer_secret=SECRET)
        w=svc.issue(issuer_secret=SECRET,recipient='alice',cap='20.00',purposes=['supplies'])
        with self.assertRaises(WalletError):
            svc.claim(invitation_token=w['invitation_token'],identity_proof='alice')
    def test_expire_access_and_invites(self):
        w=self.issue(ttl_seconds=3); auth=self.claim(w)
        self.now+=timedelta(seconds=3)
        with self.assertRaises(WalletError): self.spend(auth)
        w2=self.issue(ttl_seconds=3); self.now+=timedelta(seconds=4)
        with self.assertRaises(WalletError): self.claim(w2)
    def test_revoke(self):
        w=self.issue(); auth=self.claim(w)
        self.svc.revoke(issuer_secret=SECRET,wallet_id=w['wallet_id'])
        with self.assertRaises(WalletError): self.spend(auth)
    def test_revoke_invite(self):
        w=self.issue(); self.svc.revoke(issuer_secret=SECRET,wallet_id=w['wallet_id'])
        with self.assertRaises(WalletError): self.claim(w)
    def test_cap_blocks_without_meter_movement(self):
        auth=self.claim(self.issue()); self.spend(auth,amount='240.00')
        x=self.spend(auth,amount='11.00',invoice_id='INV-2'); self.assertEqual(x['decision'],'BLOCKED')
        self.assertEqual(x['meter_after'],'240.00')
    def test_duplicate_invoice_rejected(self):
        auth=self.claim(self.issue())
        self.spend(auth,amount="25.00")
        with self.assertRaises(WalletError): self.spend(auth,amount="25.00")
        self.assertEqual(self.svc.status(issuer_secret=SECRET,wallet_id=auth["wallet_id"])["spent"],"25.00")
    def test_warn(self):
        auth=self.claim(self.issue())
        self.assertEqual(self.spend(auth,amount='200.00')['decision'],'WARNED')
    def test_scope_denied(self):
        auth=self.claim(self.issue())
        with self.assertRaises(WalletError): self.spend(auth,purpose='gift card')
        self.assertEqual(self.spend(auth)['meter_after'],'25.00')
    def test_reject_invalid_amounts(self):
        auth=self.claim(self.issue())
        for amount in ('0','-1','NaN','Infinity','1.234','foo',True):
            with self.subTest(amount=amount),self.assertRaises(WalletError): self.spend(auth,amount=amount)
    def test_owner_only(self):
        with self.assertRaises(PermissionError):
            self.svc.issue(issuer_secret='bad',recipient='alice',cap='250',purposes=['supplies'])
    def test_tokens_not_logged(self):
        w=self.issue(); auth=self.claim(w); self.spend(auth)
        status=self.svc.status(issuer_secret=SECRET,wallet_id=w['wallet_id'])
        self.assertEqual(status['status'],'CLAIMED')
        self.assertNotIn(w['invitation_token'],str(status))
        self.assertNotIn(auth['access_token'],str(status))
    def test_invalid_limits(self):
        for val in ('-2','0','NaN','12.345'):
            with self.subTest(val=val),self.assertRaises(WalletError):
                self.svc.issue(issuer_secret=SECRET,recipient='alice',cap=val,purposes=['supplies'])
        with self.assertRaises(WalletError): self.issue(ttl_seconds=999999999)
if __name__=='__main__': unittest.main()
