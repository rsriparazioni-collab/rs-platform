"""Backend tests for the Password Manager section (list/reveal/CRUD/RBAC/import/audit)."""
import os
import time

import pyotp
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_TOTP_SECRET = os.environ["TEST_ADMIN_TOTP_SECRET"]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ibvEaSKWzq96YMYHJQM-0c7uOixkKYiyKSfOO4kxs7E/edit?gid=0"


def _sess_from_token(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _admin_login():
    last_err = None
    for attempt in range(3):
        r = requests.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "Devis2026!"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        if not data.get("mfa_required"):
            return data["token"], data["user"]
        code = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": data["mfa_token"], "code": code}, timeout=30)
        if r2.status_code == 200:
            return r2.json()["token"], r2.json()["user"]
        last_err = r2.text
        # code reused / clock skew — wait for next window
        time.sleep(32)
    raise AssertionError(f"Admin MFA login failed: {last_err}")


def _michael_login():
    r = requests.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def admin():
    tok, user = _admin_login()
    return _sess_from_token(tok), user


@pytest.fixture(scope="module")
def tirano_id(admin):
    s, _ = admin
    stores = s.get(f"{API}/stores", timeout=30).json()
    for st in stores:
        if "tirano" in st.get("nome", "").lower():
            return st["id"]
    pytest.fail("Store Tirano not found")


@pytest.fixture(scope="module")
def michael_enrolled(admin):
    """Enroll TOTP for Michael to bypass X-MFA-Setup-Required, reset after tests."""
    tok, user = _michael_login()
    s = _sess_from_token(tok)
    # Enroll
    r = s.post(f"{API}/auth/2fa/enroll", timeout=30)
    if r.status_code == 409:
        pytest.skip("Michael already has 2FA enrolled")
    assert r.status_code == 200, r.text
    manual_key = r.json()["manual_key"]
    code = pyotp.TOTP(manual_key).now()
    rc = s.post(f"{API}/auth/2fa/enroll/confirm", json={"code": code}, timeout=30)
    assert rc.status_code == 200, rc.text
    # Re-login with MFA
    r1 = requests.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"}, timeout=30)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1.get("mfa_required")
    code2 = pyotp.TOTP(manual_key).now()
    # avoid clash with just-used code
    if code2 == code:
        time.sleep(31)
        code2 = pyotp.TOTP(manual_key).now()
    r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": d1["mfa_token"], "code": code2}, timeout=30)
    assert r2.status_code == 200, r2.text
    yield _sess_from_token(r2.json()["token"]), user
    # Cleanup: admin resets Michael's 2FA
    admin_sess, _ = admin
    rr = admin_sess.post(f"{API}/users/{user['id']}/2fa/reset", timeout=30)
    assert rr.status_code == 200, rr.text


# ---------------- Admin: list/CRUD/reveal ----------------

class TestPasswordsAdmin:
    def test_list_has_52_plus_and_hides_enc(self, admin):
        s, _ = admin
        r = s.get(f"{API}/passwords", timeout=30)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) >= 52, f"Expected >=52 got {len(rows)}"
        for p in rows:
            assert "password_enc" not in p
            assert "contenuto_enc" not in p
            assert "has_password" in p
            assert "has_contenuto" in p

    def test_full_crud_and_reveal(self, admin, tirano_id):
        s, _ = admin
        payload = {"servizio": "TEST_PW", "titolo": "x", "username": "u", "password": "Segreta1!",
                   "url": "https://example.com", "contenuto": "riga1\nriga2", "store_ids": [tirano_id]}
        r = s.post(f"{API}/passwords", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        created = r.json()
        pid = created["id"]
        try:
            assert created["servizio"] == "TEST_PW"
            assert created["has_password"] is True
            assert created["has_contenuto"] is True
            assert "password_enc" not in created

            # reveal
            rv = s.get(f"{API}/passwords/{pid}/reveal", timeout=30).json()
            assert rv["password"] == "Segreta1!"
            assert rv["contenuto"] == "riga1\nriga2"

            # PATCH password=None keeps password
            pk = {**payload, "password": None, "titolo": "y"}
            r2 = s.patch(f"{API}/passwords/{pid}", json=pk, timeout=30)
            assert r2.status_code == 200, r2.text
            assert r2.json()["titolo"] == "y"
            rv2 = s.get(f"{API}/passwords/{pid}/reveal", timeout=30).json()
            assert rv2["password"] == "Segreta1!"

            # PATCH password="" clears password
            pc = {**payload, "password": "", "titolo": "y"}
            r3 = s.patch(f"{API}/passwords/{pid}", json=pc, timeout=30)
            assert r3.status_code == 200
            assert r3.json()["has_password"] is False
            rv3 = s.get(f"{API}/passwords/{pid}/reveal", timeout=30).json()
            assert rv3["password"] == ""
        finally:
            rd = s.delete(f"{API}/passwords/{pid}", timeout=30)
            assert rd.status_code == 200
            assert s.get(f"{API}/passwords/{pid}/reveal", timeout=30).status_code == 404

    def test_import_sheet_gia_importato(self, admin):
        s, _ = admin
        r = s.post(f"{API}/passwords/import-sheet", json={"sheet_url": SHEET_URL}, timeout=90)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "gia_importato"

    def test_audit_log_view_segreti_after_reveal(self, admin):
        s, _ = admin
        rows = s.get(f"{API}/passwords", timeout=30).json()
        # pick any voice (admin can reveal all)
        pid = rows[0]["id"]
        s.get(f"{API}/passwords/{pid}/reveal", timeout=30)
        time.sleep(1)
        al = s.get(f"{API}/audit-log", params={"action": "view_segreti", "limit": 50}, timeout=30)
        assert al.status_code == 200, al.text
        entries = al.json() if isinstance(al.json(), list) else al.json().get("items", [])
        assert any(e.get("entity") == "password" and e.get("action") == "view_segreti" for e in entries), \
            f"No view_segreti/password audit entry found in {entries[:5]}"


# ---------------- Michael (negozio Tirano): RBAC ----------------

class TestPasswordsRBAC:
    def test_michael_sees_only_tirano(self, admin, michael_enrolled, tirano_id):
        s_admin, _ = admin
        s_mic, m_user = michael_enrolled
        # Admin creates a Tirano voice + admin-only voice
        t_payload = {"servizio": "TEST_PW_TIRANO", "titolo": "t", "username": "u", "password": "p1",
                     "url": "", "contenuto": "", "store_ids": [tirano_id]}
        a_payload = {"servizio": "TEST_PW_ADMIN_ONLY", "titolo": "a", "username": "u", "password": "p2",
                     "url": "", "contenuto": "", "store_ids": []}
        rt = s_admin.post(f"{API}/passwords", json=t_payload, timeout=30).json()
        ra = s_admin.post(f"{API}/passwords", json=a_payload, timeout=30).json()
        try:
            rows = s_mic.get(f"{API}/passwords", timeout=30)
            assert rows.status_code == 200, rows.text
            data = rows.json()
            ids = {p["id"] for p in data}
            assert rt["id"] in ids
            assert ra["id"] not in ids
            # None of the visible items should be admin-only (store_ids empty)
            for p in data:
                assert p.get("store_ids"), f"Michael sees admin-only voice {p}"

            # reveal admin-only -> 404
            assert s_mic.get(f"{API}/passwords/{ra['id']}/reveal", timeout=30).status_code == 404

            # POST -> 403
            assert s_mic.post(f"{API}/passwords", json=t_payload, timeout=30).status_code == 403
            # PATCH -> 403
            assert s_mic.patch(f"{API}/passwords/{rt['id']}", json=t_payload, timeout=30).status_code == 403
            # DELETE -> 403
            assert s_mic.delete(f"{API}/passwords/{rt['id']}", timeout=30).status_code == 403
        finally:
            s_admin.delete(f"{API}/passwords/{rt['id']}", timeout=30)
            s_admin.delete(f"{API}/passwords/{ra['id']}", timeout=30)
