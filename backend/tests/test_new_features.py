"""Backend tests for new CRM features (iteration 33).
Covers:
  - Client search (q partial / multi-word)
  - Dashboard: /api/attivita/mese shape & /api/kpi/voci includes pellicola, cover, cavo_caricatore
  - Servizi creation guardrails: accessori requires magazzino_item_id OR non_a_magazzino
  - SIM creation without magazzino_item_id OK
  - Portali CRUD + presence check for operator used after SIM save
"""
import os
import pyotp
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rsriparazioni@gmail.com"
ADMIN_PASSWORD = "EnricoRS@26"
TOTP_SECRET = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    mfa_token = r.json().get("mfa_token")
    assert mfa_token
    code = pyotp.TOTP(TOTP_SECRET).now()
    r = requests.post(f"{BASE}/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": code}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Clienti search ----------
class TestClientiSearch:
    def test_full_name_match(self, h):
        r = requests.get(f"{BASE}/api/clients", params={"q": "Rossi Mario"}, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        found = [c for c in r.json() if (c.get("cognome") or "").lower() == "rossi" and (c.get("nome") or "").lower() == "mario"]
        assert found, "Rossi Mario non trovato con q='Rossi Mario'"

    def test_partial_name_match(self, h):
        r = requests.get(f"{BASE}/api/clients", params={"q": "rossi ma"}, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        found = [c for c in r.json() if (c.get("cognome") or "").lower() == "rossi" and (c.get("nome") or "").lower().startswith("ma")]
        assert found, "Rossi Mario non trovato con q='rossi ma' (ricerca parziale)"


# ---------- KPI / Attività mese ----------
class TestKpiAttivitaMese:
    def test_kpi_voci_contains_new_items(self, h):
        r = requests.get(f"{BASE}/api/kpi/voci", headers=h, timeout=20)
        assert r.status_code == 200
        ids = {v["id"] for v in r.json().get("voci", [])}
        for want in ("pellicola", "cover", "cavo_caricatore"):
            assert want in ids, f"KPI voce mancante: {want}"

    def test_attivita_mese_shape(self, h):
        r = requests.get(f"{BASE}/api/attivita/mese", headers=h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("anno", "mese", "totali", "obiettivi", "totale_mese"):
            assert key in d, f"Chiave mancante in /attivita/mese: {key}"
        assert isinstance(d["totali"], dict)
        assert isinstance(d["obiettivi"], list)
        assert isinstance(d["totale_mese"], int)


# ---------- Servizi guardrails (cliente TEST_82685b) ----------
CLIENT_TEST_ID = "82685b"  # suffisso


@pytest.fixture(scope="session")
def test_client_id(h):
    # Cerca cliente con suffisso 82685b nel suo id (campo id uuid). In alternativa qualunque cliente di test.
    r = requests.get(f"{BASE}/api/clients", headers=h, timeout=20)
    assert r.status_code == 200
    clients = r.json()
    # Try to find exact id containing suffix
    for c in clients:
        if CLIENT_TEST_ID in (c.get("id") or ""):
            return c["id"]
    # fallback: pick first client (just to run smoke)
    assert clients, "Nessun cliente disponibile"
    return clients[0]["id"]


_created_services = []


class TestServiziGuardrails:
    def test_accessori_without_magazzino_rejects(self, h, test_client_id):
        payload = {"client_id": test_client_id, "tipo": "accessori", "prodotto": "TEST acc senza nulla", "importo": 10}
        r = requests.post(f"{BASE}/api/servizi", json=payload, headers=h, timeout=20)
        assert r.status_code == 400, f"Dovrebbe rifiutare: {r.status_code} {r.text}"
        assert "magazzino" in r.text.lower() or "scegli" in r.text.lower()

    def test_accessori_with_non_a_magazzino_ok(self, h, test_client_id):
        payload = {"client_id": test_client_id, "tipo": "accessori", "prodotto": "TEST acc non_a_magazzino",
                   "importo": 15, "non_a_magazzino": True}
        r = requests.post(f"{BASE}/api/servizi", json=payload, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id")
        _created_services.append(d["id"])

    def test_accessori_with_magazzino_item_decrements(self, h, test_client_id):
        # Cerca un articolo in magazzino categoria accessori con quantità > 0
        r = requests.get(f"{BASE}/api/magazzino", params={"categoria": "accessori"}, headers=h, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"GET /api/magazzino non disponibile: {r.status_code}")
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        candidate = next((it for it in items if (it.get("categoria") == "accessori") and int(it.get("quantita") or 0) > 0), None)
        if not candidate:
            pytest.skip("Nessun articolo accessori con giacenza > 0 in magazzino")
        qty_before = int(candidate["quantita"])
        payload = {"client_id": test_client_id, "tipo": "accessori", "prodotto": candidate.get("nome", "TEST"),
                   "importo": 20, "magazzino_item_id": candidate["id"], "quantita": 1}
        r = requests.post(f"{BASE}/api/servizi", json=payload, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        _created_services.append(r.json()["id"])
        # verify stock decrement
        r2 = requests.get(f"{BASE}/api/magazzino", params={"categoria": "accessori"}, headers=h, timeout=20)
        items2 = r2.json()
        if isinstance(items2, dict):
            items2 = items2.get("items") or items2.get("data") or []
        upd = next((it for it in items2 if it["id"] == candidate["id"]), None)
        assert upd is not None
        assert int(upd["quantita"]) == qty_before - 1, f"Giacenza non decrementata: {qty_before} -> {upd['quantita']}"

    def test_sim_without_magazzino_ok(self, h, test_client_id):
        payload = {"client_id": test_client_id, "tipo": "sim", "operatore_tel": "WINDTRE",
                   "tipo_attivazione": "nuovo", "numero": "3331234567"}
        r = requests.post(f"{BASE}/api/servizi", json=payload, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        _created_services.append(r.json()["id"])


# ---------- Portali ----------
class TestPortali:
    def test_list_portali(self, h):
        r = requests.get(f"{BASE}/api/portali", headers=h, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_portale_mobile_for_operator(self, h):
        # ensure a portale esists for WINDTRE in mobile (seed should already have it)
        payload = {"sezione": "mobile", "operatore": "WINDTRE", "nome": "TEST portale",
                   "url": "https://example.com", "note": "test"}
        r = requests.post(f"{BASE}/api/portali", json=payload, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id")
        assert d["operatore"] == "WINDTRE"
        # cleanup
        requests.delete(f"{BASE}/api/portali/{d['id']}", headers=h, timeout=20)


# ---------- Cleanup ----------
def test_zz_cleanup_servizi(h):
    for sid in _created_services:
        requests.delete(f"{BASE}/api/servizi/{sid}", headers=h, timeout=20)
