"""Iter 25 - Trasferimenti tra negozi: scarico automatico da cedente su riparazione/vendita/ordina."""
import os
import subprocess
import time
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
BASE_URL = BASE_URL.rstrip("/")

MORBEGNO = "348642fd-364f-48ab-897b-83c6236b061f"
SONDRIO = "abbe8ad2-8102-4951-b4f7-8db24634a205"

MESE = datetime.now(timezone.utc).strftime("%Y-%m")
ANNO = int(MESE.split("-")[0])
MESE_N = int(MESE.split("-")[1])


@pytest.fixture(scope="module")
def token():
    out = subprocess.check_output(["bash", "/app/backend/tests/login_tok.sh"], text=True).strip()
    assert out and "." in out
    return out


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def ctx(h):
    """Setup: articolo su Morbegno, cliente + riparazione su Sondrio."""
    # articolo magazzino Morbegno
    art = requests.post(f"{BASE_URL}/api/magazzino", headers=h, json={
        "nome": "TEST_ITER25 Display X", "categoria": "display", "tipologia": "display",
        "marca": "TestBrand", "modello": "TESTX", "quantita": 2,
        "prezzo_acquisto": 30, "prezzo_vendita": 60, "regime_iva": "iva22", "store_id": MORBEGNO,
    }).json()
    assert "id" in art, art
    # cliente
    cli = requests.post(f"{BASE_URL}/api/clients", headers=h, json={
        "nome": "TEST_ITER25", "cognome": "Cli", "telefono": "3999999925", "venditore_id": SONDRIO,
    }).json()
    assert "id" in cli, cli
    # servizio riparazione su Sondrio
    svc = requests.post(f"{BASE_URL}/api/servizi", headers=h, json={
        "client_id": cli["id"], "tipo": "riparazione", "venditore_id": SONDRIO,
        "dispositivo": "TEST iPhone", "problema": "display rotto",
    }).json()
    assert "id" in svc, svc
    data = {"art_id": art["id"], "cli_id": cli["id"], "svc_id": svc["id"]}
    yield data
    # cleanup
    requests.delete(f"{BASE_URL}/api/servizi/{svc['id']}", headers=h)
    requests.delete(f"{BASE_URL}/api/clients/{cli['id']}", headers=h)
    requests.delete(f"{BASE_URL}/api/magazzino/{art['id']}", headers=h)
    # extra cleanup vendite/trasferimenti leftover
    for v in requests.get(f"{BASE_URL}/api/vendite", headers=h).json():
        if v.get("articolo", "").startswith("TEST_ITER25") or v.get("cliente_nome", "").startswith("TEST_ITER25"):
            requests.delete(f"{BASE_URL}/api/vendite/{v['id']}", headers=h)


def _art(h, art_id):
    r = requests.get(f"{BASE_URL}/api/magazzino", headers=h, params={"q": "TEST_ITER25"})
    for it in r.json():
        if it["id"] == art_id:
            return it
    return None


def _trasf(h, **params):
    return requests.get(f"{BASE_URL}/api/magazzino/trasferimenti", headers=h, params=params).json()


# --- 1. RIPARAZIONE cross-store ---
def test_1_riparazione_cross_store(h, ctx):
    r = requests.post(f"{BASE_URL}/api/servizi/{ctx['svc_id']}/ricambi", headers=h,
                      json={"magazzino_id": ctx["art_id"], "quantita": 1})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["altro_negozio"] is True
    assert data["giacenza"] == 1
    # articolo Morbegno scaricato
    assert _art(h, ctx["art_id"])["quantita"] == 1
    # trasferimento
    lst = _trasf(h, anno=ANNO, mese=MESE_N)
    righe = [r for r in lst["righe"] if r["item_id"] == ctx["art_id"] and r["origine"] == "riparazione"]
    assert len(righe) == 1, righe
    t = righe[0]
    ctx["tid"] = t["id"]
    assert t["da_store_id"] == MORBEGNO
    assert t["a_store_id"] == SONDRIO
    assert t["quantita"] == 1
    assert t["prezzo_unitario"] == 30.0
    assert t["imponibile"] == 30.0
    assert t["iva"] == 6.6
    assert t["totale"] == 36.6
    assert t["fatturato"] is False
    assert t.get("in_ordine", False) is False


def test_2_annulla_ricambio(h, ctx):
    r = requests.delete(f"{BASE_URL}/api/servizi/{ctx['svc_id']}/ricambi/0", headers=h)
    assert r.status_code == 200, r.text
    assert _art(h, ctx["art_id"])["quantita"] == 2
    righe = [r for r in _trasf(h)["righe"] if r["item_id"] == ctx["art_id"]]
    assert len(righe) == 0


# --- 2. ORDINA DA CEDENTE ---
def test_3_ordina_da_cedente_e_arrivo(h, ctx):
    # porta a 0
    r = requests.post(f"{BASE_URL}/api/magazzino/{ctx['art_id']}/movimento", headers=h,
                      json={"delta": -2, "motivo": "test"})
    assert r.status_code == 200, r.text
    assert _art(h, ctx["art_id"])["quantita"] == 0

    # ordina dal cedente
    r = requests.post(f"{BASE_URL}/api/servizi/{ctx['svc_id']}/ricambi/ordina", headers=h,
                      json={"magazzino_id": ctx["art_id"], "da_store_id": MORBEGNO,
                            "quantita": 1, "tipologia": "display"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["giacenza"] == -1
    assert d["in_ordine"] is True
    # articolo Morbegno -1 e in_ordine
    a = _art(h, ctx["art_id"])
    assert a["quantita"] == -1
    assert a.get("in_ordine") is True
    # trasferimento in_ordine=True
    tr = [r for r in _trasf(h)["righe"] if r["item_id"] == ctx["art_id"] and r["origine"] == "riparazione"]
    assert len(tr) == 1
    assert tr[0]["in_ordine"] is True
    ctx["ord_tid"] = tr[0]["id"]
    # notifica admin
    nots = requests.get(f"{BASE_URL}/api/notifiche", headers=h).json()
    match = [n for n in nots["items"] if n.get("store_id") == MORBEGNO and "Ordine per altro negozio" in (n.get("titolo") or "")]
    assert match, [n.get("titolo") for n in nots["items"][:5]]

    # arrivo
    r = requests.post(f"{BASE_URL}/api/magazzino/{ctx['art_id']}/arrivo", headers=h, json={"quantita": 1})
    assert r.status_code == 200, r.text
    assert r.json()["quantita"] == 0
    tr = [r for r in _trasf(h)["righe"] if r["id"] == ctx["ord_tid"]]
    assert tr and tr[0]["in_ordine"] is False
    assert tr[0].get("arrivato_at")


# --- 3. FATTURA / PREZZO / EXPORT ---
def test_4_fatturato_e_prezzo(h, ctx):
    tid = ctx["ord_tid"]
    # patch prezzo su riga non fatturata OK
    r = requests.patch(f"{BASE_URL}/api/magazzino/trasferimenti/{tid}", headers=h,
                       json={"prezzo_unitario": 40})
    assert r.status_code == 200, r.text
    # segna fatturato
    r = requests.post(f"{BASE_URL}/api/magazzino/trasferimenti/{tid}/fatturato", headers=h,
                      json={"fatturato": True, "numero_fattura": "F-1"})
    assert r.status_code == 200, r.text
    # verifica
    tr = [x for x in _trasf(h)["righe"] if x["id"] == tid][0]
    assert tr["fatturato"] is True
    assert tr["numero_fattura"] == "F-1"
    assert tr["prezzo_unitario"] == 40.0
    assert tr["imponibile"] == 40.0
    # patch prezzo su fatturata -> 404
    r = requests.patch(f"{BASE_URL}/api/magazzino/trasferimenti/{tid}", headers=h,
                       json={"prezzo_unitario": 50})
    assert r.status_code == 404, r.text


def test_5_export_xlsx(h):
    r = requests.get(f"{BASE_URL}/api/magazzino/trasferimenti/export",
                     headers={k: v for k, v in h.items() if k != "Content-Type"},
                     params={"anno": ANNO, "mese": MESE_N})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers.get("content-type", "")
    assert len(r.content) > 200


# --- 4. VENDITA cross-store ---
def test_6_vendita_cross_store(h, ctx):
    # ricarica giacenza a 1 via arrivo (item in_ordine=false gia consegnato; usa movimento)
    a = _art(h, ctx["art_id"])
    if a["quantita"] < 1:
        r = requests.post(f"{BASE_URL}/api/magazzino/{ctx['art_id']}/movimento", headers=h,
                          json={"delta": 1 - a["quantita"]})
        assert r.status_code == 200, r.text
    # crea vendita su Sondrio di articolo Morbegno
    r = requests.post(f"{BASE_URL}/api/vendite", headers=h, json={
        "store_id": SONDRIO, "cliente_nome": "TEST_ITER25 Cli",
        "categoria": "accessori", "regime_iva": "iva22",
        "articolo": "TEST_ITER25 Display X", "magazzino_item_id": ctx["art_id"],
        "quantita": 1, "prezzo": 60,
    })
    assert r.status_code == 200, r.text
    v = r.json()
    ctx["vendita_id"] = v["id"]
    # trasferimento origine vendita
    tr = [x for x in _trasf(h)["righe"] if x.get("vendita_id") == v["id"]]
    assert len(tr) == 1
    assert tr[0]["origine"] == "vendita"
    assert tr[0]["da_store_id"] == MORBEGNO
    assert tr[0]["a_store_id"] == SONDRIO
    # delete vendita ripristina
    q_prima = _art(h, ctx["art_id"])["quantita"]
    r = requests.delete(f"{BASE_URL}/api/vendite/{v['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert _art(h, ctx["art_id"])["quantita"] == q_prima + 1
    tr = [x for x in _trasf(h)["righe"] if x.get("vendita_id") == v["id"]]
    assert len(tr) == 0


# --- 5. SCOPE utente negozio ---
def test_7_scope_negozio_tirano():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "michael@cambiaora.local", "password": "Michael2026!"})
    if r.status_code != 200:
        pytest.skip("login michael fallito")
    j = r.json()
    if j.get("mfa_required"):
        pytest.skip("2FA richiesta per michael - skip scope test")
    tok = j.get("token")
    if not tok:
        pytest.skip("no token")
    hh = {"Authorization": f"Bearer {tok}"}
    r = requests.get(f"{BASE_URL}/api/magazzino/trasferimenti", headers=hh)
    if r.status_code == 403:
        pytest.skip("MFA setup required")
    assert r.status_code == 200
    TIRANO = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"
    for x in r.json().get("righe", []):
        assert TIRANO in (x["da_store_id"], x["a_store_id"]), x
