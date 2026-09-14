"""Iter 15 - Follow-up contatti (esito chiamate su scadenze).

Covers:
- POST /api/followup validations (esito, richiamare_il, target 404)
- GET /api/followup listing
- GET /api/followup/da-richiamare open filter + scaduto flag
- attach_followups on /scadenze-settimana and /alerts (ultimo_contatto field)
- Re-post with 'contattato' closes previous open entry
- RBAC: negozio user Michael sees only his store, POST on other store's client -> 404
"""
import os
import time
from datetime import date, timedelta

import pyotp
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_TOTP_SECRET = os.environ["TEST_ADMIN_TOTP_SECRET"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _admin_login():
    last_err = None
    for _ in range(3):
        r = requests.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "Devis2026!"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        if not d.get("mfa_required"):
            return d["token"], d["user"]
        code = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": code}, timeout=30)
        if r2.status_code == 200:
            return r2.json()["token"], r2.json()["user"]
        last_err = r2.text
        time.sleep(32)
    raise AssertionError(f"Admin MFA login failed: {last_err}")


def _simple_login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def admin():
    tok, u = _admin_login()
    return _sess(tok), u


@pytest.fixture(scope="module")
def michael_enrolled(admin):
    tok, user = _simple_login("michael@cambiaora.local", "Michael2026!")
    s = _sess(tok)
    r = s.post(f"{API}/auth/2fa/enroll", timeout=30)
    if r.status_code == 409:
        # Already enrolled - can't do full MFA login without secret; skip module
        pytest.skip("Michael already has 2FA enrolled - cannot proceed without secret")
    assert r.status_code == 200, r.text
    manual_key = r.json()["manual_key"]
    code = pyotp.TOTP(manual_key).now()
    rc = s.post(f"{API}/auth/2fa/enroll/confirm", json={"code": code}, timeout=30)
    assert rc.status_code == 200, rc.text
    r1 = requests.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"}, timeout=30)
    d1 = r1.json()
    assert d1.get("mfa_required"), d1
    code2 = pyotp.TOTP(manual_key).now()
    if code2 == code:
        time.sleep(31)
        code2 = pyotp.TOTP(manual_key).now()
    r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": d1["mfa_token"], "code": code2}, timeout=30)
    assert r2.status_code == 200, r2.text
    yield _sess(r2.json()["token"]), user
    admin_sess, _ = admin
    admin_sess.post(f"{API}/users/{user['id']}/2fa/reset", timeout=30)


@pytest.fixture(scope="module")
def a_client(admin):
    s, _ = admin
    r = s.get(f"{API}/clients", params={"limit": 1000}, timeout=30)
    assert r.status_code == 200
    body = r.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    assert items, "no clients in DB"
    return items[0]


@pytest.fixture(scope="module")
def tirano_client(admin):
    """A client belonging to Tirano store (Michael's scope) and one NOT belonging."""
    s, _ = admin
    stores = s.get(f"{API}/stores", timeout=30).json()
    tirano = next((st for st in stores if "tirano" in st.get("nome", "").lower()), None)
    assert tirano, "Tirano store not found"
    r = s.get(f"{API}/clients", params={"limit": 2000}, timeout=30)
    body = r.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    in_tirano = next((c for c in items if c.get("venditore_id") == tirano["id"]), None)
    out_tirano = next((c for c in items if c.get("venditore_id") and c.get("venditore_id") != tirano["id"]), None)
    assert in_tirano and out_tirano, "need at least one client in Tirano and one outside"
    return tirano, in_tirano, out_tirano


TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

_created_ids: list = []


# ---------------- Validation ----------------

class TestFollowupValidation:
    def test_post_missing_richiamare_il_returns_400(self, admin, a_client):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "client", "target_id": a_client["id"], "motivo": "rinnovo",
            "esito": "non_risponde", "note": "TEST_ missing date",
        }, timeout=30)
        assert r.status_code == 400, r.text

    def test_post_invalid_esito_returns_400(self, admin, a_client):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "client", "target_id": a_client["id"], "motivo": "rinnovo",
            "esito": "bogus", "richiamare_il": TOMORROW, "note": "TEST_ invalid esito",
        }, timeout=30)
        assert r.status_code == 400, r.text

    def test_post_target_not_found_returns_404(self, admin):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "client", "target_id": "does-not-exist-xyz", "motivo": "rinnovo",
            "esito": "non_risponde", "richiamare_il": TOMORROW, "note": "TEST_ ghost",
        }, timeout=30)
        assert r.status_code == 404, r.text


# ---------------- Happy path + attach_followups ----------------

class TestFollowupFlow:
    def test_create_open_followup(self, admin, a_client):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "client", "target_id": a_client["id"], "motivo": "rinnovo",
            "esito": "non_risponde", "richiamare_il": TOMORROW, "note": "TEST_ prova",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["aperto"] is True
        assert d["esito"] == "non_risponde"
        assert d["richiamare_il"] == TOMORROW
        assert d.get("label"), "label must be set"
        assert "store_id" in d
        _created_ids.append(d["id"])

    def test_list_followup_history_contains_entry(self, admin, a_client):
        s, _ = admin
        r = s.get(f"{API}/followup", params={"target_type": "client", "target_id": a_client["id"]}, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert any(x.get("note") == "TEST_ prova" for x in rows), rows

    def test_da_richiamare_contains_entry_not_scaduto(self, admin, a_client):
        s, _ = admin
        r = s.get(f"{API}/followup/da-richiamare", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        mine = [x for x in rows if x.get("target_id") == a_client["id"] and x.get("note") == "TEST_ prova"]
        assert mine, "created followup not in da-richiamare"
        assert mine[0]["scaduto"] is False
        assert mine[0].get("aperto", True) is True

    def test_scadenze_settimana_has_ultimo_contatto_field(self, admin):
        s, _ = admin
        r = s.get(f"{API}/scadenze-settimana", timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        for row in out.get("rinnovi", []):
            assert "ultimo_contatto" in row  # may be None but field must exist

    def test_alerts_rinnovi_has_ultimo_contatto_field(self, admin):
        s, _ = admin
        r = s.get(f"{API}/alerts", timeout=30)
        assert r.status_code == 200, r.text
        out = r.json()
        for row in out.get("rinnovi", []):
            assert "ultimo_contatto" in row

    def test_reposting_contattato_closes_previous(self, admin, a_client):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "client", "target_id": a_client["id"], "motivo": "rinnovo",
            "esito": "contattato", "note": "TEST_ closed",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["aperto"] is False
        _created_ids.append(d["id"])

        # No longer in da-richiamare
        r2 = s.get(f"{API}/followup/da-richiamare", timeout=30)
        rows = r2.json()
        still_open = [x for x in rows if x.get("target_id") == a_client["id"] and x.get("motivo") == "rinnovo"]
        assert not still_open, f"still open: {still_open}"


# ---------------- Servizio riparazione + scaduto ----------------

class TestFollowupServizio:
    @pytest.fixture(scope="class")
    def pronto_repair_id(self, admin):
        s, _ = admin
        r = s.get(f"{API}/servizi", params={"tipo": "riparazione", "stato": "pronto", "limit": 50}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        items = body["items"] if isinstance(body, dict) and "items" in body else body
        if not items:
            pytest.skip("no repair in stato=pronto to test")
        return items[0]["id"]

    def test_servizio_riparazione_scaduto_true(self, admin, pronto_repair_id):
        s, _ = admin
        r = s.post(f"{API}/followup", json={
            "target_type": "servizio", "target_id": pronto_repair_id, "motivo": "riparazione_pronta",
            "esito": "richiamare", "richiamare_il": YESTERDAY, "note": "TEST_ scaduto",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        _created_ids.append(d["id"])
        r2 = s.get(f"{API}/followup/da-richiamare", timeout=30)
        rows = r2.json()
        mine = [x for x in rows if x.get("target_id") == pronto_repair_id and x.get("motivo") == "riparazione_pronta"]
        assert mine, "servizio followup missing"
        assert mine[0]["scaduto"] is True


# ---------------- RBAC Michael (Tirano) ----------------

class TestFollowupRBAC:
    def test_michael_da_richiamare_only_his_stores(self, admin, michael_enrolled, tirano_client):
        tirano, _in, _out = tirano_client
        m_sess, m_user = michael_enrolled

        # Create a Tirano followup as admin so Michael sees it
        adm, _ = admin
        r = adm.post(f"{API}/followup", json={
            "target_type": "client", "target_id": _in["id"], "motivo": "rinnovo",
            "esito": "non_risponde", "richiamare_il": TOMORROW, "note": "TEST_ tirano scope",
        }, timeout=30)
        assert r.status_code == 200, r.text
        _created_ids.append(r.json()["id"])

        r2 = m_sess.get(f"{API}/followup/da-richiamare", timeout=30)
        assert r2.status_code == 200, r2.text
        rows = r2.json()
        assert rows, "Michael should see at least the Tirano entry"
        for x in rows:
            assert x.get("store_id") in m_user.get("store_ids", []), (
                f"Michael saw store {x.get('store_id')} not in scope {m_user.get('store_ids')}")

    def test_michael_post_other_store_client_returns_404(self, michael_enrolled, tirano_client):
        _, _in, _out = tirano_client
        m_sess, _ = michael_enrolled
        r = m_sess.post(f"{API}/followup", json={
            "target_type": "client", "target_id": _out["id"], "motivo": "rinnovo",
            "esito": "non_risponde", "richiamare_il": TOMORROW, "note": "TEST_ cross store",
        }, timeout=30)
        assert r.status_code == 404, r.text


# ---------------- Cleanup ----------------

def test_zzz_cleanup(admin):
    """Delete all TEST_ prefixed followup docs directly via Mongo."""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values as dv
    env = dv("/app/backend/.env")
    mongo_url = env.get("MONGO_URL") or os.environ.get("MONGO_URL")
    db_name = env.get("DB_NAME") or os.environ.get("DB_NAME")
    assert mongo_url and db_name, "missing MONGO_URL/DB_NAME"

    async def _run():
        client = AsyncIOMotorClient(mongo_url)
        try:
            res = await client[db_name].followup.delete_many({"note": {"$regex": "^TEST_"}})
            return res.deleted_count
        finally:
            client.close()

    deleted = asyncio.run(_run())
    print(f"Cleanup: deleted {deleted} TEST_ followup docs")
    assert deleted >= 0
