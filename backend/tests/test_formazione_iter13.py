"""Iteration 13 regression: Formazione (public + auth CRUD + PDF + RBAC) + sync-fogli dry_run.

Rules:
- Only create TEST_ entries; delete them at end.
- DO NOT call /formazione/ripristina-default.
- Sync-fogli only with dry_run=true.
- Michael negozio: enroll 2FA to test read-only access, then admin resets 2FA at end.
"""
import io
import os
import time

import pyotp
import pypdf
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rsriparazioni@gmail.com"
ADMIN_PWD = "Devis2026!"
ADMIN_TOTP = os.environ["TEST_ADMIN_TOTP_SECRET"]
MICHAEL = ("michael@cambiaora.local", "Michael2026!")

STATE = {"created_ids": []}


def _admin_login():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    for _ in range(3):
        code = pyotp.TOTP(ADMIN_TOTP).now()
        r2 = requests.post(f"{API}/auth/login/mfa",
                           json={"mfa_token": body["mfa_token"], "code": code}, timeout=30)
        if r2.status_code == 200:
            return r2.json()["token"]
        time.sleep(31)
    pytest.fail(f"MFA login failed: {r2.status_code} {r2.text[:200]}")


def _session(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin():
    return _session(_admin_login())


@pytest.fixture(scope="session")
def michael_with_2fa(admin):
    """Login michael, enroll 2FA, then return authenticated session. Cleaned up in teardown."""
    r = requests.post(f"{API}/auth/login", json={"email": MICHAEL[0], "password": MICHAEL[1]}, timeout=30)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    sess = _session(token)
    # Enroll 2FA
    r = sess.post(f"{API}/auth/2fa/enroll", json={}, timeout=15)
    if r.status_code == 409:
        # Already enrolled - skip enrollment. Rely on existing setup.
        yield sess
    else:
        assert r.status_code == 200, r.text
        secret = r.json()["manual_key"]
        # Confirm
        code = pyotp.TOTP(secret).now()
        r = sess.post(f"{API}/auth/2fa/enroll/confirm", json={"code": code}, timeout=15)
        if r.status_code != 200:
            time.sleep(31)
            code = pyotp.TOTP(secret).now()
            r = sess.post(f"{API}/auth/2fa/enroll/confirm", json={"code": code}, timeout=15)
        assert r.status_code == 200, r.text
        yield sess
    # Teardown: admin resets Michael's 2FA
    me = sess.get(f"{API}/auth/me").json()
    admin.post(f"{API}/users/{me['id']}/2fa/reset", json={}, timeout=15)


# ---------- PUBLIC endpoints ----------
class TestPublicFormazione:
    def test_public_presentazione_list_no_auth(self):
        r = requests.get(f"{API}/public/formazione/presentazione", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 13, f"expected 13 slides, got {len(data)}"
        # Ordered by 'ordine' ascending
        ordini = [d.get("ordine") for d in data]
        assert ordini == sorted(ordini), f"slides not sorted by ordine: {ordini}"
        # sezione slide
        assert all(d.get("sezione") == "slide" for d in data)

    def test_public_presentazione_pdf(self):
        r = requests.get(f"{API}/public/formazione/presentazione.pdf", timeout=60)
        assert r.status_code == 200, r.text
        assert "application/pdf" in r.headers.get("content-type", "")
        reader = pypdf.PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) == 13, f"expected 13 pages, got {len(reader.pages)}"


# ---------- AUTH endpoints ----------
class TestAuthFormazione:
    def test_no_token_401(self):
        assert requests.get(f"{API}/formazione", timeout=15).status_code == 401

    def test_list_all_admin_40(self, admin):
        r = admin.get(f"{API}/formazione", timeout=30)
        assert r.status_code == 200
        rows = r.json()
        by_sez = {}
        for r_ in rows:
            by_sez[r_["sezione"]] = by_sez.get(r_["sezione"], 0) + 1
        # Total: seed has 13 slide + 13 manuale + 14 servizi = 40.
        # We may have added TEST_ items at this point; filter them.
        rows_seed = [r_ for r_ in rows if not r_["titolo"].startswith("TEST_")]
        seed_by_sez = {}
        for r_ in rows_seed:
            seed_by_sez[r_["sezione"]] = seed_by_sez.get(r_["sezione"], 0) + 1
        assert len(rows_seed) == 40, f"expected 40 seed rows, got {len(rows_seed)}: {seed_by_sez}"
        assert seed_by_sez.get("slide") == 13
        assert seed_by_sez.get("manuale") == 13
        assert seed_by_sez.get("servizi") == 14

    def test_filter_manuale(self, admin):
        r = admin.get(f"{API}/formazione?sezione=manuale", timeout=30)
        assert r.status_code == 200
        rows = [x for x in r.json() if not x["titolo"].startswith("TEST_")]
        assert all(r_["sezione"] == "manuale" for r_ in r.json())
        assert len(rows) == 13

    def test_pdf_manuale(self, admin):
        r = admin.get(f"{API}/formazione/pdf?sezione=manuale", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        reader = pypdf.PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) >= 1

    def test_pdf_servizi(self, admin):
        r = admin.get(f"{API}/formazione/pdf?sezione=servizi", timeout=60)
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")

    def test_pdf_slide(self, admin):
        r = admin.get(f"{API}/formazione/pdf?sezione=slide", timeout=60)
        assert r.status_code == 200
        reader = pypdf.PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) == 13

    def test_pdf_invalid_section_400(self, admin):
        r = admin.get(f"{API}/formazione/pdf?sezione=invalid", timeout=15)
        assert r.status_code == 400


# ---------- CRUD admin ----------
class TestFormazioneCRUD:
    def test_create_auto_ordine(self, admin):
        # find current max ordine in manuale (seed only)
        rows = [x for x in admin.get(f"{API}/formazione?sezione=manuale").json()]
        max_ord = max((r_["ordine"] for r_ in rows), default=0)
        payload = {"sezione": "manuale", "titolo": "TEST_CAP", "contenuto": "## Prova\n- a",
                   "categoria": "generale"}
        r = admin.post(f"{API}/formazione", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["titolo"] == "TEST_CAP"
        assert doc["ordine"] == max_ord + 1, f"expected {max_ord+1}, got {doc['ordine']}"
        assert doc["categoria"] == "generale"
        assert "_id" not in doc
        STATE["created_ids"].append(doc["id"])
        STATE["last_id"] = doc["id"]

    def test_patch(self, admin):
        _id = STATE["last_id"]
        payload = {"sezione": "manuale", "titolo": "TEST_CAP_MOD", "contenuto": "## Prova mod",
                   "categoria": "generale"}
        r = admin.patch(f"{API}/formazione/{_id}", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["titolo"] == "TEST_CAP_MOD"
        # Verify persistence
        rows = admin.get(f"{API}/formazione?sezione=manuale").json()
        found = [r_ for r_ in rows if r_["id"] == _id]
        assert found and found[0]["titolo"] == "TEST_CAP_MOD"

    def test_invalid_section_on_create_400(self, admin):
        r = admin.post(f"{API}/formazione", json={"sezione": "wrong", "titolo": "TEST_x"}, timeout=15)
        assert r.status_code == 400

    def test_michael_read_ok(self, michael_with_2fa):
        r = michael_with_2fa.get(f"{API}/formazione", timeout=30)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 40

    def test_michael_post_403(self, michael_with_2fa):
        r = michael_with_2fa.post(f"{API}/formazione",
                                  json={"sezione": "manuale", "titolo": "TEST_forbidden"}, timeout=15)
        assert r.status_code == 403

    def test_michael_patch_403(self, michael_with_2fa):
        _id = STATE["last_id"]
        r = michael_with_2fa.patch(f"{API}/formazione/{_id}",
                                   json={"sezione": "manuale", "titolo": "TEST_x"}, timeout=15)
        assert r.status_code == 403

    def test_michael_delete_403(self, michael_with_2fa):
        _id = STATE["last_id"]
        r = michael_with_2fa.delete(f"{API}/formazione/{_id}", timeout=15)
        assert r.status_code == 403

    def test_delete(self, admin):
        _id = STATE["last_id"]
        r = admin.delete(f"{API}/formazione/{_id}", timeout=15)
        assert r.status_code == 200
        # verify gone
        rows = admin.get(f"{API}/formazione").json()
        assert not any(r_["id"] == _id for r_ in rows)
        STATE["created_ids"].remove(_id)


# ---------- Sync-fogli dry_run ----------
class TestSyncFogli:
    def test_sync_admin_dry_run(self, admin):
        r = admin.post(f"{API}/admin/sync-fogli", json={"dry_run": True}, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("dry_run") is True
        assert "energia" in body and "riparazioni" in body
        en = body["energia"]
        for k in ("nuovi", "aggiornati", "invariati", "negozi"):
            assert k in en, f"energia missing key {k}"
        rp = body["riparazioni"]
        for k in ("nuove", "aggiornate"):
            assert k in rp, f"riparazioni missing key {k}"
        assert "negozi" in rp
        # Expected already-synced state
        assert en["nuovi"] == 0, f"expected nuovi=0, got {en['nuovi']} - examples: {en.get('esempi_nuovi')}"
        assert en["aggiornati"] == 0, f"expected aggiornati=0, got {en['aggiornati']}"
        assert rp["nuove"] == 0, f"expected nuove=0, got {rp['nuove']} - examples: {rp.get('esempi_nuove')}"

    def test_sync_non_admin_403(self, michael_with_2fa):
        r = michael_with_2fa.post(f"{API}/admin/sync-fogli", json={"dry_run": True}, timeout=30)
        assert r.status_code == 403


# ---------- Cleanup ----------
def test_zzz_cleanup(admin):
    for _id in list(STATE["created_ids"]):
        admin.delete(f"{API}/formazione/{_id}", timeout=15)
    # verify no TEST_ residuals
    rows = admin.get(f"{API}/formazione").json()
    left = [r_ for r_ in rows if r_["titolo"].startswith("TEST_")]
    assert not left, f"TEST_ leftovers: {left}"
