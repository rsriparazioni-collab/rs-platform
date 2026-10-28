# Iter39: Banche (estratti conto, riconciliazione POS), report commercialista, allegati fatture estere
import os
import pytest
import pyotp
import requests
from pymongo import MongoClient

BASE_URL = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE_URL}/api"
MG = "morbegno+gravedona"
SONDRIO = "store:abbe8ad2-8102-4951-b4f7-8db24634a205"
F_INTESA = "TEST_iter39_intesa.csv"
F_NEXI = "TEST_iter39_nexi.csv"
CSV_INTESA = "Data contabile;Descrizione;Uscite;Entrate\n01/09/2026;ACCREDITO POS NEXI;;138,50\n02/09/2026;PAGAMENTO MIWO;-236,32;\n03/09/2026;BONIFICO TEST;-10,00;\n".encode()
CSV_NEXI = 'Data transazione,Esercente,Importo\n01/09/2026,RS,"140,00"\n'.encode()
mdb = MongoClient("mongodb://localhost:27017")["test_database"]


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    r = sess.post(f"{API}/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": pyotp.TOTP("ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV").now()})
    assert r.status_code == 200, r.text
    sess.headers["Authorization"] = f"Bearer {r.json()['token']}"
    yield sess
    # cleanup
    mdb.movimenti_banca.delete_many({"file": {"$regex": "^TEST_iter39"}})
    mdb.estratti_caricati.delete_many({"file": {"$regex": "^TEST_iter39"}})
    mdb.contabilita_invii.delete_many({"to": "test@example.com"})
    mdb.fatture_estere.delete_many({"fornitore": "Test Estero"})


def up(s, conto, name, content):
    return s.post(f"{API}/banche/upload", data={"conto_id": conto}, files={"file": (name, content, "text/csv")})


# --- Banche ---
def test_conti(s):
    r = s.get(f"{API}/banche/conti")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == ["ditta-intesa-pos", "ditta-intesa-2", "ditta-mypos", "ditta-nexi", "srls-intesa", "srls-nexi"]


def test_upload_intesa_and_dedup(s):
    r = up(s, "ditta-intesa-pos", F_INTESA, CSV_INTESA)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["righe"] == 3 and d["nuovi"] == 3 and d["gia_presenti"] == 0
    assert d["dal"] == "2026-09-01" and d["al"] == "2026-09-03"
    r = up(s, "ditta-intesa-pos", F_INTESA, CSV_INTESA)
    assert r.status_code == 200
    assert r.json()["gia_presenti"] == 3 and r.json()["nuovi"] == 0


def test_upload_invalid(s):
    assert up(s, "nope", F_INTESA, CSV_INTESA).status_code == 400
    r = up(s, "ditta-intesa-pos", "TEST_iter39_bad.csv", b"foo;bar\n1;2\n")
    assert r.status_code == 400, r.text


def test_upload_nexi(s):
    r = up(s, "ditta-nexi", F_NEXI, CSV_NEXI)
    assert r.status_code == 200, r.text
    assert r.json()["nuovi"] == 1 and r.json()["righe"] == 1


def test_movimenti(s):
    r = s.get(f"{API}/banche/movimenti", params={"conto_id": "ditta-intesa-pos", "anno": 2026, "mese": 9})
    assert r.status_code == 200
    d = r.json()
    assert d["entrate"] == 138.5 and d["uscite"] == 246.32
    assert all("hash" not in i and "_id" not in i for i in d["items"])


def test_riconciliazione(s):
    r = s.get(f"{API}/banche/riconciliazione", params={"entita": "ditta", "anno": 2026, "mese": 9})
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("giorni", "totali", "fatture_pagate", "fatture_non_trovate_in_banca", "estratti_caricati"):
        assert k in d
    g = next(x for x in d["giorni"] if x["data"] == "2026-09-01")
    print("giorno 01:", g)
    assert g["pos_transazioni"] == 140.0
    assert g["accrediti_banca"] == 138.5
    assert g["pos_chiusure"] == 140.0 and g["ok"] is True
    files = {e["file"] for e in d["estratti_caricati"]}
    assert F_INTESA in files and F_NEXI in files


def test_riconciliazione_srls_and_invalid(s):
    assert s.get(f"{API}/banche/riconciliazione", params={"entita": "xx", "anno": 2026, "mese": 9}).status_code == 400
    r = s.get(f"{API}/banche/riconciliazione", params={"entita": "srls", "anno": 2026, "mese": 9})
    assert r.status_code == 200
    assert len(r.json()["conti"]) == 2


def test_delete_estratto(s):
    d = s.get(f"{API}/banche/riconciliazione", params={"entita": "ditta", "anno": 2026, "mese": 9}).json()
    e = next(x for x in d["estratti_caricati"] if x["file"] == F_NEXI)
    r = s.delete(f"{API}/banche/estratti/{e['id']}")
    assert r.status_code == 200 and r.json()["eliminati"] == 1
    assert s.delete(f"{API}/banche/estratti/{e['id']}").status_code == 404
    m = s.get(f"{API}/banche/movimenti", params={"conto_id": "ditta-nexi", "anno": 2026, "mese": 9}).json()
    assert not [i for i in m["items"] if i["file"] == F_NEXI]


def test_delete_duplicate_upload_record_keeps_movements(s):
    """BUG-candidate: deleting the 2nd (0 nuovi) upload record of the same file should NOT remove movements of the 1st."""
    d = s.get(f"{API}/banche/riconciliazione", params={"entita": "ditta", "anno": 2026, "mese": 9}).json()
    dup = [x for x in d["estratti_caricati"] if x["file"] == F_INTESA and x["nuovi"] == 0]
    assert dup
    r = s.delete(f"{API}/banche/estratti/{dup[0]['id']}")
    assert r.status_code == 200
    print("eliminati deleting dup record:", r.json())
    m = s.get(f"{API}/banche/movimenti", params={"conto_id": "ditta-intesa-pos", "anno": 2026, "mese": 9}).json()
    assert len([i for i in m["items"] if i["file"] == F_INTESA]) == 3, "deleting a duplicate upload removed the original movements"


def test_same_day_same_amount_transactions_not_collapsed(s):
    """BUG-candidate: two legit POS transactions same day/amount/merchant in one file are counted once."""
    content = 'Data transazione,Esercente,Importo\n05/09/2026,RS,"20,00"\n05/09/2026,RS,"20,00"\n'.encode()
    r = up(s, "ditta-nexi", "TEST_iter39_dupday.csv", content)
    assert r.status_code == 200
    print("dupday:", r.json())
    assert r.json()["nuovi"] == 2, "second identical transaction in same file discarded as duplicate"


# --- Report commercialista ---
def test_report_anteprima(s):
    r = s.get(f"{API}/report-commercialista", params={"centro_id": MG, "anno": 2026, "mese": 9})
    assert r.status_code == 200, r.text
    d = r.json()
    sez = {t: dict(rr) for t, rr in d["sezioni"]}
    assert sez["Entrate"]["TOTALE ENTRATE"] == "€ 26.737,52"
    assert sez["Risultato del mese"]["Entrate − uscite"] == "€ -557,02"
    assert "<h2>" in d["html"]
    assert s.get(f"{API}/report-commercialista", params={"centro_id": "zzz", "anno": 2026, "mese": 9}).status_code == 404


def test_report_config(s):
    r = s.get(f"{API}/report-commercialista/config")
    assert r.status_code == 200
    d = r.json()
    assert "destinatari" in d and "centri" in d and "invio_automatico" in d
    r = s.put(f"{API}/report-commercialista/config", json={"destinatari": {SONDRIO: "  "}, "invio_automatico": True})
    assert r.status_code == 200 and r.json()["destinatari"] == {}


def test_report_invia(s):
    r = s.post(f"{API}/report-commercialista/invia", json={"centro_id": MG, "anno": 2026, "mese": 9})
    assert r.status_code == 400 and "Email del commercialista non impostata" in r.json()["detail"]
    r = s.post(f"{API}/report-commercialista/invia", json={"centro_id": MG, "anno": 2026, "mese": 9, "to": "test@example.com"})
    print("invia:", r.status_code, r.text[:300])
    assert r.status_code == 200, r.text
    assert mdb.contabilita_invii.count_documents({"to": "test@example.com"}) >= 1


def test_report_non_admin_and_cron():
    r = requests.post(f"{API}/cron/report-commercialisti")
    assert r.status_code == 401
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"})
    if r.status_code != 200 or not r.json().get("token"):
        pytest.skip(f"non-admin login unavailable: {r.status_code}")
    sess.headers["Authorization"] = f"Bearer {r.json()['token']}"
    for path in ("/report-commercialista/config", "/banche/conti"):
        rr = sess.get(f"{API}{path}")
        assert rr.status_code == 403, (path, rr.status_code)


# --- Estere allegato ---
def test_estere_allegato(s):
    r = s.post(f"{API}/estere", json={"centro_id": SONDRIO, "data": "2026-10-05", "fornitore": "Test Estero", "tipo": "ue_rc", "imponibile": 50})
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    assert r.json()["iva_integrata"] == 11.0
    assert s.get(f"{API}/estere/fattura/{fid}/allegato").status_code == 404
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    r = s.post(f"{API}/estere/fattura/{fid}/allegato", files={"file": ("test.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    r = s.get(f"{API}/estere/fattura/{fid}/allegato")
    assert r.status_code == 200 and "pdf" in r.headers["content-type"] and r.content == pdf
    lst = s.get(f"{API}/estere", params={"anno": 2026, "mese": 10}).json()["items"]
    assert any(i["id"] == fid and i["allegato_nome"] == "test.pdf" for i in lst)
    r = s.post(f"{API}/estere/fattura/{fid}/allegato", files={"file": ("fattura è.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    r = s.get(f"{API}/estere/fattura/{fid}/allegato")
    print("non-ascii filename download:", r.status_code)
    nonascii_ok = r.status_code == 200
    assert s.delete(f"{API}/estere/fattura/{fid}").status_code == 200
    assert s.post(f"{API}/estere/fattura/{fid}/allegato", files={"file": ("x.pdf", pdf, "application/pdf")}).status_code == 404
    assert nonascii_ok, "download fails for non-ASCII filename (Content-Disposition latin-1)"
