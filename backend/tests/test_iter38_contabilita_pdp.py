# Iter38: Contabilità PDP (read-only) - totali, spese cassa in fattura AdE, possibili doppi, trend, report annuale/confronto
import os
import pytest
import pyotp
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"
MG = "morbegno+gravedona"
SONDRIO = "store:abbe8ad2-8102-4951-b4f7-8db24634a205"
MORBEGNO = "348642fd-364f-48ab-897b-83c6236b061f"
GRAVEDONA = "0916114d-79f9-4f06-8d7e-7e030ebe6cdc"
SONDRIO_STORE = "abbe8ad2-8102-4951-b4f7-8db24634a205"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    mfa = r.json()["mfa_token"]
    r = sess.post(f"{API}/auth/login/mfa", json={"mfa_token": mfa, "code": pyotp.TOTP("ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV").now()})
    assert r.status_code == 200, r.text
    sess.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return sess


_cache = {}


def pdp(s, c, m):
    if (c, m) not in _cache:
        r = s.get(f"{API}/contabilita/pdp", params={"centro_id": c, "anno": 2026, "mese": m})
        assert r.status_code == 200, r.text
        _cache[(c, m)] = r.json()
    return _cache[(c, m)]


def test_pdp_requires_auth():
    r = requests.get(f"{API}/contabilita/pdp", params={"centro_id": MG, "anno": 2026, "mese": 8})
    assert r.status_code == 401


@pytest.mark.parametrize("c", [MG, SONDRIO])
@pytest.mark.parametrize("m", [8, 9, 10])
def test_pdp_coerenza_totali(s, c, m):
    d = pdp(s, c, m)
    assert abs(d["tot_entrate"] - sum(d["entrate"].values())) < 0.02
    assert abs(d["tot_uscite"] - sum(d["tot_spese"].values())) < 0.02
    assert abs(d["risultato"] - (d["tot_entrate"] - d["tot_uscite"])) < 0.02
    assert all(v >= 0 for v in d["sezioni"]["fornitori"].values()), d["sezioni"]["fornitori"]
    assert "spese_cassa_in_fattura" in d and "possibili_doppi" in d
    assert abs(d["tot_spese"]["fornitori"] - sum(d["sezioni"]["fornitori"].values())) < 0.02
    assert abs(d["tot_spese_cassa"] - sum(d["spese_cassa"].values())) < 0.02


def test_pdp_mg_agosto(s):
    d = pdp(s, MG, 8)
    assert d["entrate"]["Corrispettivi negozi (scontrini)"] == 13052.0
    assert d["entrate"]["Fatture emesse (AdE)"] == 21762.49
    assert d["tot_entrate"] == 34814.49
    assert d["tot_spese"]["spese_fisse"] == 14340.0
    doppi = d["possibili_doppi"]
    assert any(x["voce"] == "Phoneclik" and x["importo"] == 689.0 and "DISTRO" in x["controparte_ade"] for x in doppi)
    motivi = {x["motivo"].lower() for x in d["spese_cassa_in_fattura"]}
    assert "miwo" in motivi and "sifar" in motivi


def test_pdp_mg_settembre_escluse(s):
    d = pdp(s, MG, 9)
    ex = {(x["motivo"], x["importo"]) for x in d["spese_cassa_in_fattura"]}
    assert ("Radio station one", 634.4) in ex
    assert ("FRATE ELETT.", 7.5) in ex
    # escluse non devono essere sommate nelle spese cassa
    assert "Radio Station One" not in d["spese_cassa"]


def test_pdp_mg_ottobre_foglio(s):
    d = pdp(s, MG, 10)
    assert d["entrate"]["Corrispettivi negozi (scontrini)"] == 0.0
    assert d["foglio"] is not None and d["foglio"]["corrispettivi"] == 8904.9
    gd = d["foglio"].get("giorni_diff") or []
    assert any(g.get("foglio") and not g.get("scontrini") for g in gd), "nessun giorno rosso"


@pytest.mark.parametrize("c", [MG, SONDRIO])
def test_trend_coerente(s, c):
    r = s.get(f"{API}/contabilita/pdp/trend", params={"centro_id": c, "anno": 2026, "mese": 10, "mesi": 6})
    assert r.status_code == 200
    t = r.json()
    assert len(t) == 6 and [x["mese"] for x in t] == [5, 6, 7, 8, 9, 10]
    for x in t[3:]:
        d = pdp(s, c, x["mese"])
        assert x["fatturato"] == d["tot_entrate"] and x["uscite"] == d["tot_uscite"] and x["risultato"] == d["risultato"]


@pytest.mark.parametrize("sid", [MORBEGNO, GRAVEDONA, SONDRIO_STORE])
def test_report_annuale(s, sid):
    r = s.get(f"{API}/contabilita/report/annuale", params={"store_id": sid, "anno": 2026})
    assert r.status_code == 200
    d = r.json()
    assert len(d["mesi"]) == 12
    assert abs(d["totali"]["tot"] - sum(m["tot"] for m in d["mesi"])) < 0.05


def test_corrispettivi_morbegno_settembre_vs_pdp(s):
    r = s.get(f"{API}/contabilita/corrispettivi", params={"store_id": MORBEGNO, "anno": 2026, "mese": 9})
    assert r.status_code == 200
    t = r.json()["totali"]
    assert t["totale"] == 10471.0
    d = pdp(s, MG, 9)
    assert d["corrispettivi_per_negozio"][MORBEGNO] == 10471.0
    rg = s.get(f"{API}/contabilita/corrispettivi", params={"store_id": GRAVEDONA, "anno": 2026, "mese": 9}).json()["totali"]
    assert abs(t["scontrini"] + rg["scontrini"] - d["entrate"]["Corrispettivi negozi (scontrini)"]) < 0.02


def test_report_confronto_settembre(s):
    r = s.get(f"{API}/contabilita/report/confronto", params={"anno": 2026})
    assert r.status_code == 200
    d = r.json()
    mg = next(c for c in d["centri"] if c["id"] == MG)
    sett = mg["mesi"][8]
    p = pdp(s, MG, 9)
    assert sett["entrate"] == p["tot_entrate"] and sett["uscite"] == p["tot_uscite"] and sett["risultato"] == p["risultato"]
    morb = next(n for n in d["negozi"] if n["id"] == MORBEGNO)
    assert morb["mesi"][8]["tot"] == 10471.0


def test_report_sondrio_vs_corrispettivi_anomalia(s):
    """ANOMALIA: report fatturato Sondrio agosto deve essere ~ corrispettivi Sondrio (1.357,99), non 35.224,54 (entrate M+G foglio)."""
    rep = s.get(f"{API}/contabilita/report/annuale", params={"store_id": SONDRIO_STORE, "anno": 2026}).json()
    ago = rep["mesi"][7]["tot"]
    corr = pdp(s, SONDRIO, 8)["corrispettivi_per_negozio"][SONDRIO_STORE]
    assert ago < corr * 3, f"report Sondrio agosto {ago} vs corrispettivi {corr}"
