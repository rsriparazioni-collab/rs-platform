# Iter46: retest avvisi WhatsApp dry-run with a malformed data_contratto (non-string) client
import os
import uuid
from datetime import date, datetime, timezone

import pytest
import requests
from dateutil.relativedelta import relativedelta
from pymongo import MongoClient

from test_iter45_avvisi_dry_run import _admin_session, API

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    return _admin_session()


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    for cid in ids:
        db.clients.delete_one({"id": cid})
        db.wa_log.delete_many({"client_id": cid})


def _good_client(created, giorni, tel):
    scad = date.today() + relativedelta(days=giorni)
    dc = scad - relativedelta(months=12)
    cid = f"TEST_{uuid.uuid4()}"
    db.clients.insert_one({"id": cid, "nome": "TEST_Iter46", "cognome": "Good", "telefono": tel,
                           "data_contratto": dc.isoformat(), "created_at": datetime.now(timezone.utc).isoformat()})
    created.append(cid)
    return cid, (dc + relativedelta(months=12)).isoformat()


def _bad_client(created, value, tel):
    cid = f"TEST_{uuid.uuid4()}"
    db.clients.insert_one({"id": cid, "nome": "TEST_Iter46", "cognome": "Bad", "telefono": tel, "data_contratto": value})
    created.append(cid)
    return cid


# Malformed data_contratto (int, list, dict, garbage string) must not break rinnovo
@pytest.mark.parametrize("bad_value", [12345, ["2025-01-01"], {"d": 1}, "not-a-date"])
def test_rinnovo_malformed_does_not_break(admin, created, bad_value):
    bad = _bad_client(created, bad_value, "3331111999")
    good, scad = _good_client(created, 30, "3331111030")
    r = admin.post(f"{API}/energia/avvisi-rinnovo/invia-ora", timeout=120)
    assert r.status_code == 200, r.text[:300]
    rep = r.json()["report"]
    mine = [x for x in rep if x["client_id"] == good]
    assert mine and mine[0]["dry_run"] is True and mine[0]["inviato"] is False
    assert mine[0]["scadenza"] == scad
    assert not any(x["client_id"] == bad for x in rep)
    assert db.clients.find_one({"id": good}).get("rinnovo_msg_sent_for") is None
    assert db.wa_log.count_documents({"client_id": good, "tipo": "rinnovo_energia", "dry_run": True}) >= 1


def test_bollette_and_stato_with_malformed(admin, created):
    _bad_client(created, 12345, "3331111998")
    good, _ = _good_client(created, 71, "3331111071")
    r = admin.post(f"{API}/energia/avvisi-bollette/invia-ora", timeout=120)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d["inviati"] == 0
    for x in d["report"]:
        if "errore" not in x:
            assert x["dry_run"] is True and x["inviato"] is False
    mine = [x for x in d["report"] if x["client_id"] == good]
    assert mine
    doc = db.clients.find_one({"id": good})
    assert not doc.get("bollette_msg_sent_for") and doc.get("lavorazione") != "richieste_bollette"
    s = admin.get(f"{API}/avvisi/stato", timeout=60)
    assert s.status_code == 200 and s.json()["dry_run"] is True
    a = admin.get(f"{API}/energia/avvisi-bollette/anteprima", timeout=60)
    assert a.status_code == 200


def test_vincolo_dry_run(admin):
    r = admin.post(f"{API}/telefonia/avvisi-vincolo/invia-ora", timeout=120)
    assert r.status_code == 200
    for x in r.json()["report"]:
        if "errore" not in x:
            assert x["dry_run"] is True and x["inviato"] is False


def test_ripristina_and_stato(admin):
    r = admin.post(f"{API}/avvisi/ripristina-test", timeout=120)
    assert r.status_code == 200
    assert set(r.json()) == {"rinnovo_energia", "bollette", "vincolo"}
    s = admin.get(f"{API}/avvisi/stato", timeout=60).json()
    assert s["dry_run"] is True


def test_alerts_dashboard_with_malformed(admin, created):
    _bad_client(created, 12345, "3331111997")
    r = admin.get(f"{API}/alerts", timeout=60)
    assert r.status_code in (200, 404), r.text[:200]
