"""E2E backend tests for Gestionale Utenze (auth, RBAC, clients, stores, users, dashboard, alerts)."""
import os
import uuid
from datetime import date

import pytest
import requests
from dateutil.relativedelta import relativedelta
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "admin": ("rsriparazioni@gmail.com", "Devis2026!"),
    "deborah": ("deborah@cambiaora.local", "Deborah2026!"),
    "michael": ("michael@cambiaora.local", "Michael2026!"),
    "lorenzo": ("lorenzo@cambiaora.local", "Lorenzo2026!"),
    "kevin": ("kevin@cambiaora.local", "Kevin2026!"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


def _client(email, password):
    r = _login(email, password)
    if r.status_code != 200:
        pytest.fail(f"Login failed for {email}: {r.status_code} {r.text[:300]}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"})
    return s, r.json()["user"]


@pytest.fixture(scope="session")
def admin():
    s, u = _client(*CREDS["admin"])
    return s


@pytest.fixture(scope="session")
def admin_user():
    _, u = _client(*CREDS["admin"])
    return u


@pytest.fixture(scope="session")
def michael():
    return _client(*CREDS["michael"])


@pytest.fixture(scope="session")
def lorenzo():
    return _client(*CREDS["lorenzo"])


@pytest.fixture(scope="session")
def deborah():
    return _client(*CREDS["deborah"])


# ---------------- Health / auth ----------------
class TestAuth:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=30)
        assert r.status_code == 200
        assert "message" in r.json()

    @pytest.mark.parametrize("key", list(CREDS.keys()))
    def test_login_all_seeded_users(self, key):
        email, pwd = CREDS[key]
        r = _login(email, pwd)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data.get("token"), str) and len(data["token"]) > 20
        assert data["user"]["email"] == email
        assert "password_hash" not in data["user"]

    def test_me_matches_login(self, admin, admin_user):
        r = admin.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == admin_user["email"]
        assert r.json()["role"] == "admin"

    def test_no_token_401(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401

    def test_invalid_token_401(self):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"}, timeout=30)
        assert r.status_code == 401

    def test_bad_password_401(self):
        # unique non-existing email so lockout never affects real accounts
        r = _login(f"nouser_{uuid.uuid4().hex[:8]}@test.local", "wrongpass")
        assert r.status_code == 401

    def test_logout(self, admin):
        r = admin.post(f"{API}/auth/logout", timeout=30)
        assert r.status_code == 200

    def test_bcrypt_hash_format_and_lockout(self):
        """5 failed logins on a throwaway email must return 429 afterwards."""
        email = f"lockout_{uuid.uuid4().hex[:8]}@test.local"
        codes = [_login(email, "wrong").status_code for _ in range(5)]
        assert all(c == 401 for c in codes), codes
        assert _login(email, "wrong").status_code == 429


# ---------------- RBAC ----------------
class TestRBAC:
    def test_admin_sees_all_clients(self, admin):
        r = admin.get(f"{API}/clients", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) >= 10

    def test_deborah_can_view_all(self, deborah, admin):
        s, u = deborah
        assert u["can_view_all"] is True
        r = s.get(f"{API}/clients", timeout=30)
        assert r.status_code == 200
        assert len(r.json()) == len(admin.get(f"{API}/clients", timeout=30).json())

    def test_michael_scope(self, michael, admin):
        s, u = michael
        stores = {st["id"]: st["nome"] for st in admin.get(f"{API}/stores", timeout=30).json()}
        allowed = {stores[i] for i in u["store_ids"]}
        assert allowed == {"Tirano", "Sondrio", "Sondrio Grosio"}
        clients = s.get(f"{API}/clients", timeout=30).json()
        assert len(clients) == 5, [f"{c['cognome']} {c['nome']}" for c in clients]
        assert all(c["venditore_id"] in u["store_ids"] for c in clients)

    def test_lorenzo_scope(self, lorenzo, admin):
        s, u = lorenzo
        clients = s.get(f"{API}/clients", timeout=30).json()
        assert len(clients) == 2, [c["cognome"] for c in clients]
        assert all(c["venditore_id"] in u["store_ids"] for c in clients)

    def test_store_user_forbidden_users_endpoint(self, michael):
        s, _ = michael
        assert s.get(f"{API}/users", timeout=30).status_code == 403

    def test_store_user_forbidden_operators_stats(self, michael):
        s, _ = michael
        assert s.get(f"{API}/operators/stats", timeout=30).status_code == 403

    def test_store_user_forbidden_send_digest(self, michael):
        s, _ = michael
        assert s.post(f"{API}/alerts/send-digest", timeout=60).status_code == 403

    def test_store_user_stores_scoped(self, michael):
        s, u = michael
        stores = s.get(f"{API}/stores", timeout=30).json()
        assert {st["id"] for st in stores} == set(u["store_ids"])

    def test_cross_scope_client_read_404(self, lorenzo, michael):
        ls, _ = lorenzo
        ms, _ = michael
        m_client_id = ms.get(f"{API}/clients", timeout=30).json()[0]["id"]
        assert ls.get(f"{API}/clients/{m_client_id}", timeout=30).status_code == 404

    def test_store_user_cannot_delete_client(self, michael):
        s, _ = michael
        cid = s.get(f"{API}/clients", timeout=30).json()[0]["id"]
        assert s.delete(f"{API}/clients/{cid}", timeout=30).status_code == 403


# ---------------- Business logic: dates + payment reset ----------------
class TestBusinessLogic:
    def test_computed_dates(self, admin):
        clients = admin.get(f"{API}/clients", timeout=30).json()
        checked = 0
        for c in clients:
            if not c.get("data_contratto"):
                continue
            d0 = date.fromisoformat(c["data_contratto"][:10])
            assert c["data_attivazione"] == (d0 + relativedelta(months=2)).isoformat()
            assert c["data_rinnovo"] == (d0 + relativedelta(months=10)).isoformat()
            assert c["data_scadenza"] == (d0 + relativedelta(months=14)).isoformat()
            assert c["giorni_al_rinnovo"] == (date.fromisoformat(c["data_rinnovo"]) - date.today()).days
            checked += 1
        assert checked >= 10

    def test_payment_reset_after_6_months(self, admin):
        clients = admin.get(f"{API}/clients", timeout=30).json()
        mario = next(c for c in clients if c["cognome"] == "Rossi" and c["nome"] == "Mario")
        assert mario["pagato"] is True
        assert mario["pagato_effettivo"] is False, "pagato 7 mesi fa deve resettare a non pagato"
        giuseppe = next(c for c in clients if c["cognome"] == "Bianchi")
        assert giuseppe["pagato_effettivo"] is True

    def test_no_mongo_id_leak(self, admin):
        for path in ["/clients", "/stores", "/users", "/operators/stats", "/meta", "/dashboard/stats", "/alerts"]:
            r = admin.get(f"{API}{path}", timeout=30)
            assert r.status_code == 200, path
            assert '"_id"' not in r.text, path


# ---------------- Clients CRUD ----------------
class TestClientsCRUD:
    created = []

    def test_create_read_update_delete(self, admin):
        meta = admin.get(f"{API}/meta", timeout=30).json()
        store_id = meta["stores"][0]["id"]
        op_id = meta["operators"][0]["id"]
        payload = {
            "nome": "TEST_Nome", "cognome": "TEST_Cognome", "tipo_cliente": "privato",
            "codice_fiscale": "RSSMRA80A01F205X", "indirizzo": "Via Test 1",
            "pod": "IT001E99999999", "email": "test_qa@esempio.it", "telefono": "3339998877",
            "kw_potenza": 4.5, "tipo_bolletta": "luce", "fornitore_provenienza": "Enel Energia",
            "costo_kwh_attuale": 0.31, "spese_fisse_attuale": 9.5,
            "data_contratto": date.today().isoformat(), "tipo_contratto": "fisso",
            "nuovo_fornitore": "Sorgenia", "costo_kwh_nuovo": 0.22,
            "privacy_firmata": True, "lavorazione": "da_quotare",
            "venditore_id": store_id, "operatore_id": op_id,
        }
        r = admin.post(f"{API}/clients", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        c = r.json()
        cid = c["id"]
        TestClientsCRUD.created.append(cid)
        assert c["nome"] == "TEST_Nome"
        assert c["pagato"] is False
        assert c["data_attivazione"] == (date.today() + relativedelta(months=2)).isoformat()

        # GET verify persistence + history log
        g = admin.get(f"{API}/clients/{cid}", timeout=30)
        assert g.status_code == 200
        gd = g.json()
        assert gd["cognome"] == "TEST_Cognome"
        assert gd["venditore_id"] == store_id
        assert len(gd["history"]) >= 1
        assert gd["history"][0]["status"] == "da_quotare"

        # UPDATE lavorazione
        payload["lavorazione"] = "cambio_effettuato"
        payload["note"] = "aggiornato dal test"
        u = admin.patch(f"{API}/clients/{cid}", json=payload, timeout=30)
        assert u.status_code == 200, u.text[:300]
        assert u.json()["lavorazione"] == "cambio_effettuato"
        g2 = admin.get(f"{API}/clients/{cid}", timeout=30).json()
        assert g2["lavorazione"] == "cambio_effettuato"
        assert g2["note"] == "aggiornato dal test"
        assert len(g2["history"]) >= 2

        # MARK PAID
        p = admin.post(f"{API}/clients/{cid}/mark-paid", timeout=30)
        assert p.status_code == 200
        g3 = admin.get(f"{API}/clients/{cid}", timeout=30).json()
        assert g3["pagato"] is True and g3["pagato_effettivo"] is True
        assert g3["last_payment_date"] == date.today().isoformat()

        # DELETE
        d = admin.delete(f"{API}/clients/{cid}", timeout=30)
        assert d.status_code == 200
        assert admin.get(f"{API}/clients/{cid}", timeout=30).status_code == 404
        TestClientsCRUD.created.remove(cid)

    def test_store_user_create_forced_to_own_store(self, michael, admin):
        s, u = michael
        r = s.post(f"{API}/clients", json={"nome": "TEST_Neg", "cognome": "TEST_Scope",
                                           "venditore_id": "id-inesistente",
                                           "data_contratto": date.today().isoformat()}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        c = r.json()
        assert c["venditore_id"] in u["store_ids"], "venditore_id deve essere forzato al negozio dell'utente"
        admin.delete(f"{API}/clients/{c['id']}", timeout=30)

    def test_missing_required_fields_422(self, admin):
        r = admin.post(f"{API}/clients", json={"nome": "solo nome"}, timeout=30)
        assert r.status_code == 422

    def test_client_not_found_404(self, admin):
        assert admin.get(f"{API}/clients/{uuid.uuid4()}", timeout=30).status_code == 404

    def test_filters(self, admin):
        all_c = admin.get(f"{API}/clients", timeout=30).json()
        gas = admin.get(f"{API}/clients", params={"tipo_bolletta": "gas"}, timeout=30).json()
        assert gas and all(c["tipo_bolletta"] == "gas" for c in gas)
        lav = admin.get(f"{API}/clients", params={"lavorazione": "rinnovato"}, timeout=30).json()
        assert all(c["lavorazione"] == "rinnovato" for c in lav)
        q = admin.get(f"{API}/clients", params={"q": "Rossi"}, timeout=30).json()
        assert q and all("Rossi" in (c["cognome"] + c["nome"]) for c in q)
        assert len(gas) < len(all_c)
        # regex injection safety
        assert admin.get(f"{API}/clients", params={"q": "("}, timeout=30).status_code == 200


# ---------------- Stores ----------------
class TestStores:
    def test_list_and_mark_paid_and_create(self, admin):
        stores = admin.get(f"{API}/stores", timeout=30).json()
        assert len(stores) >= 7
        for s in stores:
            assert "pagato_effettivo" in s and "contratti_mese" in s and "totale_clienti" in s

        target = stores[0]["id"]
        r = admin.post(f"{API}/stores/{target}/mark-paid", timeout=30)
        assert r.status_code == 200
        after = next(s for s in admin.get(f"{API}/stores", timeout=30).json() if s["id"] == target)
        assert after["pagato"] is True and after["pagato_effettivo"] is True

        c = admin.post(f"{API}/stores", json={"nome": "TEST_Negozio", "referente": "QA"}, timeout=30)
        assert c.status_code == 200, c.text[:300]
        new_id = c.json()["id"]
        assert c.json()["pagato"] is False
        listed = admin.get(f"{API}/stores", timeout=30).json()
        assert any(s["id"] == new_id for s in listed)

        up = admin.patch(f"{API}/stores/{new_id}", json={"referente": "QA2"}, timeout=30)
        assert up.status_code == 200 and up.json()["referente"] == "QA2"

    def test_store_mark_paid_404(self, admin):
        assert admin.post(f"{API}/stores/{uuid.uuid4()}/mark-paid", timeout=30).status_code == 404

    def test_store_user_cannot_create_store(self, michael):
        s, _ = michael
        assert s.post(f"{API}/stores", json={"nome": "TEST_X"}, timeout=30).status_code == 403


# ---------------- Users (admin) ----------------
class TestUsers:
    def test_user_lifecycle(self, admin):
        stores = admin.get(f"{API}/stores", timeout=30).json()
        email = f"test_qa_{uuid.uuid4().hex[:6]}@cambiaora.local"
        r = admin.post(f"{API}/users", json={"name": "TEST_Utente", "email": email,
                                             "password": "TestQa2026!", "role": "negozio",
                                             "store_ids": [stores[0]["id"]]}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        uid = r.json()["id"]
        assert r.json()["email"] == email
        assert r.json()["store_ids"] == [stores[0]["id"]]

        # new user can login
        assert _login(email, "TestQa2026!").status_code == 200

        # duplicate email rejected
        assert admin.post(f"{API}/users", json={"name": "x", "email": email, "password": "TestQa2026!"},
                          timeout=30).status_code == 400
        # invalid role rejected
        assert admin.post(f"{API}/users", json={"name": "x", "email": f"z{email}", "password": "p",
                                                "role": "superuser"}, timeout=30).status_code == 400

        # deactivate -> login 403
        d = admin.patch(f"{API}/users/{uid}", json={"active": False}, timeout=30)
        assert d.status_code == 200 and d.json()["active"] is False
        assert _login(email, "TestQa2026!").status_code == 403

        # reset password + reactivate
        p = admin.patch(f"{API}/users/{uid}", json={"active": True, "password": "NewQa2026!"}, timeout=30)
        assert p.status_code == 200
        assert _login(email, "NewQa2026!").status_code == 200
        assert admin.patch(f"{API}/users/{uuid.uuid4()}", json={"name": "x"}, timeout=30).status_code == 404

    def test_users_list_no_hash(self, admin):
        users = admin.get(f"{API}/users", timeout=30).json()
        assert len(users) >= 5
        assert all("password_hash" not in u for u in users)


# ---------------- Dashboard / alerts / meta / operators ----------------
class TestDashboardAlerts:
    def test_dashboard_stats(self, admin):
        s = admin.get(f"{API}/dashboard/stats", timeout=30).json()
        assert s["totale_clienti"] >= 10
        assert s["luce"] + s["gas"] == s["totale_clienti"]
        assert s["non_pagati"] >= 1
        assert isinstance(s["per_lavorazione"], dict) and s["per_lavorazione"]

    def test_dashboard_scoped_for_store_user(self, michael):
        s, _ = michael
        st = s.get(f"{API}/dashboard/stats", timeout=30).json()
        assert st["totale_clienti"] == 5

    def test_alerts(self, admin):
        a = admin.get(f"{API}/alerts", timeout=30).json()
        assert set(a.keys()) == {"rinnovi", "pagamenti_clienti", "pagamenti_negozi"}
        assert any(p["nome"] == "Mario" for p in a["pagamenti_clienti"])
        if len(a["rinnovi"]) > 1:
            assert a["rinnovi"] == sorted(a["rinnovi"], key=lambda x: x["giorni"])

    def test_meta(self, admin):
        m = admin.get(f"{API}/meta", timeout=30).json()
        assert len(m["suppliers"]) >= 30
        assert len(m["lavorazioni"]) == 13
        assert m["stores"] and m["operators"]

    def test_operators_stats(self, admin):
        r = admin.get(f"{API}/operators/stats", timeout=30)
        assert r.status_code == 200
        ops = r.json()
        assert ops
        for o in ops:
            assert {"id", "name", "lavorazioni_mese", "per_status", "clienti_gestiti", "chiusi_mese"} <= set(o)
        deb = next(o for o in ops if o["name"] == "Deborah")
        assert deb["clienti_gestiti"] >= 10

    def test_cron_requires_secret(self):
        r = requests.post(f"{API}/cron/daily-digest", timeout=30)
        assert r.status_code == 401

    def test_send_digest_admin(self, admin):
        r = admin.post(f"{API}/alerts/send-digest", timeout=90)
        # 502 expected if ALERT_EMAIL recipient is undeliverable (known env issue)
        assert r.status_code in (200, 502), r.text[:300]
        if r.status_code == 502:
            pytest.skip(f"Email proxy rejected recipient: {r.text[:200]}")
