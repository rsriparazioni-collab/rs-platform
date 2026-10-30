# Iter40 edge cases: estere PUT validation, ricorrenti PUT validation, auth playbook (bcrypt, httpOnly cookie, CORS)
import pytest
import requests
import pyotp
from dotenv import dotenv_values
from pymongo import MongoClient

FE = dotenv_values("/app/frontend/.env")
BE = dotenv_values("/app/backend/.env")
ROOT = FE["REACT_APP_BACKEND_URL"].rstrip("/")
API = ROOT + "/api"
STORE = "348642fd-364f-48ab-897b-83c6236b061f"


def db():
    return MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    r = sess.post(f"{API}/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": pyotp.TOTP("ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV").now()})
    assert r.status_code == 200
    sess.login_resp = r
    if r.json().get("token"):
        sess.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return sess


def test_cookie_httponly(s):
    sc = s.login_resp.headers.get("set-cookie", "")
    print("SET-COOKIE", sc[:200])
    assert "gu_token" in sc and "httponly" in sc.lower()


def test_bcrypt_hash():
    u = db().users.find_one({"email": "rsriparazioni@gmail.com"})
    h = u.get("password_hash") or u.get("password") or u.get("hashed_password")
    assert h.startswith("$2b$")


def test_cors_credentials():
    r = requests.options(f"{API}/auth/login", headers={"Origin": ROOT, "Access-Control-Request-Method": "POST"})
    print("CORS", r.status_code, r.headers.get("access-control-allow-origin"), r.headers.get("access-control-allow-credentials"))
    assert r.headers.get("access-control-allow-origin") == ROOT
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_estere_put_invalid(s):
    centri = s.get(f"{API}/contabilita/pdp/centri").json()
    r = s.post(f"{API}/estere", json={"centro_id": centri[0]["id"], "data": "2026-10-10", "fornitore": "TEST edge", "tipo": "ue_rc", "imponibile": 10})
    fid = r.json()["id"]
    try:
        bad_date = s.put(f"{API}/estere/fattura/{fid}", json={"centro_id": centri[0]["id"], "data": "xx", "fornitore": "TEST edge", "tipo": "ue_rc", "imponibile": 10})
        bad_imp = s.put(f"{API}/estere/fattura/{fid}", json={"centro_id": centri[0]["id"], "data": "2026-10-10", "fornitore": "TEST edge", "tipo": "ue_rc", "imponibile": -5})
        bad_tipo = s.put(f"{API}/estere/fattura/{fid}", json={"centro_id": centri[0]["id"], "data": "2026-10-10", "fornitore": "TEST edge", "tipo": "zzz", "imponibile": 10})
        print("ESTERE PUT invalid date", bad_date.status_code, "neg imponibile", bad_imp.status_code, "bad tipo", bad_tipo.status_code)
        assert bad_date.status_code == 400
        assert bad_imp.status_code == 400
        assert bad_tipo.status_code == 400
    finally:
        s.delete(f"{API}/estere/fattura/{fid}")


def test_ricorrenti_put_invalid(s):
    r = s.post(f"{API}/contabilita/spese-ricorrenti", json={"store_id": STORE, "motivo": "TEST edge ric", "importo": 1, "giorno": 1, "attiva": False})
    rid = r.json()["id"]
    try:
        bad = s.put(f"{API}/contabilita/spese-ricorrenti/{rid}", json={"store_id": STORE, "motivo": "TEST edge ric", "importo": -3, "giorno": 99, "attiva": False})
        print("RICORRENTI PUT invalid", bad.status_code)
        assert bad.status_code == 400
    finally:
        s.delete(f"{API}/contabilita/spese-ricorrenti/{rid}")
        db().spese_cassa.delete_many({"ricorrente_id": rid})
