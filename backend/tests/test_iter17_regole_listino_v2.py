"""Iter 17: 14 regole v2, calcolo prezzo su casi reali, parser Sifar dedicato per 49.pdf, ricerca listino."""
import os
import pytest
import pyotp
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
be = dotenv_values("/app/backend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE}/api"
TOTP_SECRET = os.environ.get("TEST_ADMIN_TOTP_SECRET") or be.get("TEST_ADMIN_TOTP_SECRET") or "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"


def _login_with_mfa(email, password, totp_secret=None):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    if d.get("mfa_required"):
        code = pyotp.TOTP(totp_secret).now()
        r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": code}, timeout=30)
        assert r2.status_code == 200, r2.text[:400]
        d = r2.json()
    return d["token"], d["user"]


@pytest.fixture(scope="module")
def admin_headers():
    tok, _ = _login_with_mfa("rsriparazioni@gmail.com", "Devis2026!", TOTP_SECRET)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- 14 regole default ----------
class TestRegole14:
    def test_get_14_regole(self, admin_headers):
        r = requests.get(f"{API}/regole-prezzi", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "regole" in d and "tipologie" in d
        assert len(d["regole"]) == 14, f"expected 14 got {len(d['regole'])}"
        labels = {x["label"] for x in d["regole"]}
        # sanity: check expected tipologie represented
        tips = {x["tipologia"] for x in d["regole"]}
        assert {"display", "display_compatibile", "batteria", "connettore", "fotocamera",
                "vetro_camera", "vetro_posteriore", "altro", "software",
                "vetro_temperato", "pellicola", "cover"}.issubset(tips), tips


# ---------- Calcolo prezzo consigliato via POST /api/servizi ----------
@pytest.fixture(scope="module")
def cliente_id(admin_headers):
    r = requests.get(f"{API}/clients", headers=admin_headers, params={"limit": 5}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("clients") or []
    assert items, "No clients found"
    return items[0]["id"]


CASES = [
    # (dispositivo, con_ricambio, tipo_ricambio, costo, minuti, expected)
    ("TEST_ iPhone 11", True, "display_compatibile", 17, 30, 100.0),
    ("TEST_ iPhone 13 Pro Max", True, "display", 70, 30, 220.0),
    ("TEST_ Samsung Galaxy A15", True, "display", 34, 30, 100.0),
    ("TEST_ iPhone 12", True, "batteria", 12, 30, 70.0),
    ("TEST_ iPhone 12", True, "connettore", 7.5, 30, 50.0),
    ("TEST_ iPhone 12", True, "vetro_camera", 3.5, 30, 30.0),
    ("TEST_ Xiaomi Redmi 12", True, "vetro_temperato", 3.1, 30, 10.0),
    ("TEST_ iPhone 12", False, "", 0, 30, 45.0),
]


@pytest.mark.parametrize("dispositivo,cr,tr,costo,minuti,expected", CASES)
def test_calcolo_prezzo(admin_headers, cliente_id, dispositivo, cr, tr, costo, minuti, expected):
    payload = {
        "tipo": "riparazione",
        "client_id": cliente_id,
        "dispositivo": dispositivo,
        "problema": "TEST_",
        "con_ricambio": cr,
        "tipo_ricambio": tr,
        "costo_componente": costo,
        "minuti_lavoro": minuti,
    }
    r = requests.post(f"{API}/servizi", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text[:400]
    s = r.json()
    sid = s["id"]
    try:
        pc = s.get("prezzo_consigliato")
        assert pc == expected, f"{dispositivo}/{tr} costo={costo} min={minuti}: expected {expected} got {pc}"
    finally:
        d = requests.delete(f"{API}/servizi/{sid}", headers=admin_headers, timeout=30)
        assert d.status_code in (200, 204)


# ---------- Parser Sifar dedicato su 49.pdf reale ----------
class TestParseSifar49:
    def test_parse_49_pdf(self, admin_headers):
        pdf_path = "/app/memory/fatture/49.pdf"
        assert os.path.exists(pdf_path)
        hdr = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        with open(pdf_path, "rb") as f:
            files = {"file": ("49.pdf", f, "application/pdf")}
            r = requests.post(f"{API}/listino/parse-fattura", headers=hdr, files=files, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("fornitore") == "Sifar", f"fornitore: {d.get('fornitore')}"
        assert d.get("data_fattura") == "21/05/2025", f"data: {d.get('data_fattura')}"
        righe = d.get("righe") or []
        assert len(righe) == 20, f"expected 20 righe got {len(righe)}"
        # tutte con codice
        no_code = [r for r in righe if not r.get("codice")]
        assert not no_code, f"righe senza codice: {no_code}"
        # riga DSPIH11THMCPY
        target = next((r for r in righe if r.get("codice") == "DSPIH11THMCPY"), None)
        assert target, f"DSPIH11THMCPY non trovata; codici: {[r.get('codice') for r in righe]}"
        assert target["prezzo_netto"] == 16.89, target
        assert target["tipologia"] == "display_compatibile", target
        assert target["marca"] == "apple", target
        assert "iphone 11" in (target.get("modello", "") or "").lower(), target
        assert target.get("qty_hint") == "4", target


# ---------- Ricerca listino ----------
class TestListinoSearch:
    def test_search_iphone_11(self, admin_headers):
        r = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "iphone 11", "limit": 50}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 3, f"iphone 11 count={len(data)}"

    def test_search_galaxy_s23(self, admin_headers):
        r = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "galaxy s23", "limit": 50}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1, f"galaxy s23 count={len(data)}"

    def test_search_zzz_empty(self, admin_headers):
        r = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "zzz"}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data == [], f"zzz should be empty, got {data}"
