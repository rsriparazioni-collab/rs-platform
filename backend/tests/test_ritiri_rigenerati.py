"""Backend tests for Ritiro/Rigenerati flow: create ritiro from riparazione, upload docs,
merge PDF, vendi rigenerato, rigenerati venduti, dashboard margini-negozi (Rigenerati column)."""
import io
import os
import time

import pyotp
import pymupdf
import pytest
import requests
from dotenv import dotenv_values
from PIL import Image
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")

ADMIN_TOTP_SECRET = os.environ["TEST_ADMIN_TOTP_SECRET"]


def _admin_login():
    last_err = None
    for _ in range(3):
        r = requests.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "Devis2026!"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        if not data.get("mfa_required"):
            return data["token"]
        code = pyotp.TOTP(ADMIN_TOTP_SECRET).now()
        r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": data["mfa_token"], "code": code}, timeout=30)
        if r2.status_code == 200:
            return r2.json()["token"]
        last_err = r2.text
        time.sleep(32)
    raise AssertionError(f"admin MFA login failed: {last_err}")


@pytest.fixture(scope="module")
def admin_sess():
    tok = _admin_login()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def riparazione(admin_sess):
    r = admin_sess.get(f"{API}/servizi", params={"tipo": "riparazione"}, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    # pick one without ritiro
    for s in rows:
        if not s.get("ritiro_id") and s.get("venditore_id"):
            return s
    pytest.skip("No riparazione without ritiro available")


@pytest.fixture(scope="module")
def state(admin_sess, riparazione, mongo_db):
    """Track things to clean up + previous counter value."""
    store_id = riparazione["venditore_id"]
    ckey = f"ritiro:{store_id}"
    prev = mongo_db.counters.find_one({"_id": ckey})
    prev_seq = prev["seq"] if prev else None
    st = {"ritiro_id": None, "magazzino_id": None, "store_id": store_id,
          "ckey": ckey, "prev_seq": prev_seq, "vendita_ids": []}
    yield st
    # Cleanup
    if st["ritiro_id"]:
        admin_sess.delete(f"{API}/ritiri/{st['ritiro_id']}", timeout=30)
    if st["magazzino_id"]:
        admin_sess.delete(f"{API}/magazzino/{st['magazzino_id']}", timeout=30)
    mongo_db.vendite_rigenerati.delete_many({"nome": {"$regex": "^TEST_"}})
    if prev_seq is not None:
        mongo_db.counters.update_one({"_id": ckey}, {"$set": {"seq": prev_seq}})


# --- Ritiro creation ---
def test_create_ritiro_creates_rigenerato(admin_sess, riparazione, state):
    payload = {
        "store_id": riparazione["venditore_id"],
        "client_id": riparazione.get("cliente_id", ""),
        "servizio_id": riparazione["id"],
        "nome": riparazione.get("cliente_nome") or "TEST_Nome",
        "cognome": riparazione.get("cliente_cognome") or "TEST_Cognome",
        "articolo": "TEST_RIGEN Flip 6",
        "imei": "TEST123",
        "prezzo_ritiro": 0,
        "costo_ricambi": 120,
        "crea_rigenerato": True,
    }
    r = admin_sess.post(f"{API}/ritiri", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("numero")
    assert data.get("magazzino_id")
    state["ritiro_id"] = data["id"]
    state["magazzino_id"] = data["magazzino_id"]
    state["ritiro_numero"] = data["numero"]

    # GET magazzino
    mg = admin_sess.get(f"{API}/magazzino", timeout=30).json()
    item = next((m for m in mg if m["id"] == data["magazzino_id"]), None)
    assert item is not None
    assert item["categoria"] == "rigenerati"
    assert item["quantita"] == 1
    assert float(item["prezzo_acquisto"]) == 120.0
    assert item.get("ritiro_id") == data["id"]
    assert item.get("ritiro_numero") == data["numero"]

    # GET servizio
    sv = admin_sess.get(f"{API}/servizi/{riparazione['id']}", timeout=30).json()
    assert sv.get("ritiro_id") == data["id"]
    assert sv.get("ritiro_numero") == data["numero"]


def _make_png_bytes():
    img = Image.new("RGB", (100, 100), (200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes(pages=2):
    doc = pymupdf.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 72), f"TEST doc page {i+1}")
    return doc.tobytes()


# --- upload documenti + merged pdf checks ---
def test_upload_documenti_and_pdf_merge(admin_sess, state):
    assert state.get("ritiro_id"), "prev test must have created ritiro"
    png = _make_png_bytes()
    pdf = _make_pdf_bytes(pages=2)

    files = [
        ("files", ("test.png", png, "image/png")),
        ("files", ("test.pdf", pdf, "application/pdf")),
    ]
    r = admin_sess.post(f"{API}/ritiri/{state['ritiro_id']}/documenti", files=files, timeout=60)
    assert r.status_code == 200, r.text

    # unsupported txt
    r_bad = admin_sess.post(f"{API}/ritiri/{state['ritiro_id']}/documenti",
                            files=[("files", ("bad.txt", b"hello", "text/plain"))], timeout=30)
    assert r_bad.status_code == 400

    # download and inspect PDF
    r_pdf = admin_sess.get(f"{API}/ritiri/{state['ritiro_id']}/pdf", timeout=30)
    assert r_pdf.status_code == 200
    assert r_pdf.headers.get("content-type", "").startswith("application/pdf")
    doc = pymupdf.open(stream=r_pdf.content, filetype="pdf")
    # bolla (1) + png (1) + pdf (2) = 4
    assert doc.page_count == 4, f"expected 4 pages, got {doc.page_count}"

    full_text = "\n".join(p.get_text() for p in doc).lower()
    assert "prezzo ritiro" in full_text
    assert "ricambi" not in full_text, "costo_ricambi should NOT appear in bolla"
    assert "120" not in full_text, "costo_ricambi value should NOT appear"


# --- vendi rigenerato ---
def test_vendi_rigenerato_and_double_vendi(admin_sess, state, mongo_db):
    r = admin_sess.post(f"{API}/magazzino/{state['magazzino_id']}/vendi", json={"prezzo_vendita": 305}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    expected = round(305 / 1.22 - 120, 2)
    assert data["margine"] == expected == 130.0
    state["vendita_ids"].append(data["id"])

    # second attempt
    r2 = admin_sess.post(f"{API}/magazzino/{state['magazzino_id']}/vendi", json={"prezzo_vendita": 305}, timeout=30)
    assert r2.status_code == 400

    # rigenerati venduti list
    vv = admin_sess.get(f"{API}/rigenerati/venduti", timeout=30).json()
    ids = [v["id"] for v in vv["vendite"]]
    assert data["id"] in ids
    assert vv["totale_margine"] >= 130.0


def test_dashboard_margini_negozi_rigenerati(admin_sess, state):
    r = admin_sess.get(f"{API}/dashboard/margini-negozi", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    row = next((n for n in d["negozi"] if n["store_id"] == state["store_id"]), None)
    assert row is not None, f"store {state['store_id']} not found in margini"
    assert row.get("rigenerati", 0) >= 1
    assert row.get("margine_rigenerati", 0) >= 130.0
    assert row.get("margine", 0) >= 130.0


def test_vendi_non_rigenerato_returns_400(admin_sess):
    # create a temporary magazzino item with different categoria
    stores = admin_sess.get(f"{API}/stores", timeout=30).json()
    store_id = stores[0]["id"]
    payload = {"nome": "TEST_NON_RIGEN", "categoria": "accessori", "store_id": store_id,
               "quantita": 1, "prezzo_acquisto": 10}
    r = admin_sess.post(f"{API}/magazzino", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    item_id = r.json()["id"]
    try:
        r2 = admin_sess.post(f"{API}/magazzino/{item_id}/vendi", json={"prezzo_vendita": 20}, timeout=30)
        assert r2.status_code == 400
    finally:
        admin_sess.delete(f"{API}/magazzino/{item_id}", timeout=30)
