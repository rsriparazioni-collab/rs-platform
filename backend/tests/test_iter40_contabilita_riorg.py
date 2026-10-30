# Iter40: Contabilità riorganizzata - da-sistemare, edit spese/versati, estere PUT, spese ricorrenti, cron promemoria AdE, import AdE controllo
import os
import asyncio
import pytest
import requests
import pyotp
from dotenv import dotenv_values
from pymongo import MongoClient

FE = dotenv_values("/app/frontend/.env")
BE = dotenv_values("/app/backend/.env")
API = FE["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
STORE = "348642fd-364f-48ab-897b-83c6236b061f"
ANNO, MESE = 2026, 10  # mese corrente (data server 30/10/2026)


def _db():
    return MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]


def run(x):
    return x


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    r = sess.post(f"{API}/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": pyotp.TOTP("ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV").now()})
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    return sess


# --- Cose da sistemare
def test_da_sistemare_settembre(s):
    r = s.get(f"{API}/contabilita/da-sistemare", params={"store_id": STORE, "anno": 2026, "mese": 9})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totale"] == len(d["items"]) and d["totale"] > 0
    ordine = {"alto": 0, "medio": 1, "basso": 2}
    livs = [ordine[i["livello"]] for i in d["items"]]
    assert livs == sorted(livs)
    assert d["alto"] == sum(1 for i in d["items"] if i["livello"] == "alto")
    for i in d["items"]:
        assert i["testo"] and i["tab"] in ("cassa", "scadenze", "banche") and "tipo" in i
    print("ITEMS", [(i["livello"], i["tipo"], i["testo"][:90]) for i in d["items"][:6]])


def test_da_sistemare_negozio_inesistente(s):
    r = s.get(f"{API}/contabilita/da-sistemare", params={"store_id": "nope", "anno": 2026, "mese": 9})
    assert r.status_code in (403, 404)


# --- Spese cassa edit
def test_spesa_crud_edit(s):
    r = s.post(f"{API}/contabilita/spese", json={"store_id": STORE, "data": "2026-10-15", "motivo": "TEST spesa api", "importo": 5.5, "riferimento": ""})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    try:
        r = s.put(f"{API}/contabilita/spese/{sid}", json={"data": "2026-10-16", "motivo": "TEST spesa api mod", "importo": 7.25, "riferimento": "R1"})
        assert r.status_code == 200, r.text
        assert r.json()["updated_by"] == "Enrico"
        doc = run(_db().spese_cassa.find_one({"id": sid}, {"_id": 0}))
        assert doc["motivo"] == "TEST spesa api mod" and doc["importo"] == 7.25 and doc["data"] == "2026-10-16" and doc["riferimento"] == "R1"
        assert doc["storico"][0]["prima"]["motivo"] == "TEST spesa api" and doc["storico"][0]["da"] == "Enrico"
        assert s.put(f"{API}/contabilita/spese/{sid}", json={"data": "bad", "motivo": "x", "importo": 1}).status_code == 400
        assert s.put(f"{API}/contabilita/spese/{sid}", json={"data": "2026-10-16", "motivo": "  ", "importo": 1}).status_code == 400
        assert s.put(f"{API}/contabilita/spese/nonexist", json={"data": "2026-10-16", "motivo": "x", "importo": 1}).status_code == 404
    finally:
        assert s.delete(f"{API}/contabilita/spese/{sid}").status_code == 200
    assert run(_db().spese_cassa.find_one({"id": sid})) is None


# --- Versati dopo edit
def test_versato_dopo_edit(s):
    base = f"{API}/contabilita/corrispettivi/{STORE}/{ANNO}/{MESE}/versati-dopo"
    r = s.post(base, json={"data": "2026-10-20", "importo": 11, "note": "TEST versato"})
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    try:
        r = s.put(f"{base}/{vid}", json={"data": "2026-10-21", "importo": 12.5, "note": "TEST versato mod"})
        assert r.status_code == 200, r.text
        doc = run(_db().corrispettivi_mese.find_one({"store_id": STORE, "anno": ANNO, "mese": MESE}, {"_id": 0, "versati_dopo": 1}))
        v = next(x for x in doc["versati_dopo"] if x["id"] == vid)
        assert v["importo"] == 12.5 and v["data"] == "2026-10-21" and v["updated_by"] == "Enrico"
        assert s.put(f"{base}/nonexist", json={"data": "2026-10-21", "importo": 1, "note": ""}).status_code == 404
        assert s.put(f"{base}/{vid}", json={"data": "xx", "importo": 1, "note": ""}).status_code == 400
    finally:
        assert s.delete(f"{base}/{vid}").status_code == 200


# --- Fatture estere PUT
def test_estere_put(s):
    centri = s.get(f"{API}/contabilita/pdp/centri").json()
    assert centri
    r = s.post(f"{API}/estere", json={"centro_id": centri[0]["id"], "data": "2026-10-10", "fornitore": "TEST Fornitore", "paese": "DE", "tipo": "ue_rc", "numero": "T1", "imponibile": 100, "iva_pct": 22, "iva_dogana": 0, "note": ""})
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    try:
        r = s.put(f"{API}/estere/fattura/{fid}", json={"centro_id": centri[0]["id"], "data": "2026-10-11", "fornitore": "TEST Fornitore mod", "paese": "FR", "tipo": "ue_rc", "numero": "T2", "imponibile": 200, "iva_pct": 22, "iva_dogana": 0, "note": "n"})
        assert r.status_code == 200, r.text
        items = s.get(f"{API}/estere", params={"anno": 2026, "mese": 10}).json()["items"]
        f = next(x for x in items if x["id"] == fid)
        assert f["fornitore"] == "TEST Fornitore mod" and f["imponibile"] == 200 and abs(f["iva_integrata"] - 44) < 0.01
    finally:
        assert s.delete(f"{API}/estere/fattura/{fid}").status_code == 200


# --- Spese ricorrenti
def test_spese_ricorrenti_flow(s):
    r = s.post(f"{API}/contabilita/spese-ricorrenti", json={"store_id": STORE, "motivo": "TEST affitto api", "importo": 10, "giorno": 1})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    try:
        db = _db()
        gen = list(db.spese_cassa.find({"ricorrente_id": rid}, {"_id": 0}))
        assert len(gen) == 1 and gen[0]["data"] == "2026-10-01" and gen[0]["created_by"] == "automatico (spesa ricorrente)"
        r = s.post(f"{API}/contabilita/spese-ricorrenti/genera", params={"anno": 2026, "mese": 10})
        assert r.status_code == 200 and r.json()["create"] == 0, r.text
        assert _db().spese_cassa.count_documents({"ricorrente_id": rid}) == 1
        # validazione
        assert s.post(f"{API}/contabilita/spese-ricorrenti", json={"store_id": STORE, "motivo": "TEST", "importo": 10, "giorno": 31}).status_code == 400
        assert s.post(f"{API}/contabilita/spese-ricorrenti", json={"store_id": STORE, "motivo": "TEST", "importo": 0, "giorno": 1}).status_code == 400
        # sospendi
        r = s.put(f"{API}/contabilita/spese-ricorrenti/{rid}", json={"store_id": STORE, "motivo": "TEST affitto api2", "importo": 12, "giorno": 2, "attiva": False})
        assert r.status_code == 200 and r.json()["attiva"] is False
        lst = s.get(f"{API}/contabilita/spese-ricorrenti", params={"store_id": STORE}).json()
        assert any(x["id"] == rid and x["motivo"] == "TEST affitto api2" and x["importo"] == 12 for x in lst)
    finally:
        assert s.delete(f"{API}/contabilita/spese-ricorrenti/{rid}").status_code == 200
        run(_db().spese_cassa.delete_many({"ricorrente_id": rid}))
    assert s.delete(f"{API}/contabilita/spese-ricorrenti/{rid}").status_code == 404


# --- Cron promemoria AdE
def test_cron_promemoria_ade():
    assert requests.post(f"{API}/cron/promemoria-ade").status_code == 401
    assert requests.post(f"{API}/cron/promemoria-ade", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = requests.post(f"{API}/cron/promemoria-ade", headers={"Authorization": f"Bearer {BE['WEBHOOK_CRON_SECRET']}"})
    assert r.status_code in (200, 202) and r.json()["status"] == "accepted"
    st = run(_db().settings.find_one({"key": "wa_dry_run"}, {"_id": 0}))
    assert st and st["value"] is True
    import time; time.sleep(2)
    log = _db().scadenze_alert_log.find_one({"key": "promemoria-ade-2026-09"}, {"_id": 0})
    print("PROMEMORIA LOG", log)
    _db().scadenze_alert_log.delete_many({"key": "promemoria-ade-2026-09", "n": 0})  # cleanup test artefact


# --- Import AdE: re-import identico di 1 riga esistente (backup/restore)
def test_import_ade_controllo(s):
    db = _db()
    key = {"matricola": "1BENI060703", "data": "2026-09-01"}
    orig = run(db.corrispettivi_ade.find_one(key))
    assert orig
    csv = "Matricola;Data;Imponibile;Imposta;Totale\n1BENI060703;01/09/2026;263,44;31,56;295,00\n"
    try:
        r = s.post(f"{API}/contabilita/corrispettivi-ade/importa", params={"store_id": STORE}, files={"file": ("test.csv", csv.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        d = r.json()
        print("IMPORT", {k: v for k, v in d.items() if k != "controllo"}, "controllo keys", list(d["controllo"].keys()))
        assert d["importate"] == 0 and d["aggiornate"] == 1
        c = d["controllo"]
        assert "problemi" in c and "avvisi_whatsapp" in c and "dettaglio" in c
    finally:
        run(_db().corrispettivi_ade.replace_one({"_id": orig["_id"]}, orig))
