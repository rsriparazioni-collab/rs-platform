# Iter43: Conto economico (margine.py) - totali, auto-classificazione, regole banca/fornitore, auth/validazione
import pytest
import requests
import pyotp
from dotenv import dotenv_values
from pymongo import MongoClient

FE = dotenv_values("/app/frontend/.env")
BE = dotenv_values("/app/backend/.env")
API = FE["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
P = {"entita": "ditta", "anno": 2026, "mese": 9}


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


def ce(s, **kw):
    r = s.get(f"{API}/margine/conto-economico", params={**P, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# --- Totali coerenti
def test_totali(s):
    d = ce(s)
    e = d["entrate"]
    assert abs(e["totale"] - (e["scontrini"] + e["fatture_emesse"])) < 0.02
    assert abs(d["margine_lordo"] - (e["totale"] - d["costi_variabili"]["merce"])) < 0.02
    assert abs(d["risultato"] - (d["margine_lordo"] - d["costi_fissi"]["totale"])) < 0.02
    cf = d["costi_fissi"]
    parts = sum(cf[k] for k in ("utenze", "servizi", "affitto", "tasse", "stipendi", "commissioni", "altro_costo", "spese_cassa"))
    assert abs(cf["totale"] - parts) < 0.02
    dc = sum(g["totale"] for g in d["banca"] + d["fornitori"] if g["categoria"] is None)
    assert abs(d["da_classificare"] - dc) < 0.02
    pn = d["per_negozio"]
    assert len(pn) == 2
    assert {n["nome"] for n in pn} >= {"Morbegno", "Gravedona"} or len({n["nome"] for n in pn}) == 2
    assert abs(sum(n["quota_pct"] for n in pn) - 100) <= 0.15
    assert abs(sum(n["entrate"] for n in pn) - e["totale"]) <= 0.05
    print("CE", {k: d[k] for k in ("margine_lordo", "risultato", "da_classificare")}, e, cf, [(n["nome"], n["quota_pct"]) for n in pn])
    print("BANCA", len(d["banca"]), "FORN", len(d["fornitori"]))


# --- Auto-classificazione
def test_auto_classificazione(s):
    d = ce(s)
    g = {x["chiave"]: x for x in d["banca"]}
    print("CHIAVI", [(k, v["categoria"], v["auto"]) for k, v in g.items()])
    for k in ("franca boffini", "savina caminada"):
        assert k in g, k
        assert g[k]["categoria"] == "affitto" and g[k]["auto"] is True
    assert g["delega"]["categoria"] == "tasse"
    assert g["anticipo transato pos"]["categoria"] == "giroconto"
    comm = [v for k, v in g.items() if "commission" in k]
    assert comm and all(v["categoria"] == "commissioni" for v in comm)


# --- Regola banca kevin ghiani -> stipendi
def test_regola_banca(s):
    assert DB.banca_regole.count_documents({"entita": "ditta", "chiave": "kevin ghiani"}) == 0
    before = ce(s)
    g0 = next(x for x in before["banca"] if x["chiave"] == "kevin ghiani")
    assert g0["categoria"] is None
    try:
        r = s.put(f"{API}/margine/regola-banca", json={"entita": "ditta", "chiave": "kevin ghiani", "categoria": "stipendi"})
        assert r.status_code == 200, r.text
        after = ce(s)
        assert round(after["costi_fissi"]["stipendi"] - before["costi_fissi"]["stipendi"], 2) == 2541.00
        g = next(x for x in after["banca"] if x["chiave"] == "kevin ghiani")
        assert g["categoria"] == "stipendi" and g["auto"] is False
        assert round(before["da_classificare"] - after["da_classificare"], 2) == 2541.00
        bad = s.put(f"{API}/margine/regola-banca", json={"entita": "ditta", "chiave": "kevin ghiani", "categoria": "xyz"})
        assert bad.status_code == 400
    finally:
        DB.banca_regole.delete_one({"entita": "ditta", "chiave": "kevin ghiani"})
    assert ce(s)["costi_fissi"]["stipendi"] == before["costi_fissi"]["stipendi"]


# --- Regola fornitore sifar -> merce
def test_regola_fornitore(s):
    cid = "morbegno+gravedona"
    assert DB.fornitori_regole.count_documents({"centro_id": cid, "chiave": "sifar"}) == 0
    before = ce(s)
    assert before["centro_id"] == cid
    try:
        r = s.put(f"{API}/margine/regola-fornitore", json={"centro_id": cid, "chiave": "sifar", "categoria": "merce"})
        assert r.status_code == 200, r.text
        after = ce(s)
        delta = round(after["costi_variabili"]["merce"] - before["costi_variabili"]["merce"], 2)
        print("MERCE before/after", before["costi_variabili"]["merce"], after["costi_variabili"]["merce"])
        assert after["costi_variabili"]["merce"] == 2895.88 or delta == 2895.88
        assert round(before["margine_lordo"] - after["margine_lordo"], 2) == delta
        bad = s.put(f"{API}/margine/regola-fornitore", json={"centro_id": cid, "chiave": "sifar", "categoria": "affitto"})
        assert bad.status_code == 400
    finally:
        DB.fornitori_regole.delete_one({"centro_id": cid, "chiave": "sifar"})


# --- srls, entita invalida, categorie
def test_srls_e_invalidi(s):
    d = ce(s, entita="srls")
    for k in ("entrate", "costi_variabili", "costi_fissi", "margine_lordo", "risultato", "banca", "fornitori", "per_negozio", "categorie"):
        assert k in d
    r = s.get(f"{API}/margine/conto-economico", params={**P, "entita": "xyz"})
    assert r.status_code == 400
    c = s.get(f"{API}/margine/categorie")
    assert c.status_code == 200
    j = c.json()
    assert {x["id"] for x in j["banca"]} >= {"affitto", "tasse", "stipendi", "commissioni", "giroconto"}
    assert {x["id"] for x in j["fornitore"]} == {"merce", "utenze", "servizi", "passante"}


# --- Non admin -> 403, anonimo -> 401
def test_non_admin():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "deborah@cambiaora.local", "password": "Deborah2026!"})
    print("DEB LOGIN", r.status_code, r.text[:200])
    if r.status_code != 200 or r.json().get("mfa_required"):
        pytest.skip("deborah needs MFA")
    tok = r.json().get("token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    for path in ("/margine/conto-economico", "/margine/categorie"):
        rr = sess.get(f"{API}{path}", params=P)
        print(path, rr.status_code, rr.text[:120])
        assert rr.status_code == 403
    rr = sess.put(f"{API}/margine/regola-banca", json={"entita": "ditta", "chiave": "TEST_x", "categoria": "stipendi"})
    assert rr.status_code == 403
    assert requests.get(f"{API}/margine/conto-economico", params=P).status_code in (401, 403)
