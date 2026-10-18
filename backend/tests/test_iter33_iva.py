# Iter33: IVA module (iva.py), AdE fatture import anteprima/conferma/natura (fatture_ade.py), PDP riconciliazione, corrispettivi no IVA stima
import os
import io
import pytest
import pyotp
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CENTRO = "morbegno+gravedona"
Q = {"centro_id": CENTRO, "anno": 2026, "mese": 9}
MORB = "348642fd-364f-48ab-897b-83c6236b061f"
GRAV = "0916114d-79f9-4f06-8d7e-7e030ebe6cdc"
SECRET = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"

mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="session")
def s():
    ses = requests.Session()
    r = ses.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    d = r.json()
    if d.get("mfa_required"):
        r = ses.post(f"{API}/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": pyotp.TOTP(SECRET).now()})
        assert r.status_code == 200, r.text
        d = r.json()
    ses.headers["Authorization"] = f"Bearer {d['token']}"
    return ses


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    mdb.fatture_ade.delete_many({"numero": {"$regex": "^TEST-"}})


# ---- GET IVA
class TestIvaGet:
    def test_iva_main(self, s):
        r = s.get(f"{API}/contabilita/iva", params=Q)
        assert r.status_code == 200, r.text
        d = r.json()
        v = d["vendite"]
        c = v["corrispettivi"]
        assert c["non_determinabile_lordo"] > 0
        assert v["determinabile"] is False
        for n in c["negozi"]:
            assert n["certezza"] == "incompleto"
            assert n["giorni_rt"] < n["giorni_attesi"]
            assert len(n["giorni_mancanti_rt"]) > 0
            assert "giorni_discordanti" in n
        fe = v["fatture_emesse"]
        assert fe["n"] == 27 and fe["imposta"] == 2730.36 and fe["imponibile"] == 13019.16
        fr = d["acquisti"]["fatture_ricevute"]
        assert fr["n"] == 39 and fr["imposta"] == 1518.78
        assert d["acquisti"]["iva_detraibile"] == 1497.40
        assert sum(1 for a in d["anomalie"] if a["tipo"] == "detraibilita_limitata") == 3
        assert sum(1 for a in d["anomalie"] if a["tipo"] == "natura_da_verificare") == 7
        assert any(a["tipo"] == "aliquota_non_standard" for a in d["anomalie"])
        assert round(v["iva_debito"] - d["acquisti"]["iva_detraibile"] - d["credito_precedente"] + d["rettifiche"], 2) == d["saldo"]
        assert any("RT AdE presente" in m for m in d["mancanti"])
        assert any("2 fatture scritte nelle chiusure" in m and "senza documento AdE" in m for m in d["mancanti"])
        print("IVA", c["imponibile"], c["imposta"], c["non_determinabile_lordo"], d["saldo"], d["mancanti"])

    def test_corrispettivi_from_rt_only(self, s):
        d = s.get(f"{API}/contabilita/iva", params=Q).json()
        c = d["vendite"]["corrispettivi"]
        imp = iva = 0.0
        for x in mdb.corrispettivi_ade.find({"store_id": {"$in": [MORB, GRAV]}, "data": {"$regex": "^2026-09"}}):
            imp += float(x.get("imponibile") or 0); iva += float(x.get("imposta") or 0)
        assert round(iva, 2) == c["imposta"]
        assert round(imp, 2) == c["imponibile"]
        # no 22% estimate of manual scontrini
        lordo_man = sum(n["scontrini_manuali_lordi"] for n in c["negozi"])
        assert abs(c["imposta"] - round(lordo_man / 1.22 * 0.22, 2)) > 1

    def test_mese_invalido(self, s):
        r = s.get(f"{API}/contabilita/iva", params={**Q, "mese": 13})
        assert r.status_code == 400


# ---- PUT periodo
class TestIvaPeriodo:
    def test_put_credito(self, s):
        base = s.get(f"{API}/contabilita/iva", params=Q).json()
        r = s.put(f"{API}/contabilita/iva", params=Q, json={"credito_precedente": 300, "rettifiche": -50, "note": "t"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["credito_fonte"] == "manuale" and d["credito_precedente"] == 300 and d["rettifiche"] == -50
        assert d["saldo"] == round(base["vendite"]["iva_debito"] - base["acquisti"]["iva_detraibile"] - 300 - 50, 2)
        r = s.put(f"{API}/contabilita/iva", params=Q, json={"credito_precedente": None, "rettifiche": None, "note": ""})
        assert r.status_code == 200
        d2 = r.json()
        assert d2["rettifiche"] == 0 and d2["credito_fonte"] != "manuale"
        print("restored credito_fonte", d2["credito_fonte"], d2["saldo"], "base saldo", base["saldo"])


# ---- Config periodicita
class TestIvaConfig:
    def test_periodicita(self, s):
        r = s.put(f"{API}/contabilita/iva/config", params={"centro_id": CENTRO}, json={"periodicita": "trimestrale"})
        assert r.status_code == 200
        d = s.get(f"{API}/contabilita/iva", params=Q).json()
        assert d["scadenza"] == "2026-11-16" and "1%" in d["scadenza_nota"]
        assert d["interessi_trimestrale"] == (round(d["saldo"] * 0.01, 2) if d["saldo"] > 0 else 0)
        r = s.put(f"{API}/contabilita/iva/config", params={"centro_id": CENTRO}, json={"periodicita": "mensile"})
        assert r.status_code == 200
        d = s.get(f"{API}/contabilita/iva", params=Q).json()
        assert d["scadenza"] == "2026-10-16" and d["scadenza_nota"]
        r = s.put(f"{API}/contabilita/iva/config", params={"centro_id": CENTRO}, json={"periodicita": "annuale"})
        assert r.status_code == 400

    def test_anno(self, s):
        r = s.get(f"{API}/contabilita/iva/anno", params={"centro_id": CENTRO, "anno": 2026}, timeout=120)
        assert r.status_code == 200
        mesi = r.json()["mesi"]
        print("mesi", len(mesi), [(m["mese"], m["saldo"], m["certezza"]) for m in mesi])
        assert len(mesi) >= 9
        assert all("saldo" in m and "certezza" in m for m in mesi)


CSV = ("Tipo documento;Numero;Data emissione;Denominazione;Natura;Imponibile;Imposta;Totale\n"
       "Fattura;TEST-001;10/09/2026;TEST Fornitore A;;100,00;22,00;122,00\n"
       "Nota di credito TD04;TEST-002;11/09/2026;TEST Fornitore A;;50,00;11,00;61,00\n"
       "Fattura;TEST-003;12/09/2026;TEST Fornitore B;N4;200,00;0,00;200,00\n"
       "Fattura;TEST-004;13/09/2026;TEST Fornitore C;;80,00;0,00;80,00\n"
       "Fattura;36457;31/08/2026;ENEL Energia SpA;;;;5595,02\n")


# ---- Import AdE anteprima / conferma / natura
class TestAdeImport:
    def test_flow(self, s):
        p = {**Q, "direzione": "ricevute"}
        before = s.get(f"{API}/contabilita/pdp/fatture", params=Q).json()["totali"]
        r = s.post(f"{API}/contabilita/pdp/fatture/anteprima", params=p, files={"file": ("test.csv", CSV.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        a = r.json()
        print("anteprima", {k: a[k] for k in ("colonne", "n", "duplicati", "fuori_mese", "con_anomalie", "totali_nuove")})
        for rr in a["righe"]:
            print(" ", rr["numero"], rr["tipo"], rr["imponibile"], rr["imposta"], rr["totale"], rr["natura_iva"], rr["duplicato"], rr["note"])
        assert "natura" in a["colonne"]
        assert a["n"] == 5 and a["duplicati"] == 1 and a["fuori_mese"] == 1
        R = {x["numero"]: x for x in a["righe"]}
        assert R["TEST-002"]["totale"] == -61 and R["TEST-002"]["imposta"] == -11
        assert R["TEST-003"]["natura_iva"] == "esente"
        assert R["TEST-004"]["natura_iva"] == "da_verificare" and "senza IVA" in R["TEST-004"]["note"]
        assert R["36457"]["duplicato"] is True and any("fuori dal mese" in n for n in R["36457"]["note"])
        assert a["totali_nuove"]["totale"] == round(122 - 61 + 200 + 80, 2)
        # anteprima does not persist
        assert mdb.fatture_ade.count_documents({"numero": {"$regex": "^TEST-"}}) == 0
        nuove = [x for x in a["righe"] if not x["duplicato"]]
        r = s.post(f"{API}/contabilita/pdp/fatture/conferma", params=p, json={"righe": nuove})
        assert r.status_code == 200 and r.json()["importate"] == 4, r.text
        r = s.post(f"{API}/contabilita/pdp/fatture/conferma", params=p, json={"righe": nuove})
        assert r.json()["importate"] == 0 and r.json()["duplicate"] == 4
        t = s.get(f"{API}/contabilita/pdp/fatture", params=Q).json()["totali"]
        assert t["note_credito_ricevute"]["n"] == before["note_credito_ricevute"]["n"] + 1
        assert t["note_credito_ricevute"]["totale"] == round(before["note_credito_ricevute"]["totale"] - 61, 2)
        assert t["n_ricevute"] == before["n_ricevute"] + 4
        # natura patch
        f4 = mdb.fatture_ade.find_one({"numero": "TEST-004"})
        r = s.patch(f"{API}/contabilita/pdp/fatture/{f4['id']}/natura", json={"natura_iva": "forfettario"})
        assert r.status_code == 200
        d = s.get(f"{API}/contabilita/iva", params=Q).json()
        nz = d["acquisti"]["fatture_ricevute"]["nature_iva_zero"]
        assert "forfettario" in nz and "esente" in nz
        assert d["acquisti"]["fatture_ricevute"]["note_credito"]["n"] >= 1
        r = s.patch(f"{API}/contabilita/pdp/fatture/{f4['id']}/natura", json={"natura_iva": "boh"})
        assert r.status_code == 400
        r = s.patch(f"{API}/contabilita/pdp/fatture/nonexistent-id/natura", json={"natura_iva": "esente"})
        assert r.status_code == 404
        mdb.fatture_ade.delete_many({"numero": {"$regex": "^TEST-"}})
        after = s.get(f"{API}/contabilita/pdp/fatture", params=Q).json()["totali"]
        assert after["n_ricevute"] == before["n_ricevute"]


# ---- PDP riconciliazione
class TestPdp:
    def test_pdp(self, s):
        r = s.get(f"{API}/contabilita/pdp", params=Q)
        assert r.status_code == 200, r.text
        d = r.json()
        e = d["entrate"]
        print("entrate", e, "tot", d["tot_entrate"], "manuali", d["fatture_manuali"]["tot_non_riconciliate"], len(d["fatture_manuali"]["riconciliate"]))
        assert "Corrispettivi negozi (scontrini)" in e
        assert e["Fatture emesse (AdE)"] == 15749.52
        assert e["Fatture da chiusure senza documento AdE"] == 1977.0
        assert len(d["fatture_manuali"]["riconciliate"]) == 5
        assert d["fatture_manuali"]["tot_non_riconciliate"] == 1977
        iv = d["iva"]
        assert iv["determinabile"] is False and iv["ricavi_netti"] is None
        for k in ("iva_debito", "iva_detraibile", "saldo", "certezza"):
            assert k in iv
        assert d["ade_dettaglio"]["emesse_imposta"] == 2730.36
        assert round(e["Corrispettivi negozi (scontrini)"] + e["Fatture da chiusure senza documento AdE"] + e["Fatture emesse (AdE)"], 2) == d["tot_entrate"]
        # scontrini only (no fatture manuali)
        sc = 0.0
        for sid in (MORB, GRAV):
            sc += s.get(f"{API}/contabilita/corrispettivi", params={"store_id": sid, "anno": 2026, "mese": 9}).json()["totali"]["scontrini"]
        assert round(sc, 2) == e["Corrispettivi negozi (scontrini)"]


# ---- Corrispettivi: no IVA stima
class TestCorrispettivi:
    def test_no_iva(self, s):
        r = s.get(f"{API}/contabilita/corrispettivi", params={"store_id": MORB, "anno": 2026, "mese": 9})
        assert r.status_code == 200
        d = r.json()
        assert "scontrini" in d["totali"]
        assert d["totali"].get("iva") is None
        assert all(x.get("iva") is None for x in d["righe"])

    def test_pdf(self, s):
        r = s.get(f"{API}/contabilita/corrispettivi/pdf", params={"store_id": MORB, "anno": 2026, "mese": 9})
        assert r.status_code == 200 and r.content[:4] == b"%PDF"

    def test_report_annuale(self, s):
        r = s.get(f"{API}/contabilita/report/annuale", params={"anno": 2026})
        print("report annuale", r.status_code, r.text[:200])
        assert r.status_code in (200, 422)
