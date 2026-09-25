"""Iter 22 - Backend tests for KPI Team feature (kpi.py)."""
import os
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")


def _login_token() -> str:
    out = subprocess.check_output(["bash", "/app/backend/tests/login_tok.sh"], text=True).strip()
    assert out and "." in out, f"Login failed: {out}"
    return out


@pytest.fixture(scope="module")
def token():
    return _login_token()


@pytest.fixture(scope="module")
def api(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_id(api):
    r = api.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    return r.json()["id"]


# --- kpi/voci ---
def test_voci_returns_33(api):
    r = api.get(f"{BASE_URL}/api/kpi/voci")
    assert r.status_code == 200
    d = r.json()
    assert len(d["voci"]) == 33
    for v in d["voci"]:
        assert set(v.keys()) >= {"id", "label", "area", "fonte"}
    assert "iliad" in d["mnp_operatori"]


# --- POST /attivita ---
_created_ids = []


def test_attivita_pellicola(api):
    r = api.post(f"{BASE_URL}/api/attivita", json={"voce": "pellicola"})
    assert r.status_code == 200
    d = r.json()
    assert d["voce"] == "pellicola"
    assert d["data"]  # date populated
    from datetime import datetime, timezone
    assert d["data"] == datetime.now(timezone.utc).date().isoformat()
    _created_ids.append(d["id"])


def test_attivita_sim_mnp_iliad(api):
    r = api.post(f"{BASE_URL}/api/attivita", json={"voce": "sim_mnp", "dettaglio": "iliad"})
    assert r.status_code == 200
    d = r.json()
    assert d["dettaglio"] == "iliad"
    _created_ids.append(d["id"])


def test_attivita_invalid_voce(api):
    r = api.post(f"{BASE_URL}/api/attivita", json={"voce": "xxx"})
    assert r.status_code == 400


def test_attivita_with_client(api):
    # find an energia client
    r = api.get(f"{BASE_URL}/api/clients", params={"limit": 20})
    lst = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    client_id = None
    for c in lst:
        if c.get("id"):
            client_id = c["id"]
            break
    assert client_id, "Nessun cliente trovato per il test"
    r2 = api.post(f"{BASE_URL}/api/attivita", json={"voce": "eolo_proposto", "client_id": client_id})
    assert r2.status_code == 200
    d = r2.json()
    assert d["client_nome"], f"client_nome vuoto: {d}"
    _created_ids.append(d["id"])


def test_lista_attivita(api, admin_id):
    r = api.get(f"{BASE_URL}/api/attivita")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    for cid in _created_ids:
        assert cid in ids


# --- KPI griglia ---
def test_kpi_grid_pellicola(api, admin_id):
    r = api.get(f"{BASE_URL}/api/kpi", params={"anno": 2026, "mese": 9, "user_id": admin_id})
    assert r.status_code == 200
    d = r.json()
    pell = next(v for v in d["voci"] if v["id"] == "pellicola")
    assert pell["giorni"].get("25", 0) >= 1
    assert "manuale" in pell["fonti_usate"]


def test_kpi_riepilogo(api):
    r = api.get(f"{BASE_URL}/api/kpi/riepilogo", params={"anno": 2026, "mese": 9})
    assert r.status_code == 200
    names = {u["name"] for u in r.json()}
    for n in ["Bruno", "Deborah", "Kevin", "Lorenzo", "Michael", "Seba", "Silvio"]:
        assert any(n.lower() in x.lower() for x in names), f"Manca {n} in {names}"


def test_kpi_utenti_admin(api):
    r = api.get(f"{BASE_URL}/api/kpi/utenti")
    assert r.status_code == 200
    assert len(r.json()) == 7


def test_kpi_export_xlsx(api):
    r = api.get(f"{BASE_URL}/api/kpi/export", params={"anno": 2026, "mese": 9})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers.get("content-type", "")
    assert len(r.content) > 500


# --- DELETE ---
def test_delete_created(api):
    for cid in _created_ids:
        r = api.delete(f"{BASE_URL}/api/attivita/{cid}")
        assert r.status_code == 200


def test_delete_not_found(api):
    r = api.delete(f"{BASE_URL}/api/attivita/nonesistente-123")
    assert r.status_code == 404
