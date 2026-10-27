# Ricordi (post-it cliente) + Compleanni (auguri WhatsApp) - /api/clients/{id}/ricordi, /api/ricordi/*
import os
import sys
from datetime import date, datetime, timezone

import pyotp
import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from ricordi import nascita_da_cf  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
API = f"{BASE_URL.rstrip('/')}/api"
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
STORE_TIRANO = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"
mdb = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TODAY = date.today()


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    r = s.post(f"{API}/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": pyotp.TOTP(TOTP).now()})
    assert r.status_code == 200, r.text
    if r.json().get("token"):
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def tclient(admin):
    r = admin.post(f"{API}/clients", json={"nome": "Ric", "cognome": "TEST_Ricordi", "venditore_id": STORE_TIRANO,
                                           "codice_fiscale": "RSSMRA85M01H501Z", "telefono": "3999000001"})
    assert r.status_code == 200, r.text
    c = r.json()
    yield c
    mdb.client_ricordi.delete_many({"client_id": c["id"]})
    admin.delete(f"{API}/clients/{c['id']}")


# --- CF parsing
def test_nascita_da_cf():
    assert nascita_da_cf("RSSMRA85M01H501Z") == "1985-08-01"
    assert nascita_da_cf("RSSMRA85M41H501Z") == "1985-08-01"
    assert nascita_da_cf("rssmra85m01h501z") == "1985-08-01"
    assert nascita_da_cf("XXXX") is None
    assert nascita_da_cf("") is None
    assert nascita_da_cf("RSSMRA85Z01H501Z") is None  # mese non valido
    assert nascita_da_cf("RSSMRA85B31H501Z") is None  # 31 febbraio


# --- ricordi CRUD
def test_ricordi_crud(admin, tclient):
    cid = tclient["id"]
    r = admin.get(f"{API}/clients/{cid}/ricordi")
    assert r.status_code == 200
    d = r.json()
    assert d["ricordi"] == [] and d["data_nascita"] == "1985-08-01" and d["nascita_da_cf"] is True
    assert admin.post(f"{API}/clients/{cid}/ricordi", json={"testo": "   "}).status_code == 400
    r = admin.post(f"{API}/clients/{cid}/ricordi", json={"testo": "x" * 250})
    assert r.status_code == 200 and len(r.json()["testo"]) == 200
    long_id = r.json()["id"]
    r = admin.post(f"{API}/clients/{cid}/ricordi", json={"testo": "Ha un cane di nome Fido"})
    assert r.status_code == 200
    rid = r.json()["id"]
    assert r.json()["testo"] == "Ha un cane di nome Fido" and r.json()["da"]
    items = admin.get(f"{API}/clients/{cid}/ricordi").json()["ricordi"]
    assert [i["id"] for i in items][0] == rid and len(items) == 2
    p = admin.get(f"{API}/ricordi/preview", params={"ids": f"{cid},nonexistent"}).json()
    assert p[cid][0] == "Ha un cane di nome Fido" and "nonexistent" not in p
    assert admin.get(f"{API}/ricordi/preview").json() == {}
    assert admin.delete(f"{API}/clients/{cid}/ricordi/{rid}").status_code == 200
    assert admin.delete(f"{API}/clients/{cid}/ricordi/{rid}").status_code == 404
    admin.delete(f"{API}/clients/{cid}/ricordi/{long_id}")
    assert admin.get(f"{API}/clients/{cid}/ricordi").json()["ricordi"] == []
    assert admin.get(f"{API}/clients/nonexistent-xyz/ricordi").status_code == 404


def test_patch_data_nascita(admin, tclient):
    r = admin.patch(f"{API}/clients/{tclient['id']}", json={"nome": "Ric", "cognome": "TEST_Ricordi", "data_nascita": "1990-05-04"})
    assert r.status_code == 200, r.text
    assert admin.get(f"{API}/clients/{tclient['id']}").json()["data_nascita"] == "1990-05-04"
    d = admin.get(f"{API}/clients/{tclient['id']}/ricordi").json()
    assert d["data_nascita"] == "1990-05-04" and d["nascita_da_cf"] is False


# --- compleanni
def test_compleanni_stato(admin):
    r = admin.get(f"{API}/ricordi/compleanni/stato")
    assert r.status_code == 200
    d = r.json()
    for k in ("clienti", "con_data_nascita", "da_codice_fiscale", "senza"):
        assert isinstance(d[k], int)
    assert d["clienti"] == d["con_data_nascita"] + d["da_codice_fiscale"] + d["senza"]
    print("stato:", d)


def test_cron_unauth():
    assert requests.post(f"{API}/cron/auguri-compleanno").status_code == 401
    assert requests.post(f"{API}/cron/auguri-compleanno", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_invia_ora_non_admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"})
    if r.status_code != 200 or r.json().get("mfa_required"):
        pytest.skip("non-admin login not usable")
    if r.json().get("token"):
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    r = s.post(f"{API}/ricordi/compleanni/invia-ora")
    assert r.status_code == 403
    print("non-admin invia-ora:", r.text, r.headers.get("X-MFA-Setup-Required"))
    r = s.get(f"{API}/ricordi/compleanni/stato")
    print("non-admin stato:", r.status_code)


@pytest.fixture(scope="module")
def bday(admin):
    """Due utenze stessa persona (stesso CF/telefono) con compleanno oggi + store msg custom."""
    pre_auguri = {c["id"] for c in mdb.clients.find({"auguri_anno": TODAY.year}, {"id": 1})}
    start = datetime.now(timezone.utc).isoformat()
    orig = mdb.stores.find_one({"id": STORE_TIRANO}, {"_id": 0, "msg_compleanno": 1}) or {}
    r = admin.patch(f"{API}/stores/{STORE_TIRANO}", json={"msg_compleanno": "TEST_AUGURI {nome} {cognome} da {negozio}"})
    assert r.status_code == 200 and r.json()["msg_compleanno"].startswith("TEST_AUGURI")
    dn = TODAY.replace(year=1980).isoformat()
    ids = []
    for i in range(2):
        r = admin.post(f"{API}/clients", json={"nome": "Bday", "cognome": f"TEST_Compleanno{i}", "venditore_id": STORE_TIRANO,
                                               "telefono": "3999000077", "codice_fiscale": "TSTBDY80A01H501X", "data_nascita": dn})
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    yield ids
    for cid in ids:
        admin.delete(f"{API}/clients/{cid}")
    admin.patch(f"{API}/stores/{STORE_TIRANO}", json={"msg_compleanno": orig.get("msg_compleanno", "")})
    # ripristina eventuali clienti reali marcati dal test
    mdb.clients.update_many({"auguri_anno": TODAY.year, "id": {"$nin": list(pre_auguri)}}, {"$unset": {"auguri_anno": "", "auguri_sent_at": ""}})
    mdb.wa_log.delete_many({"tipo": "compleanno", "at": {"$gte": start}})


def test_compleanni_list(admin, bday):
    r = admin.get(f"{API}/ricordi/compleanni", params={"giorni": 7})
    assert r.status_code == 200
    lst = r.json()
    assert [x["data"] for x in lst] == sorted(x["data"] for x in lst)
    mine = [x for x in lst if x["id"] in bday]
    assert len(mine) == 1, f"duplicati per stessa persona: {mine}"
    m = mine[0]
    assert m["oggi"] is True and m["eta"] == TODAY.year - 1980 and m["auguri_inviati"] is False and m["negozio"] == "Tirano"
    for x in lst:
        assert set(["id", "client_name", "telefono", "negozio", "data", "oggi", "eta", "auguri_inviati"]) <= set(x)


def test_invia_ora_flow(admin, bday):
    r = admin.post(f"{API}/ricordi/compleanni/invia-ora")
    assert r.status_code == 200, r.text
    assert r.json()["inviati"] >= 1
    docs = list(mdb.clients.find({"id": {"$in": bday}}, {"_id": 0, "id": 1, "auguri_anno": 1}))
    marked = [d for d in docs if d.get("auguri_anno") == TODAY.year]
    assert len(marked) == 1
    logs = list(mdb.wa_log.find({"tipo": "compleanno", "client_id": {"$in": bday}}, {"_id": 0}))
    assert len(logs) == 1, logs
    assert logs[0]["message"] == "TEST_AUGURI Bday TEST_Compleanno{} da Tirano".format(bday.index(marked[0]["id"]))
    assert logs[0].get("dry_run") is True
    lst = admin.get(f"{API}/ricordi/compleanni").json()
    mine = [x for x in lst if x["id"] in bday]
    print("after send list entry:", mine)
    # seconda chiamata: nessun nuovo invio alla stessa persona (anche sull'altra utenza)
    r2 = admin.post(f"{API}/ricordi/compleanni/invia-ora")
    assert r2.status_code == 200
    logs = list(mdb.wa_log.find({"tipo": "compleanno", "client_id": {"$in": bday}}, {"_id": 0}))
    assert len(logs) == 1, f"reinvio alla stessa persona su seconda utenza: {[l['client_id'] for l in logs]}"
