# Riepilogo Lavorazioni (energia) - endpoints /api/lavorazioni/*
import os
from datetime import date, timedelta

import pyotp
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
DEBORAH_ID = "f32e7569-9bbd-43de-aa55-88d352ae0aa6"
STORE_TIRANO = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    mfa = r.json()["mfa_token"]
    r = s.post(f"{API}/auth/login/mfa", json={"mfa_token": mfa, "code": pyotp.TOTP(TOTP).now()})
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="session")
def test_client(admin):
    r = admin.post(f"{API}/clients", json={"nome": "Lav", "cognome": "TEST_Reins", "lavorazione": "annullato",
                                           "venditore_id": STORE_TIRANO, "gestione": "cambiaora", "pod": "IT001E0000TEST"})
    assert r.status_code == 200, r.text
    c = r.json()
    yield c
    admin.delete(f"{API}/clients/{c['id']}")


# --- accesso / addetti
def test_accesso_admin(admin):
    r = admin.get(f"{API}/lavorazioni/accesso")
    assert r.status_code == 200
    assert r.json() == {"abilitato": True, "admin": True}


def test_addetti_get_put(admin):
    r = admin.get(f"{API}/lavorazioni/addetti")
    assert r.status_code == 200
    d = r.json()
    assert DEBORAH_ID in d["addetti"]
    assert all(u.get("role") != "admin" for u in d["utenti"])
    orig = d["addetti"]
    r = admin.put(f"{API}/lavorazioni/addetti", json={"addetti": orig + ["non-esiste-id"]})
    assert r.status_code == 200
    assert "non-esiste-id" not in r.json()["addetti"]
    assert DEBORAH_ID in r.json()["addetti"]
    assert set(admin.get(f"{API}/lavorazioni/addetti").json()["addetti"]) == set(orig)


def test_addetti_non_admin_forbidden():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"})
    if r.status_code != 200 or r.json().get("mfa_required"):
        pytest.skip("non-admin login not usable")
    tok = r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    r1 = s.get(f"{API}/lavorazioni/addetti")
    r2 = s.put(f"{API}/lavorazioni/addetti", json={"addetti": []})
    assert r1.status_code == 403 and r2.status_code == 403
    print("non-admin 403 detail:", r1.text, r1.headers.get("X-MFA-Setup-Required"))


# --- riepilogo
def test_riepilogo_structure(admin):
    r = admin.get(f"{API}/lavorazioni/riepilogo")
    assert r.status_code == 200
    d = r.json()
    for k in ["negozi", "da_lavorare", "lavorate", "da_reinserire", "verifica_esito", "agenda_scadute", "totali", "oggi"]:
        assert k in d
    assert d["totali"]["da_lavorare"] == len(d["da_lavorare"])
    assert d["totali"]["lavorate"] == len(d["lavorate"])
    righe = d["da_lavorare"] + d["lavorate"] + d["da_reinserire"]
    assert righe
    for x in righe:
        assert x["semaforo"] in ("verde", "giallo", "rosso")
        assert 0 <= x["giorni_fermo"] <= 999
        g = x["giorni_fermo"]
        assert x["semaforo"] == ("rosso" if g > 7 else "giallo" if g > 3 else "verde")
        assert "GDPR-" not in x["client_name"]
    print("totali", d["totali"], "negozi", len(d["negozi"]))


def test_riepilogo_store_filter(admin):
    d = admin.get(f"{API}/lavorazioni/riepilogo", params={"store_id": STORE_TIRANO}).json()
    righe = d["da_lavorare"] + d["lavorate"] + d["da_reinserire"]
    assert all(x["store_id"] == STORE_TIRANO for x in righe)
    assert all(n["store_id"] == STORE_TIRANO for n in d["negozi"])


# --- presa in carico
def test_presa_in_carico(admin, test_client):
    cid = test_client["id"]
    r = admin.post(f"{API}/lavorazioni/{cid}/presa-in-carico", json={"attiva": True})
    assert r.status_code == 200
    d = admin.get(f"{API}/lavorazioni/riepilogo").json()
    row = next(x for x in d["da_reinserire"] if x["id"] == cid)
    assert row["presa_in_carico_nome"]
    hist = admin.get(f"{API}/clients/{cid}").json()["history"]
    assert any(h["note"] == "Presa in carico" for h in hist)
    r = admin.post(f"{API}/lavorazioni/{cid}/presa-in-carico", json={"attiva": False})
    assert r.status_code == 200
    d = admin.get(f"{API}/lavorazioni/riepilogo").json()
    row = next(x for x in d["da_reinserire"] if x["id"] == cid)
    assert row["presa_in_carico_nome"] == ""
    assert admin.post(f"{API}/lavorazioni/nonexist/presa-in-carico", json={"attiva": True}).status_code == 404


# --- reinserisci
def test_reinserisci(admin, test_client):
    cid = test_client["id"]
    r = admin.post(f"{API}/lavorazioni/{cid}/reinserisci", json={"motivo": "TEST motivo"})
    assert r.status_code == 200, r.text
    c = admin.get(f"{API}/clients/{cid}").json()
    assert c["lavorazione"] == "da_quotare"
    assert c["reinserimenti"] == 1
    assert any("Pratica reinserita" in h["note"] for h in c["history"])
    d = admin.get(f"{API}/lavorazioni/riepilogo").json()
    row = next(x for x in d["da_lavorare"] if x["id"] == cid)
    assert row["reinserimenti"] == 1
    # non annullata -> 400
    r = admin.post(f"{API}/lavorazioni/{cid}/reinserisci", json={})
    assert r.status_code == 400


def test_patch_client_annullato_and_problema_tecnico(admin, test_client):
    cid = test_client["id"]
    r = admin.patch(f"{API}/clients/{cid}", json={"nome": "Lav", "cognome": "TEST_Reins", "lavorazione": "problema_tecnico"})
    assert r.status_code == 200 and r.json()["lavorazione"] == "problema_tecnico"
    r = admin.post(f"{API}/lavorazioni/{cid}/reinserisci", json={})
    assert r.status_code == 200
    r = admin.patch(f"{API}/clients/{cid}", json={"nome": "Lav", "cognome": "TEST_Reins", "lavorazione": "annullato"})
    assert r.status_code == 200 and r.json()["lavorazione"] == "annullato"
    assert admin.get(f"{API}/clients/{cid}").json()["reinserimenti"] == 2


def test_put_client_method(admin, test_client):
    r = admin.put(f"{API}/clients/{test_client['id']}", json={"nome": "Lav", "cognome": "TEST_Reins", "lavorazione": "annullato"})
    print("PUT /clients/{id} status:", r.status_code)


# --- agenda
def test_agenda_crud(admin):
    oggi = date.today().isoformat()
    domani = (date.today() + timedelta(days=1)).isoformat()
    assert admin.post(f"{API}/lavorazioni/agenda", json={"data": "2026-13-45", "nota": "x"}).status_code == 400
    assert admin.post(f"{API}/lavorazioni/agenda", json={"data": oggi, "nota": "   "}).status_code == 400
    r = admin.post(f"{API}/lavorazioni/agenda", json={"data": oggi, "nota": "TEST_agenda oggi"})
    assert r.status_code == 200
    a = r.json()
    assert a["fatto"] is False and a["nota"] == "TEST_agenda oggi" and "_id" not in a
    b = admin.post(f"{API}/lavorazioni/agenda", json={"data": domani, "nota": "TEST_agenda domani"}).json()
    lst = admin.get(f"{API}/lavorazioni/agenda").json()
    ids = [x["id"] for x in lst]
    assert a["id"] in ids and b["id"] in ids
    sc = [x["id"] for x in admin.get(f"{API}/lavorazioni/riepilogo").json()["agenda_scadute"]]
    assert a["id"] in sc and b["id"] not in sc
    assert admin.patch(f"{API}/lavorazioni/agenda/{a['id']}", json={"fatto": True}).status_code == 200
    sc = [x["id"] for x in admin.get(f"{API}/lavorazioni/riepilogo").json()["agenda_scadute"]]
    assert a["id"] not in sc
    assert admin.delete(f"{API}/lavorazioni/agenda/{a['id']}").status_code == 200
    assert admin.delete(f"{API}/lavorazioni/agenda/{b['id']}").status_code == 200
    assert admin.delete(f"{API}/lavorazioni/agenda/{a['id']}").status_code == 404
    assert admin.patch(f"{API}/lavorazioni/agenda/{a['id']}", json={"fatto": True}).status_code == 404


def test_unauth():
    assert requests.get(f"{API}/lavorazioni/riepilogo").status_code in (401, 403)
