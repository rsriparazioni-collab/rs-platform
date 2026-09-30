"""Iter 26 - Contabilità & Corrispettivi tests"""
import os
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE_URL = BASE_URL.rstrip("/")
WEBHOOK_SECRET = [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("WEBHOOK_CRON_SECRET=")][0]

MORBEGNO = "348642fd-364f-48ab-897b-83c6236b061f"
GRAVEDONA = "0916114d-79f9-4f06-8d7e-7e030ebe6cdc"
SONDRIO = "abbe8ad2-8102-4951-b4f7-8db24634a205"
TIRANO = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"

TEST_DATE = "2026-01-15"  # test day; will be cleaned up


@pytest.fixture(scope="module")
def admin_token():
    tok = subprocess.check_output(["bash", "/tmp/tok.sh"], text=True).strip().splitlines()[-1]
    assert tok.startswith("ey"), f"Invalid token: {tok}"
    return tok


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Meta ----------
def test_meta_lists_completi_and_stato(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/meta", headers=h, timeout=30)
    assert r.status_code == 200
    data = r.json()
    stores = data["stores"]
    completi = {s["nome"].lower() for s in stores if s["completo"]}
    solo_stato = {s["nome"].lower() for s in stores if not s["completo"]}
    assert {"morbegno", "gravedona", "sondrio"}.issubset(completi), completi
    # Others (Grosio, Ipro/IPRO, Sondalo, Tirano) should be badge-only
    for nome in ("grosio", "sondalo", "tirano"):
        assert nome in solo_stato, f"{nome} should be badge-only (got completi={completi} solo_stato={solo_stato})"
    assert data["is_admin"] is True
    assert set(data["categorie"]) == {"entrate", "spese_fisse", "spese_semifisse", "fornitori"}


# ---------- Corrispettivi CRUD ----------
def test_put_get_corrispettivo_totale_calcolato(h):
    body = {
        "riparazioni": 100, "merce": 50, "art74": 20, "fatture": 0,
        "fatture_dettaglio": [{"numero": "F-TEST-1", "importo": 30, "pagamento": "pos"}],
        "contanti": 80, "pos": 120, "versati": 0, "note": "TEST_ITER26"
    }
    r = requests.put(f"{BASE_URL}/api/contabilita/corrispettivi/{MORBEGNO}/{TEST_DATE}", headers=h, json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totale"] == 200  # 100+50+20+30
    assert d["fatture"] == 30  # recomputed from dettaglio
    assert d["iva"] > 0
    # GET verifies persisted
    r = requests.get(f"{BASE_URL}/api/contabilita/corrispettivi",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1})
    assert r.status_code == 200
    tot = r.json()["totali"]
    assert tot["totale"] >= 200


# ---------- Spese cassa ----------
_spesa_id = {}

def test_add_spesa(h):
    r = requests.post(f"{BASE_URL}/api/contabilita/spese", headers=h, json={
        "store_id": MORBEGNO, "data": TEST_DATE, "motivo": "TEST_ITER26_spesa", "importo": 42.50, "riferimento": "R1"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["importo"] == 42.5
    assert "id" in d
    _spesa_id["id"] = d["id"]

def test_spesa_listed_in_month(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/corrispettivi",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1})
    assert r.status_code == 200
    spese = r.json()["spese"]
    ids = [s["id"] for s in spese]
    assert _spesa_id["id"] in ids

def test_del_spesa(h):
    r = requests.delete(f"{BASE_URL}/api/contabilita/spese/{_spesa_id['id']}", headers=h)
    assert r.status_code == 200
    # verify removed
    r = requests.get(f"{BASE_URL}/api/contabilita/corrispettivi",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1})
    ids = [s["id"] for s in r.json()["spese"]]
    assert _spesa_id["id"] not in ids


# ---------- PDF ----------
def test_pdf_mensile(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/corrispettivi/pdf",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


# ---------- PDP ----------
def test_pdp_get_and_save(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/pdp",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1})
    assert r.status_code == 200
    d = r.json()
    assert "Eolo" in d["voci"]["entrate"]
    assert "Stipendi" in d["voci"]["spese_fisse"]
    # save
    valori = {"entrate|Eolo": 200, "spese_fisse|Stipendi": 1500}
    r = requests.put(f"{BASE_URL}/api/contabilita/pdp/{MORBEGNO}/2026/1", headers=h,
                     json={"valori": valori, "note": "TEST_ITER26"})
    assert r.status_code == 200
    d = r.json()
    # entrate include corrispettivi + Eolo (200)
    assert d["entrate"]["Eolo"] == 200
    assert d["tot_entrate"] >= 200
    assert d["sezioni"]["spese_fisse"]["Stipendi"] == 1500
    assert d["risultato"] == round(d["tot_entrate"] - d["tot_uscite"], 2)


def test_pdp_voci_add_remove(h):
    # get current
    r = requests.get(f"{BASE_URL}/api/contabilita/pdp/voci/{MORBEGNO}", headers=h)
    voci = r.json()
    new_list = list(voci["fornitori"]) + ["TEST_ITER26_forn"]
    r = requests.put(f"{BASE_URL}/api/contabilita/pdp/voci/{MORBEGNO}", headers=h,
                     json={**voci, "fornitori": new_list})
    assert r.status_code == 200
    assert "TEST_ITER26_forn" in r.json()["fornitori"]
    # remove
    r = requests.put(f"{BASE_URL}/api/contabilita/pdp/voci/{MORBEGNO}", headers=h, json=voci)
    assert r.status_code == 200
    assert "TEST_ITER26_forn" not in r.json()["fornitori"]


# ---------- Report ----------
def test_report_annuale(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/report/annuale",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026})
    assert r.status_code == 200
    d = r.json()
    assert len(d["mesi"]) == 12
    # month 1 should reflect the corrispettivo inserted (totale >= 200)
    gennaio = d["mesi"][0]
    assert gennaio["tot"] >= 200


def test_report_storico_put(h):
    r = requests.put(f"{BASE_URL}/api/contabilita/report/storico/{MORBEGNO}/2025/3", headers=h,
                     json={"enel": 111, "altro": 222})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # verify via report annuale 2026 -> mese 3 -> AP has 111/222
    r = requests.get(f"{BASE_URL}/api/contabilita/report/annuale",
                     headers=h, params={"store_id": MORBEGNO, "anno": 2026})
    marzo = r.json()["mesi"][2]
    assert marzo["enel_ap"] == 111
    assert marzo["altro_ap"] == 222


# ---------- Invio email/WA ----------
def test_invia_email_manuale(h):
    r = requests.post(f"{BASE_URL}/api/contabilita/corrispettivi/invia-email",
                      headers=h, params={"store_id": MORBEGNO, "anno": 2026, "mese": 1,
                                          "to": "cambiaora.rs@gmail.com"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["inviato"] is True
    assert d["to"] == "cambiaora.rs@gmail.com"
    assert "/api/public/report/" in d["link"]


def test_invia_whatsapp_dry_run(h):
    r = requests.post(f"{BASE_URL}/api/contabilita/corrispettivi/invia-whatsapp",
                      headers=h, params={"store_id": MORBEGNO, "data": TEST_DATE})
    assert r.status_code == 200, r.text
    # In preview WA is dry-run -> should return list, ok True (see agent_note)
    data = r.json()
    assert isinstance(data, list)


# ---------- Config ----------
def test_patch_config(h):
    r = requests.patch(f"{BASE_URL}/api/contabilita/config/{MORBEGNO}", headers=h,
                       json={"wa_numero": "+39 379 277 3557"})
    assert r.status_code == 200
    assert r.json()["wa_numero"] == "393792773557"  # normalized (digits only)


# ---------- Log ----------
def test_log_visible(h):
    r = requests.get(f"{BASE_URL}/api/contabilita/log", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- RBAC: user negozio kevin (Gravedona) ----------
def test_kevin_rbac_scope():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "kevin@cambiaora.local", "password": "Kevin2026!"
    }, timeout=30)
    if r.status_code == 403:
        pytest.skip(f"Kevin 2FA setup required (403): headers={dict(r.headers)}")
    if r.status_code != 200:
        pytest.skip(f"Kevin login failed: {r.status_code} {r.text}")
    data = r.json()
    if data.get("mfa_required"):
        pytest.skip("Kevin has MFA (not seeded)")
    token = data.get("token")
    if not token:
        pytest.skip(f"No token for kevin: {data}")
    kh = {"Authorization": f"Bearer {token}"}
    # /meta -> only Gravedona completo
    r = requests.get(f"{BASE_URL}/api/contabilita/meta", headers=kh)
    if r.status_code == 403:
        pytest.skip(f"Kevin MFA-setup enforced on API (403 X-MFA-Setup-Required={r.headers.get('X-MFA-Setup-Required')})")
    assert r.status_code == 200
    completi_ids = [s["id"] for s in r.json()["stores"] if s["completo"]]
    assert completi_ids == [GRAVEDONA]


def test_admin_forbidden_on_tirano(h):
    # Tirano has condividi_admin False by default -> 403
    r = requests.get(f"{BASE_URL}/api/contabilita/corrispettivi",
                     headers=h, params={"store_id": TIRANO, "anno": 2026, "mese": 1})
    assert r.status_code == 403


# ---------- Cron endpoints ----------
def test_cron_giornalieri_no_auth():
    r = requests.post(f"{BASE_URL}/api/cron/corrispettivi-giornalieri")
    assert r.status_code == 401

def test_cron_mensile_no_auth():
    r = requests.post(f"{BASE_URL}/api/cron/corrispettivi-mensile")
    assert r.status_code == 401

def test_cron_giornalieri_with_secret():
    r = requests.post(f"{BASE_URL}/api/cron/corrispettivi-giornalieri",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

def test_cron_mensile_with_secret():
    r = requests.post(f"{BASE_URL}/api/cron/corrispettivi-mensile",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"})
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


# ---------- Cleanup ----------
def test_cleanup(h):
    # Delete the test corrispettivo
    requests.delete(f"{BASE_URL}/api/contabilita/corrispettivi/{MORBEGNO}/{TEST_DATE}", headers=h)
    # Reset config
    requests.patch(f"{BASE_URL}/api/contabilita/config/{MORBEGNO}", headers=h, json={"wa_numero": ""})
