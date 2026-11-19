# Iter50: PDP specchio (mirror Google sheet PDP per mese) - GET auth/RBAC/values, POST carica idempotent
import asyncio
import os
import pyotp
import pytest
import requests
from fastapi import HTTPException
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
URL = f"{BASE_URL}/api/contabilita/pdp-specchio"


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


def _neg(d, nome):
    return next(n for n in d["negozi"] if n["nome"].strip().lower() == nome)


class TestAuth:
    def test_unauth_get(self):
        r = requests.get(URL, params={"anno": 2026, "mese": 10})
        assert r.status_code == 401

    def test_unauth_post(self):
        r = requests.post(f"{URL}/carica")
        assert r.status_code == 401

    def test_non_admin_get(self):
        ses = requests.Session()
        r = ses.post(f"{BASE_URL}/api/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"})
        assert r.status_code == 200, r.text
        tok = r.json().get("token")
        h = {"Authorization": f"Bearer {tok}"} if tok else {}
        r = ses.get(URL, params={"anno": 2026, "mese": 10}, headers=h)
        assert r.status_code == 403
        r = ses.post(f"{URL}/carica", headers=h)
        assert r.status_code == 403

    def test_admin_guard_role_check_unit(self):
        # direct unit check of role guard (non-admin users with MFA cannot be used in preview)
        import sys
        sys.path.insert(0, "/app/backend")
        import pdp_specchio as m

        async def fake_user(_req):
            return {"role": "operatore", "name": "x"}
        old = m._d.get("user")
        m._d["user"] = fake_user
        try:
            with pytest.raises(HTTPException) as e:
                asyncio.run(m._admin(None))
            assert e.value.status_code == 403
        finally:
            if old:
                m._d["user"] = old


class TestGet:
    def test_values_2026_10(self, s):
        r = s.get(URL, params={"anno": 2026, "mese": 10})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["anno"] == 2026 and j["mese"] == 10
        assert "2026-10" in j["mesi_disponibili"]
        assert isinstance(j["gestionale_corrispettivi"], dict)
        d = j["dati"]
        assert "_id" not in d
        m = _neg(d, "morbegno")
        assert (m["tot_entrate"], m["tot_spese"], m["risultato"]) == (11318, 9965, 1353)
        g = _neg(d, "gravedona")
        assert (g["tot_entrate"], g["tot_spese"], g["risultato"]) == (7549, 4375, 3174)
        assert abs(d["ade"]["corrispettivi"] - 27549.65) < 0.01
        assert abs(d["ade"]["fatture_emesse"] - 11163.9) < 0.01
        assert abs(d["ade"]["fatture_ricevute"] - 16385.75) < 0.01
        assert abs(d["guadagno"] - 1580.37) < 0.01
        assert abs(d["iva"] - 3071.73) < 0.01
        assert len(d["corrispettivi"]) == 43
        assert len(d["emesse"]) == 24
        assert len(d["ricevute"]) == 48
        assert len(d["fornitori"]) > 0
        assert abs(d["tot_fornitori"] - sum(f["importo"] for f in d["fornitori"])) < 0.02
        for k in ("colonne", "totali", "tot_entrate", "tot_spese"):
            assert k in d

    def test_missing_month(self, s):
        r = s.get(URL, params={"anno": 2025, "mese": 1})
        assert r.status_code == 200
        assert r.json()["dati"] is None

    def test_invalid_params(self, s):
        r = s.get(URL, params={"anno": "x", "mese": 10})
        assert r.status_code == 422


class TestCarica:
    def test_carica_idempotent(self, s, db):
        before = db.pdp_specchio.count_documents({})
        ids_before = {(x["anno"], x["mese"]): x["id"] for x in db.pdp_specchio.find({}, {"_id": 0, "anno": 1, "mese": 1, "id": 1})}
        for _ in range(2):
            r = s.post(f"{URL}/carica", timeout=120)
            assert r.status_code == 200, r.text
            esito = r.json()["esito"]
            ok = [e for e in esito if not e.get("errore")]
            err = [e for e in esito if e.get("errore")]
            print("esito:", esito)
            assert len(ok) >= 10, err
            assert not err, err
        for a, m in ids_before:
            assert db.pdp_specchio.count_documents({"anno": a, "mese": m}) == 1
        assert db.pdp_specchio.count_documents({}) >= before
        ids_after = {(x["anno"], x["mese"]): x["id"] for x in db.pdp_specchio.find({}, {"_id": 0, "anno": 1, "mese": 1, "id": 1})}
        for k, v in ids_before.items():
            assert ids_after[k] == v
        # values unchanged after reload
        d = s.get(URL, params={"anno": 2026, "mese": 10}).json()["dati"]
        assert _neg(d, "morbegno")["risultato"] == 1353
