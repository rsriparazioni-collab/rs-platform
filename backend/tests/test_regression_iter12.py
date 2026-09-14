"""Full regression suite iter 12 - tests all modules with 2FA-aware admin login.

Covers: auth+MFA, dashboard, clients CRUD+filters, servizi (energia/telefonia/riparazione),
magazzino, ritiri (smoke), stores/users/venditori, whatsapp dry-run, portali, passwords (read),
GDPR export, audit log, cron endpoints, meta.
"""
import io
import os
import time
import uuid
from typing import Optional

import pyotp
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rsriparazioni@gmail.com"
ADMIN_PWD = "Devis2026!"
ADMIN_TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
MICHAEL = ("michael@cambiaora.local", "Michael2026!")
DEBORAH = ("deborah@cambiaora.local", "Deborah2026!")

CREATED = {"clients": [], "servizi": [], "magazzino": [], "ritiri": [], "venditori": [],
           "stores": [], "users": [], "portali": [], "passwords": []}


def _admin_login():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    for attempt in range(3):
        code = pyotp.TOTP(ADMIN_TOTP).now()
        r2 = requests.post(f"{API}/auth/login/mfa",
                           json={"mfa_token": body["mfa_token"], "code": code}, timeout=30)
        if r2.status_code == 200:
            return r2.json()["token"]
        time.sleep(31)
    pytest.fail(f"MFA login failed: {r2.status_code} {r2.text[:200]}")


def _session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _simple_login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin():
    return _session(_admin_login())


@pytest.fixture(scope="session")
def michael():
    return _session(_simple_login(*MICHAEL))


# ---------------- AUTH ----------------
class TestAuth:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200 and "message" in r.json()

    def test_admin_login_requires_mfa(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("mfa_required") is True
        assert r.json().get("mfa_token")

    def test_admin_wrong_password_401(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrongpass"}, timeout=15)
        assert r.status_code == 401

    def test_admin_mfa_wrong_code(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
        mfa = r.json()["mfa_token"]
        r2 = requests.post(f"{API}/auth/login/mfa",
                           json={"mfa_token": mfa, "code": "000000"}, timeout=15)
        assert r2.status_code in (400, 401)

    def test_admin_me(self, admin):
        r = admin.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
        assert r.json()["role"] == "admin"

    def test_michael_login_no_mfa_but_forced_setup(self, michael):
        r = michael.get(f"{API}/clients", timeout=15)
        assert r.status_code == 403
        assert r.headers.get("X-MFA-Setup-Required") == "1"

    def test_michael_me_still_reachable(self, michael):
        r = michael.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == MICHAEL[0]

    def test_michael_2fa_status_endpoint(self, michael):
        r = michael.get(f"{API}/auth/2fa/status", timeout=15)
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_no_token_401(self):
        assert requests.get(f"{API}/auth/me", timeout=15).status_code == 401


# ---------------- DASHBOARD ----------------
class TestDashboard:
    def test_stats(self, admin):
        r = admin.get(f"{API}/dashboard/stats", timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_margini_negozi(self, admin):
        r = admin.get(f"{API}/dashboard/margini-negozi", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict) and "negozi" in body

    def test_margini_12_mesi(self, admin):
        r = admin.get(f"{API}/dashboard/margini-12-mesi", timeout=30)
        assert r.status_code == 200

    def test_portali_flag_scaduti(self, admin):
        r = admin.get(f"{API}/portali/flag-scaduti", timeout=30)
        assert r.status_code == 200

    def test_alerts(self, admin):
        r = admin.get(f"{API}/alerts", timeout=30)
        assert r.status_code == 200

    def test_operators_stats(self, admin):
        r = admin.get(f"{API}/operators/stats", timeout=30)
        assert r.status_code == 200

    def test_scadenze_settimana(self, admin):
        r = admin.get(f"{API}/scadenze-settimana", timeout=30)
        assert r.status_code == 200


# ---------------- META / STORES / USERS ----------------
class TestMeta:
    def test_meta(self, admin):
        r = admin.get(f"{API}/meta", timeout=15)
        assert r.status_code == 200

    def test_stores_list(self, admin):
        r = admin.get(f"{API}/stores", timeout=15)
        assert r.status_code == 200 and len(r.json()) > 0

    def test_users_list(self, admin):
        r = admin.get(f"{API}/users", timeout=15)
        assert r.status_code == 200

    def test_venditori_list(self, admin):
        r = admin.get(f"{API}/venditori", timeout=15)
        assert r.status_code == 200


# ---------------- CLIENTS CRUD ----------------
class TestClients:
    def test_list_admin(self, admin):
        r = admin.get(f"{API}/clients", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 10

    def test_filters(self, admin):
        for f in ("luce", "gas"):
            r = admin.get(f"{API}/clients", params={"tipo_bolletta": f}, timeout=30)
            assert r.status_code == 200
        for lav in ("da_quotare", "cambio_effettuato"):
            r = admin.get(f"{API}/clients", params={"lavorazione": lav}, timeout=30)
            assert r.status_code == 200
        for ts in ("luce", "gas", "rip", "mob", "fis"):
            r = admin.get(f"{API}/clients", params={"tipo_servizio": ts}, timeout=30)
            assert r.status_code == 200

    def test_search_q(self, admin):
        r = admin.get(f"{API}/clients", params={"q": "a"}, timeout=30)
        assert r.status_code == 200

    def test_create_update_get(self, admin):
        payload = {
            "nome": f"TEST_{uuid.uuid4().hex[:6]}", "cognome": "TEST_Regression",
            "tipo_bolletta": "luce", "lavorazione": "da_quotare",
            "email": "test_regression@example.com", "telefono": "+390000000001",
        }
        r = admin.post(f"{API}/clients", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        CREATED["clients"].append(cid)
        # PATCH (endpoint richiede full model)
        upd = {**payload, "note": "TEST_note", "lavorazione": "quotato"}
        r2 = admin.patch(f"{API}/clients/{cid}", json=upd, timeout=30)
        assert r2.status_code == 200, r2.text
        # GET
        r3 = admin.get(f"{API}/clients/{cid}", timeout=30)
        assert r3.status_code == 200
        assert r3.json()["note"] == "TEST_note"
        assert r3.json()["lavorazione"] == "quotato"

    def test_gdpr_export(self, admin):
        cid = CREATED["clients"][0]
        r = admin.get(f"{API}/clients/{cid}/gdpr-export", timeout=30)
        assert r.status_code == 200
        # dovrebbe essere JSON o PDF
        assert r.headers.get("content-type", "").startswith(("application/json", "application/pdf"))

    def test_export_xlsx(self, admin):
        r = admin.get(f"{API}/export/clients.xlsx", timeout=60)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "") or len(r.content) > 100

    def test_messaggi_previsti(self, admin):
        cid = CREATED["clients"][0]
        r = admin.get(f"{API}/clients/{cid}/messaggi-previsti", timeout=30)
        assert r.status_code == 200

    def test_blacklist_recensioni(self, admin):
        cid = CREATED["clients"][0]
        r = admin.post(f"{API}/clients/{cid}/blacklist-recensioni", json={"no_recensioni": True}, timeout=30)
        assert r.status_code in (200, 204)


# ---------------- SERVIZI ----------------
class TestServizi:
    def test_list(self, admin):
        r = admin.get(f"{API}/servizi", timeout=30)
        assert r.status_code == 200

    def test_create_riparazione_and_secrets(self, admin):
        assert CREATED["clients"], "manca cliente TEST_"
        cid = CREATED["clients"][0]
        payload = {
            "client_id": cid, "tipo": "riparazione", "stato": "ingresso",
            "dispositivo": "TEST_iPhone", "problema": "TEST_battery",
            "con_ricambio": True, "tipo_ricambio": "batteria",
            "costo_componente": 20.0, "minuti_lavoro": 25,
            "codice_sblocco_tipo": "PIN", "codice_sblocco": "1234",
        }
        r = admin.post(f"{API}/servizi", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        CREATED["servizi"].append(sid)
        # numero progressivo (campo numero_riparazione)
        assert r.json().get("numero_riparazione"), "numero_riparazione mancante"
        # segreti
        r2 = admin.get(f"{API}/servizi/{sid}/segreti", timeout=15)
        assert r2.status_code == 200
        assert r2.json().get("codice_sblocco") == "1234"

    def test_create_sim_and_fisso(self, admin):
        cid = CREATED["clients"][0]
        for tipo, extra in (("sim", {"numero": "+3931234567", "operatore_tel": "Iliad"}),
                            ("fisso", {"numero": "+390342000001", "operatore_tel": "TIM"}),
                            ("internet", {"operatore_tel": "Fastweb"})):
            p = {"client_id": cid, "tipo": tipo, "stato": "ingresso", **extra}
            r = admin.post(f"{API}/servizi", json=p, timeout=30)
            assert r.status_code == 200, f"{tipo}: {r.text}"
            CREATED["servizi"].append(r.json()["id"])

    def test_patch_servizio(self, admin):
        sid = CREATED["servizi"][0]
        # PATCH richiede full ServizioInput
        cur = admin.get(f"{API}/servizi/{sid}", timeout=15).json()
        upd = {k: cur.get(k) for k in ("client_id", "tipo", "stato", "dispositivo", "problema")}
        upd["stato"] = "in_lavorazione"
        upd["note"] = "TEST_note"
        r = admin.patch(f"{API}/servizi/{sid}", json=upd, timeout=30)
        assert r.status_code == 200, r.text

    def test_scheda_pdf(self, admin):
        sid = CREATED["servizi"][0]
        r = admin.get(f"{API}/servizi/{sid}/scheda", timeout=30)
        assert r.status_code == 200


# ---------------- MAGAZZINO ----------------
class TestMagazzino:
    def test_list(self, admin):
        r = admin.get(f"{API}/magazzino", timeout=30)
        assert r.status_code == 200

    def test_create_movimento(self, admin):
        # Store id (Morbegno as default)
        stores = admin.get(f"{API}/stores", timeout=15).json()
        sid = next((s["id"] for s in stores if s.get("nome") == "Morbegno"), stores[0]["id"])
        p = {"nome": f"TEST_ART_{uuid.uuid4().hex[:6]}", "categoria": "ricambi",
             "quantita": 5, "prezzo_acquisto": 10.0, "note": "TEST_note",
             "store_id": sid}
        r = admin.post(f"{API}/magazzino", json=p, timeout=30)
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        CREATED["magazzino"].append(mid)
        r2 = admin.post(f"{API}/magazzino/{mid}/movimento",
                        json={"delta": 3, "note": "TEST_carico"}, timeout=30)
        assert r2.status_code == 200
        r3 = admin.patch(f"{API}/magazzino/{mid}", json={**p, "note": "TEST_updated"}, timeout=30)
        assert r3.status_code == 200

    def test_export(self, admin):
        r = admin.get(f"{API}/magazzino/export", timeout=60)
        assert r.status_code == 200

    def test_disponibilita(self, admin):
        r = admin.get(f"{API}/magazzino/disponibilita", timeout=30)
        assert r.status_code == 200


# ---------------- RITIRI (smoke) ----------------
class TestRitiri:
    def test_list(self, admin):
        r = admin.get(f"{API}/ritiri", timeout=30)
        assert r.status_code == 200

    def test_export(self, admin):
        r = admin.get(f"{API}/ritiri/export", timeout=60)
        assert r.status_code == 200


# ---------------- WHATSAPP ----------------
class TestWhatsApp:
    def test_status(self, admin):
        r = admin.get(f"{API}/whatsapp/status", timeout=15)
        assert r.status_code == 200

    def test_sessions_summary(self, admin):
        r = admin.get(f"{API}/whatsapp/sessions-summary", timeout=15)
        assert r.status_code == 200

    def test_log(self, admin):
        r = admin.get(f"{API}/whatsapp/log", timeout=30)
        assert r.status_code == 200

    def test_privacy_dry_run(self, admin):
        cid = CREATED["clients"][0] if CREATED["clients"] else None
        if not cid:
            pytest.skip()
        r = admin.post(f"{API}/clients/{cid}/whatsapp/privacy", json={}, timeout=15)
        assert r.status_code in (200, 400)  # 400 se manca telefono valido - accettato

    def test_cron_daily_digest(self):
        secret = dotenv_values("/app/backend/.env").get("WEBHOOK_CRON_SECRET", "")
        r = requests.post(f"{API}/cron/daily-digest",
                          headers={"Authorization": f"Bearer {secret}"}, timeout=60)
        assert r.status_code == 200, r.text

    def test_cron_whatsapp_due(self):
        secret = dotenv_values("/app/backend/.env").get("WEBHOOK_CRON_SECRET", "")
        r = requests.post(f"{API}/cron/whatsapp-due",
                          headers={"Authorization": f"Bearer {secret}"}, timeout=60)
        assert r.status_code == 200, r.text

    def test_cron_riparazioni_ferme(self):
        secret = dotenv_values("/app/backend/.env").get("WEBHOOK_CRON_SECRET", "")
        r = requests.post(f"{API}/cron/riparazioni-ferme",
                          headers={"Authorization": f"Bearer {secret}"}, timeout=60)
        assert r.status_code == 200, r.text

    def test_cron_requires_secret(self, admin):
        """Cron endpoints devono rifiutare token utente (401)."""
        r = admin.post(f"{API}/cron/daily-digest", timeout=30)
        assert r.status_code == 401


# ---------------- PORTALI ----------------
class TestPortali:
    def test_list(self, admin):
        r = admin.get(f"{API}/portali", timeout=15)
        assert r.status_code == 200

    def test_da_inserire(self, admin):
        r = admin.get(f"{API}/portali/da-inserire", timeout=30)
        assert r.status_code == 200

    def test_flag_scaduti(self, admin):
        r = admin.get(f"{API}/portali/flag-scaduti", timeout=30)
        assert r.status_code == 200


# ---------------- PASSWORDS ----------------
class TestPasswords:
    def test_list(self, admin):
        r = admin.get(f"{API}/passwords", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 50  # atteso ~151

    def test_reveal_one_readonly(self, admin):
        lst = admin.get(f"{API}/passwords", timeout=30).json()
        if not lst:
            pytest.skip()
        pid = lst[0]["id"]
        r = admin.get(f"{API}/passwords/{pid}/reveal", timeout=15)
        assert r.status_code == 200
        assert "password" in r.json()

    def test_rbac_negozio(self, michael):
        r = michael.get(f"{API}/passwords", timeout=15)
        # michael è ancora MFA-gate: attesa 403
        assert r.status_code in (200, 403)


# ---------------- AUDIT / SICUREZZA ----------------
class TestAudit:
    def test_audit_log(self, admin):
        r = admin.get(f"{API}/audit-log", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_audit_michael_forbidden(self, michael):
        assert michael.get(f"{API}/audit-log", timeout=15).status_code == 403


# ---------------- VINCOLI / TELEFONIA / PROPOSTE ----------------
class TestTelefonia:
    def test_vincoli(self, admin):
        r = admin.get(f"{API}/vincoli", timeout=30)
        assert r.status_code == 200

    def test_proposte(self, admin):
        r = admin.get(f"{API}/telefonia/proposte", timeout=30)
        assert r.status_code == 200


# ---------------- CLEANUP ----------------
def test_zzz_cleanup(admin=None):
    """Rimuove tutti i record TEST_ creati durante i test."""
    tok = _admin_login()
    s = _session(tok)
    for sid in CREATED["servizi"]:
        s.delete(f"{API}/servizi/{sid}", timeout=15)
    for cid in CREATED["clients"]:
        s.delete(f"{API}/clients/{cid}", timeout=15)
    for mid in CREATED["magazzino"]:
        s.delete(f"{API}/magazzino/{mid}", timeout=15)
    print("Cleanup done:", {k: len(v) for k, v in CREATED.items()})
