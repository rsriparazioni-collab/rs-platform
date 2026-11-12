# Iter45: avvisi WhatsApp automatici in MODALITÀ TEST (dry-run), ripristina-test, stato, robustezza
import os
import uuid
from datetime import date, datetime, timezone

import pyotp
import pytest
import requests
from dateutil.relativedelta import relativedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"}, timeout=30)
    assert r.status_code == 200, r.text
    mfa = r.json()["mfa_token"]
    code = pyotp.TOTP(os.environ["TEST_ADMIN_TOTP_SECRET"]).now()
    r = s.post(f"{API}/auth/login/mfa", json={"mfa_token": mfa, "code": code}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _admin_session()


@pytest.fixture(scope="module")
def created():
    ids = {"clients": [], "servizi": [], "wa_client_ids": [], "wa_servizio_ids": []}
    yield ids
    for cid in ids["clients"]:
        db.clients.delete_one({"id": cid})
        db.wa_log.delete_many({"client_id": cid})
    for sid in ids["servizi"]:
        db.servizi.delete_one({"id": sid})
        db.wa_log.delete_many({"servizio_id": sid})


def _mk_client(created, giorni_scadenza, **extra):
    scad = date.today() + relativedelta(days=giorni_scadenza)
    dc = scad - relativedelta(months=12)
    cid = f"TEST_{uuid.uuid4()}"
    doc = {"id": cid, "nome": "TEST_Avvisi", "cognome": "Dryrun", "telefono": "3330000000", "data_contratto": dc.isoformat(),
           "created_at": datetime.now(timezone.utc).isoformat()}
    doc.update(extra)
    db.clients.insert_one(doc)
    created["clients"].append(cid)
    real_scad = (date.fromisoformat(dc.isoformat()) + relativedelta(months=12)).isoformat()
    return cid, real_scad


def test_dry_run_flag_on(admin):
    r = admin.get(f"{API}/avvisi/stato", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["dry_run"] is True, "Preview deve essere in MODALITÀ TEST"
    for k in ("giri", "invii", "in_attesa", "regole"):
        assert k in d
    assert isinstance(d["in_attesa"]["rinnovo_energia"], int)


def test_rinnovo_invia_ora_dry_run_not_marked(admin, created):
    cid, scad = _mk_client(created, 30)
    r = admin.post(f"{API}/energia/avvisi-rinnovo/invia-ora", timeout=120)
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    mine = [x for x in rep if x["client_id"] == cid]
    assert mine, "cliente di test non nel report"
    assert mine[0]["dry_run"] is True and mine[0]["inviato"] is False
    ok_items = [x for x in rep if "errore" not in x]
    assert all(x["dry_run"] is True and x["inviato"] is False for x in ok_items)
    doc = db.clients.find_one({"id": cid})
    assert doc.get("rinnovo_msg_sent_for") != scad
    # a sample of real clients in the report must not be marked either
    for x in ok_items[:10]:
        c = db.clients.find_one({"id": x["client_id"]}, {"rinnovo_msg_sent_for": 1})
        assert (c or {}).get("rinnovo_msg_sent_for") != x["scadenza"], f"cliente {x['client_id']} segnato in dry-run"


def test_bollette_invia_ora_dry_run_not_marked(admin, created):
    # giorni_al_rinnovo ~ 10 -> scadenza ~ 70 gg
    cid, _ = _mk_client(created, 71, telefono="3330000071", lavorazione="da_lavorare")
    r = admin.post(f"{API}/energia/avvisi-bollette/invia-ora", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    mine = [x for x in d["report"] if x["client_id"] == cid]
    assert mine, "cliente bollette di test non nel report"
    assert mine[0]["dry_run"] is True and mine[0]["inviato"] is False
    assert d["inviati"] == 0
    doc = db.clients.find_one({"id": cid})
    assert not doc.get("bollette_msg_sent_for")
    assert doc.get("lavorazione") == "da_lavorare"


def test_vincolo_invia_ora_dry_run(admin):
    r = admin.post(f"{API}/telefonia/avvisi-vincolo/invia-ora", timeout=120)
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    for x in rep:
        if "errore" not in x:
            assert x["dry_run"] is True and x["inviato"] is False
            s = db.servizi.find_one({"id": x["servizio"]}, {"vincolo_msg_sent_for": 1})
            assert (s or {}).get("vincolo_msg_sent_for") != x["scadenza"]


def test_ripristina_test_unmarks(admin, created):
    cid, scad = _mk_client(created, 40, telefono="3330000040")
    db.clients.update_one({"id": cid}, {"$set": {"rinnovo_msg_sent_for": scad, "rinnovo_msg_sent_at": datetime.now(timezone.utc).isoformat()}})
    db.wa_log.insert_one({"id": f"TEST_{uuid.uuid4()}", "tipo": "rinnovo_energia", "client_id": cid, "dry_run": True, "ok": True,
                          "at": datetime.now(timezone.utc).isoformat(), "phone": "3330000040", "message": "TEST"})
    before = admin.get(f"{API}/avvisi/stato", timeout=60).json()["in_attesa"]["rinnovo_energia"]
    r = admin.post(f"{API}/avvisi/ripristina-test", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d.keys()) == {"rinnovo_energia", "bollette", "vincolo"}
    assert d["rinnovo_energia"] >= 1
    doc = db.clients.find_one({"id": cid})
    assert "rinnovo_msg_sent_for" not in doc and "rinnovo_msg_sent_at" not in doc
    after = admin.get(f"{API}/avvisi/stato", timeout=60).json()["in_attesa"]["rinnovo_energia"]
    assert after >= before + 1


def test_ripristina_keeps_real_sends(admin, created):
    cid, scad = _mk_client(created, 41, telefono="3330000041")
    db.clients.update_one({"id": cid}, {"$set": {"rinnovo_msg_sent_for": scad}})
    db.wa_log.insert_one({"id": f"TEST_{uuid.uuid4()}", "tipo": "rinnovo_energia", "client_id": cid, "ok": True,
                          "at": datetime.now(timezone.utc).isoformat(), "phone": "3330000041", "message": "TEST"})
    r = admin.post(f"{API}/avvisi/ripristina-test", timeout=120)
    assert r.status_code == 200
    assert db.clients.find_one({"id": cid}).get("rinnovo_msg_sent_for") == scad


def test_invalid_phone_no_500(admin, created):
    cid, _ = _mk_client(created, 20, telefono="abc")
    r = admin.post(f"{API}/energia/avvisi-rinnovo/invia-ora", timeout=120)
    assert r.status_code == 200, r.text
    rep = r.json()["report"]
    assert any(x["client_id"] == cid for x in rep)
    assert len(rep) > 1


def test_malformed_data_contratto_does_not_break_loop(admin, created):
    """Robustezza: un cliente con data_contratto non-stringa non deve bloccare tutto il giro (500)."""
    cid, _ = _mk_client(created, 25, telefono="3330000025")
    bad = f"TEST_{uuid.uuid4()}"
    db.clients.insert_one({"id": bad, "nome": "TEST_bad", "telefono": "3330000099", "data_contratto": 20250101})
    created["clients"].append(bad)
    r = admin.post(f"{API}/energia/avvisi-rinnovo/invia-ora", timeout=120)
    assert r.status_code == 200, f"giro interrotto da un cliente malformato: {r.status_code} {r.text[:200]}"
    assert any(x["client_id"] == cid for x in r.json()["report"])


def test_non_admin_forbidden():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "deborah@cambiaora.local", "password": "Deborah2026!"}, timeout=30)
    if r.status_code != 200 or r.json().get("mfa_required"):
        pytest.skip("operatrice richiede 2FA: impossibile ottenere sessione non-admin")
    tok = r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    assert s.get(f"{API}/avvisi/stato", timeout=30).status_code == 403
    assert s.post(f"{API}/avvisi/ripristina-test", timeout=30).status_code == 403


def test_unauthenticated_401():
    assert requests.get(f"{API}/avvisi/stato", timeout=30).status_code == 401
    assert requests.post(f"{API}/avvisi/ripristina-test", timeout=30).status_code == 401
