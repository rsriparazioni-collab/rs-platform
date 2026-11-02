# Iter41: riporto (contanti non versati) a catena mese -> mese successivo
import os
import pytest
import requests
import pyotp

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
GRAV = "0916114d-79f9-4f06-8d7e-7e030ebe6cdc"
MORB = "348642fd-364f-48ab-897b-83c6236b061f"
SOND = "abbe8ad2-8102-4951-b4f7-8db24634a205"
TIR = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{BASE_URL}/api/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    d = r.json()
    if d.get("mfa_required"):
        r = ses.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": pyotp.TOTP("ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV").now()})
        assert r.status_code == 200, r.text
        tok = r.json().get("token")
        if tok:
            ses.headers["Authorization"] = f"Bearer {tok}"
    return ses


def g(s, store, m):
    r = s.get(f"{BASE_URL}/api/contabilita/corrispettivi", params={"store_id": store, "anno": 2026, "mese": m})
    assert r.status_code == 200, r.text
    return r.json()


def test_gravedona_chain(s):
    d = {m: g(s, GRAV, m) for m in range(8, 13)}
    for m in range(8, 13):
        print(m, d[m]["riporto"], d[m]["riporto_auto"], d[m]["totali"]["da_versare"])
    for m in range(9, 13):
        assert d[m]["riporto"] == d[m - 1]["totali"]["da_versare"]
        assert d[m]["riporto_auto"] is True
    assert d[9]["riporto"] == 1278.84
    assert d[10]["riporto"] == 3323.84
    assert d[10]["totali"]["da_versare"] == 6368.84
    assert d[11]["riporto"] == 6368.84 and d[12]["riporto"] == 6368.84


def test_morbegno(s):
    d = {m: g(s, MORB, m) for m in (9, 10, 11)}
    for m in d:
        print(m, d[m]["riporto"], d[m]["riporto_auto"], d[m]["totali"]["da_versare"])
    assert d[9]["riporto"] == 833 and d[9]["riporto_auto"] is False
    assert d[10]["riporto"] == d[9]["totali"]["da_versare"] == 110.60
    assert d[11]["riporto"] == d[10]["totali"]["da_versare"]
    assert d[11]["riporto"] == 5970.50


def test_sondrio(s):
    d = {m: g(s, SOND, m) for m in (10, 11, 12)}
    for m in d:
        print(m, d[m]["riporto"], d[m]["totali"]["da_versare"])
    assert d[10]["riporto"] == 8.90 and d[11]["riporto"] == 8.90 and d[12]["riporto"] == 8.90


@pytest.fixture
def tirano_shared():
    # Tirano non ha config: abilita temporaneamente condivisione admin e rimuove il doc dopo
    import pymongo
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    db = pymongo.MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
    existed = db.contabilita_config.find_one({"store_id": TIR})
    if existed is None:
        db.contabilita_config.insert_one({"store_id": TIR, "condividi_admin": True, "TEST": True})
    yield
    if existed is None:
        db.contabilita_config.delete_one({"store_id": TIR, "TEST": True})
    db.corrispettivi_mese.delete_many({"store_id": TIR, "anno": 2026, "mese": {"$in": [11, 12]}, "riporto": {"$exists": False}, "versati_dopo": {"$in": [[], None]}})


def test_tirano_scenario(s, tirano_shared):
    base = f"{BASE_URL}/api/contabilita/corrispettivi/{TIR}"
    pre12 = g(s, TIR, 12)
    print("pre", pre12["riporto"], pre12["totali"]["da_versare"])
    vid = None
    try:
        r = s.put(f"{base}/2026-11-03", json={"riparazioni": 100, "merce": 0, "art74": 0, "contanti": 100, "pos": 0})
        assert r.status_code == 200, r.text
        assert g(s, TIR, 11)["totali"]["da_versare"] == 100
        d12 = g(s, TIR, 12)
        assert d12["riporto"] == 100 and d12["riporto_auto"] is True
        r = s.post(f"{base}/2026/11/versati-dopo", json={"data": "2026-12-02", "importo": 40, "note": "TEST"})
        assert r.status_code == 200, r.text
        vd = g(s, TIR, 11)["versati_dopo"]
        vid = next(v["id"] for v in vd if v.get("note") == "TEST")
        assert g(s, TIR, 12)["riporto"] == 60
        r = s.put(f"{base}/2026/12/riporto", json={"riporto": 55, "riporto_note": "TEST"})
        assert r.status_code == 200, r.text
        d12 = g(s, TIR, 12)
        assert d12["riporto"] == 55 and d12["riporto_auto"] is False
        r = s.delete(f"{base}/2026/12/riporto")
        assert r.status_code == 200, r.text
        d12 = g(s, TIR, 12)
        assert d12["riporto"] == 60 and d12["riporto_auto"] is True
    finally:
        if vid:
            print("del vd", s.delete(f"{base}/2026/11/versati-dopo/{vid}").status_code)
        s.delete(f"{base}/2026/12/riporto")
        print("del corr", s.delete(f"{base}/2026-11-03").status_code)
    post11 = g(s, TIR, 11)
    post12 = g(s, TIR, 12)
    assert post11["totali"]["giorni_inseriti"] == 0 and not post11["versati_dopo"]
    assert post12["riporto"] == pre12["riporto"]
