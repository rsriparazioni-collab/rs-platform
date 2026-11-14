# Iter49: Incentivi - modalita reale/provvisoria, split energia 50/50 acquisizione/lavorazione, fattore 1.0, foglio mese+1, riparazioni a Bruno, /mio
import os
import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
MESE = "2026-10"
CID1, CID2, RID = "TEST-iter49-cli-split", "TEST-iter49-cli-same", "TEST-iter49-rip"
LOGIDS = ["TEST-iter49-log1", "TEST-iter49-log2"]


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


@pytest.fixture(scope="module")
def ids(db):
    m = {u["name"]: u["id"] for u in db.users.find({"name": {"$in": ["Kevin", "Deborah", "Silvio", "Bruno"]}}, {"_id": 0, "id": 1, "name": 1})}
    st = {x["nome"]: x["id"] for x in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    m["Morbegno"] = st["Morbegno"]
    return m


def _cleanup(db):
    db.clients.delete_many({"id": {"$in": [CID1, CID2]}})
    db.lavorazioni_log.delete_many({"id": {"$in": LOGIDS}})
    db.servizi.delete_many({"id": RID})


@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    _cleanup(db)
    yield
    _cleanup(db)


def _calc(s, modalita):
    r = s.get(f"{BASE_URL}/api/incentivi/calcolo", params={"mese": MESE, "modalita": modalita})
    assert r.status_code == 200, r.text
    return r.json()


def _row(c, uid):
    return next(x for x in c["classifica"] if x["user_id"] == uid)


def _client(cid, op, store):
    return {"id": cid, "nome": "TEST", "cognome": "TEST_" + cid, "lavorazione": "cambio_effettuato", "operatore_id": op, "created_by": op,
            "data_contratto": f"{MESE}-15", "venditore_id": store, "tipo_bolletta": "luce", "gestione": "cambiaora", "pagato": False,
            "created_at": f"{MESE}-15T10:00:00+00:00", "updated_at": f"{MESE}-15T10:00:00+00:00"}


def _log(lid, cid, op):
    return {"id": lid, "client_id": cid, "client_name": "TEST", "operatore_id": op, "operatore_name": "x", "status": "cambio_effettuato", "note": "TEST", "created_at": "2099-01-01T00:00:00+00:00"}


class TestConfig:
    def test_config_values(self, s, ids):
        c = s.get(f"{BASE_URL}/api/incentivi/config").json()
        assert c["costo_datore_fattore"] == 1.0
        assert c["riparazioni_a"] == ids["Bruno"]
        assert c["gettone_energia_lordo"] == 10.0
        assert c["energia_importo"] == 25.0
        assert c["energia_fondo_pct"] == 50.0

    def test_foglio_mese_succ(self, db):
        rows = list(db.incentivi_provvigioni.find({"origine": "foglio"}, {"_id": 0, "mese": 1, "mese_fattura": 1}))
        assert rows
        for r in rows:
            assert r.get("mese_fattura"), r
            y, m = int(r["mese_fattura"][:4]), int(r["mese_fattura"][5:7]) + 1
            y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
            assert r["mese"] == f"{y:04d}-{m:02d}", r


class TestCalcoloModalita:
    @pytest.mark.parametrize("mod", ["reale", "provvisoria"])
    def test_structure(self, s, mod):
        c = _calc(s, mod)
        assert c["modalita"] == mod
        for k in ("classifica", "fondo", "costi"):
            assert k in c
        assert c["costi"]["fattore_costo_datore"] == 1.0
        assert abs(c["costi"]["costo_datore_totale"] - (c["costi"]["gettoni_lordi"] + c["costi"]["premi_lordi"] + c["costi"]["bonus_squadra_lordi"])) < 0.02

    def test_default_reale(self, s):
        r = s.get(f"{BASE_URL}/api/incentivi/calcolo", params={"mese": MESE})
        assert r.status_code == 200 and r.json()["modalita"] == "reale"

    def test_unauth(self):
        r = requests.get(f"{BASE_URL}/api/incentivi/calcolo", params={"mese": MESE, "modalita": "provvisoria"})
        assert r.status_code in (401, 403)


class TestSplitEnergia:
    def test_split_two_people(self, s, db, ids):
        base = _calc(s, "provvisoria")
        db.clients.insert_one(_client(CID1, ids["Kevin"], ids["Morbegno"]))
        db.lavorazioni_log.insert_one(_log(LOGIDS[0], CID1, ids["Deborah"]))
        try:
            c = _calc(s, "provvisoria")
            for n in ("Kevin", "Deborah"):
                b, a = _row(base, ids[n]), _row(c, ids[n])
                assert a["energia_n"] - b["energia_n"] == 1, n
                assert abs(a["energia_importo"] - b["energia_importo"] - 12.5) < 0.01, n
                assert abs(a["gettoni_lordo"] - b["gettoni_lordo"] - 5.0) < 0.01, n
            assert abs(c["fondo"]["fondo_da_energia"] - base["fondo"]["fondo_da_energia"] - 7.5) < 0.01
            assert abs(c["costi"]["costo_datore_totale"] - (c["costi"]["gettoni_lordi"] + c["costi"]["premi_lordi"] + c["costi"]["bonus_squadra_lordi"])) < 0.02
            # reale non cambia
            # previste
            p = s.get(f"{BASE_URL}/api/incentivi/previste", params={"mese": MESE}).json()
            mine = {r["ref_id"]: r for r in p["righe"] if r["ref_id"].startswith(f"client:{CID1}")}
            assert set(mine) == {f"client:{CID1}", f"client:{CID1}:lav"}
            assert mine[f"client:{CID1}"]["user_id"] == ids["Kevin"] and "acquisizione" in mine[f"client:{CID1}"]["descrizione"]
            assert mine[f"client:{CID1}:lav"]["user_id"] == ids["Deborah"] and "lavorazione" in mine[f"client:{CID1}:lav"]["descrizione"]
            assert mine[f"client:{CID1}"]["importo"] == 12.5 and mine[f"client:{CID1}:lav"]["importo"] == 12.5
        finally:
            _cleanup(db)

    def test_reale_unaffected(self, s, db, ids):
        base = _calc(s, "reale")
        db.clients.insert_one(_client(CID1, ids["Kevin"], ids["Morbegno"]))
        try:
            c = _calc(s, "reale")
            assert c["n_provvigioni"] == base["n_provvigioni"]
            assert _row(c, ids["Kevin"])["energia_n"] == _row(base, ids["Kevin"])["energia_n"]
        finally:
            _cleanup(db)

    def test_same_person(self, s, db, ids):
        base = _calc(s, "provvisoria")
        db.clients.insert_one(_client(CID2, ids["Kevin"], ids["Morbegno"]))
        db.lavorazioni_log.insert_one(_log(LOGIDS[1], CID2, ids["Kevin"]))
        try:
            c = _calc(s, "provvisoria")
            b, a = _row(base, ids["Kevin"]), _row(c, ids["Kevin"])
            assert a["energia_n"] - b["energia_n"] == 1
            assert abs(a["energia_importo"] - b["energia_importo"] - 25.0) < 0.01
            assert abs(a["gettoni_lordo"] - b["gettoni_lordo"] - 10.0) < 0.01
            assert abs(c["fondo"]["fondo_da_energia"] - base["fondo"]["fondo_da_energia"] - 7.5) < 0.01
            p = s.get(f"{BASE_URL}/api/incentivi/previste", params={"mese": MESE}).json()
            mine = [r for r in p["righe"] if r["ref_id"].startswith(f"client:{CID2}")]
            assert len(mine) == 1 and mine[0]["ref_id"] == f"client:{CID2}" and mine[0]["importo"] == 25.0
        finally:
            _cleanup(db)


class TestRiparazioni:
    def test_rip_to_bruno(self, s, db, ids):
        base = _calc(s, "provvisoria")
        db.servizi.insert_one({"id": RID, "tipo": "riparazione", "stato": "consegnato", "operatore_id": ids["Silvio"], "created_by": ids["Silvio"],
                               "lavorato_at": f"{MESE}-12T10:00:00+00:00", "created_at": f"{MESE}-10T10:00:00+00:00", "prezzo_finale": 80, "con_ricambio": False, "ricambi_usati": []})
        try:
            c = _calc(s, "provvisoria")
            assert _row(c, ids["Bruno"])["riparazioni_n"] - _row(base, ids["Bruno"])["riparazioni_n"] == 1
            assert abs(_row(c, ids["Bruno"])["riparazioni_margine"] - _row(base, ids["Bruno"])["riparazioni_margine"] - 80) < 0.01
            assert _row(c, ids["Silvio"])["riparazioni_n"] == _row(base, ids["Silvio"])["riparazioni_n"]
        finally:
            _cleanup(db)


class TestMio:
    def test_mio_admin_provvisoria(self, s, db):
        assert not db.incentivi_chiusure.find_one({"mese": MESE})
        r = s.get(f"{BASE_URL}/api/incentivi/mio", params={"mese": MESE})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["modalita"] == "provvisoria" and d["chiuso"] is False
        assert isinstance(d["classifica"], list)
