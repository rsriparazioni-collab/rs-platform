# Iter47: Incentivi - auto-add partecipanti base (Kevin/Deborah/Silvio/Bruno), rimozioni esplicite, classifica 40/30/20/10
import os
import copy
import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
BASE = ["Kevin", "Deborah", "Silvio", "Bruno"]


def _mongo():
    env = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip('"')
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


@pytest.fixture(scope="module")
def db():
    return _mongo()


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{BASE_URL}/api/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    d = r.json()
    if d.get("mfa_required"):
        r = ses.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": pyotp.TOTP(TOTP).now()})
        assert r.status_code == 200, r.text
        d = r.json()
    if d.get("token"):
        ses.headers["Authorization"] = f"Bearer {d['token']}"
    return ses


@pytest.fixture(scope="module", autouse=True)
def snapshot(db):
    orig = copy.deepcopy(db.incentivi_config.find_one({"id": "config"}, {"_id": 0}))
    silvio = db.users.find_one({"email": "silvio@cambiaora.local"}, {"_id": 0, "id": 1, "name": 1})
    yield
    db.users.update_one({"id": silvio["id"]}, {"$set": {"name": silvio["name"]}})
    db.incentivi_config.replace_one({"id": "config"}, orig)


@pytest.fixture(scope="module")
def ids(s):
    r = s.get(f"{BASE_URL}/api/incentivi/meta")
    assert r.status_code == 200
    m = {u["name"]: u["id"] for u in r.json()["users"]}
    for n in BASE:
        assert n in m, f"{n} non in meta"
    return m


class TestConfig:
    def test_config_contains_base(self, s, ids):
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        for n in BASE:
            assert ids[n] in c["partecipanti"], n
        assert c["premi_pct"] == [40, 30, 20, 10]

    def test_meta_includes_admin(self, s):
        roles = {u["role"] for u in s.get(f"{BASE_URL}/api/incentivi/meta").json()["users"]}
        assert "admin" in roles

    def test_silvio_missing_readded(self, s, db, ids):
        sid = ids["Silvio"]
        db.incentivi_config.update_one({"id": "config"}, {"$pull": {"partecipanti": sid}, "$unset": {"partecipanti_rimossi": ""}})
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid in c["partecipanti"]
        assert sid in db.incentivi_config.find_one({"id": "config"})["partecipanti"]

    def test_compound_name_readded(self, s, db, ids):
        sid = ids["Silvio"]
        db.users.update_one({"id": sid}, {"$set": {"name": "Silvio Tacconis"}})
        db.incentivi_config.update_one({"id": "config"}, {"$pull": {"partecipanti": sid}})
        try:
            c = s.get(f"{BASE_URL}/api/incentivi/config").json()
            assert sid in c["partecipanti"]
        finally:
            db.users.update_one({"id": sid}, {"$set": {"name": "Silvio"}})

    def test_explicit_removal_respected(self, s, db, ids):
        sid = ids["Silvio"]
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        parts = [p for p in c["partecipanti"] if p != sid]
        r = s.put(f"{BASE_URL}/api/incentivi/config", json={"partecipanti": parts})
        assert r.status_code == 200
        assert sid not in r.json()["partecipanti"]
        c2 = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid not in c2["partecipanti"]
        assert sid in (c2.get("partecipanti_rimossi") or [])

    def test_removal_survives_second_save(self, s, ids):
        # dopo la rimozione, un altro salvataggio (il frontend invia sempre partecipanti) non deve far rientrare Silvio
        sid = ids["Silvio"]
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid not in c["partecipanti"]
        r = s.put(f"{BASE_URL}/api/incentivi/config", json={"partecipanti": c["partecipanti"], "tetto_fondo": float(c.get("tetto_fondo", 0)) + 1})
        assert r.status_code == 200
        c2 = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid not in c2["partecipanti"], "Silvio rientrato dopo un secondo salvataggio: partecipanti_rimossi sovrascritto"

    def test_removal_survives_identical_and_other_field_save(self, s, ids):
        # iter48: PUT identico (nessun diff) e PUT senza partecipanti non devono far rientrare Silvio
        sid = ids["Silvio"]
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert s.put(f"{BASE_URL}/api/incentivi/config", json={"partecipanti": c["partecipanti"]}).status_code == 200
        assert s.put(f"{BASE_URL}/api/incentivi/config", json={"coef_eolo": float(c.get("coef_eolo", 100))}).status_code == 200
        c2 = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid not in c2["partecipanti"]
        assert sid in (c2.get("partecipanti_rimossi") or [])

    def test_readd_restore(self, s, ids):
        sid = ids["Silvio"]
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        parts = list(dict.fromkeys(c["partecipanti"] + [ids[n] for n in BASE]))
        r = s.put(f"{BASE_URL}/api/incentivi/config", json={"partecipanti": parts})
        assert r.status_code == 200
        c2 = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert sid in c2["partecipanti"]
        assert sid not in (c2.get("partecipanti_rimossi") or [])


class TestCalcolo:
    def test_classifica_ottobre(self, s):
        r = s.get(f"{BASE_URL}/api/incentivi/calcolo", params={"mese": "2026-10"})
        assert r.status_code == 200, r.text
        cl = r.json()["classifica"]
        names = sorted(x["nome"] for x in cl)
        assert names == sorted(BASE), names
        tot = sum(x["premio_pct"] for x in cl)
        assert abs(tot - 100) < 0.05, tot
        # ex aequo: same posizione -> same pct, quota = media delle posizioni occupate
        premi = [40, 30, 20, 10]
        for x in cl:
            same = [y for y in cl if y["posizione"] == x["posizione"]]
            p = x["posizione"] - 1
            exp = sum(premi[p:p + len(same)]) / len(same)
            assert abs(x["premio_pct"] - exp) < 0.05
        print([(x["nome"], x["posizione"], x["premio_pct"], x["valore"]) for x in cl])
