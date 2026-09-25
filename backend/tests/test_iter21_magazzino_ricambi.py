"""Iter 21 - Magazzino ricambi + flusso ordina/arrivo + cross-store."""
import os
import subprocess
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback dal file .env frontend
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

MORBEGNO_ID = "348642fd-364f-48ab-897b-83c6236b061f"


def _get_token():
    r = subprocess.run(["bash", "/app/backend/tests/login_tok.sh"], capture_output=True, text=True, timeout=30)
    tok = (r.stdout or "").strip().splitlines()[-1]
    assert tok.startswith("eyJ"), f"login failed: {r.stdout} {r.stderr}"
    return tok


@pytest.fixture(scope="module")
def token():
    return _get_token()


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# --- Cleanup helper --------------------------------------------------------
QA_ITEMS = []  # item ids to delete at end
QA_SERVICES_STATE = {}  # servizio_id -> {stato_iniziale, ricambi_iniziali_len}


@pytest.fixture(scope="module", autouse=True)
def cleanup(client):
    yield
    # Rimuovi ricambi aggiunti (dai servizi) e ripristina stato
    for sid, meta in QA_SERVICES_STATE.items():
        try:
            svc = client.get(f"{BASE_URL}/api/servizi/{sid}").json()
            usati = svc.get("ricambi_usati") or []
            for i in range(len(usati) - 1, meta["ricambi_iniziali_len"] - 1, -1):
                client.delete(f"{BASE_URL}/api/servizi/{sid}/ricambi/{i}")
            client.patch(f"{BASE_URL}/api/servizi/{sid}", json={"stato": meta["stato_iniziale"]})
        except Exception as e:
            print("cleanup svc err", e)
    for iid in QA_ITEMS:
        try:
            client.delete(f"{BASE_URL}/api/magazzino/{iid}")
        except Exception as e:
            print("cleanup item err", e)


# --- (1) Magazzino base ----------------------------------------------------
def test_tipologie(client):
    r = client.get(f"{BASE_URL}/api/magazzino/tipologie")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 11
    ids = {d["id"] for d in data}
    assert {"display", "batteria", "fotocamera", "connettore_ricarica", "vetro_posteriore",
            "altoparlante", "microfono", "tasti_flex", "scocca", "accessorio", "altro"} == ids


def test_create_magazzino_nome_auto(client):
    payload = {"marca": "Apple", "modello": "iPhone 12 QA", "tipologia": "display",
               "categoria": "display", "store_id": MORBEGNO_ID, "quantita": 2, "nome": ""}
    r = client.post(f"{BASE_URL}/api/magazzino", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nome"] == "Display Apple iPhone 12 QA"
    assert d["marca"] == "Apple"
    assert d["tipologia"] == "display"
    assert d["quantita"] == 2
    QA_ITEMS.append(d["id"])


def test_list_magazzino_search(client):
    r = client.get(f"{BASE_URL}/api/magazzino", params={"q": "iphone 12 qa"})
    assert r.status_code == 200
    items = r.json()
    assert any(i["nome"] == "Display Apple iPhone 12 QA" for i in items)


def test_list_magazzino_filter_tipologia_marca(client):
    r = client.get(f"{BASE_URL}/api/magazzino", params={"tipologia": "display", "marca": "apple"})
    assert r.status_code == 200
    items = r.json()
    assert any(i["nome"] == "Display Apple iPhone 12 QA" for i in items)


def test_disponibilita_group(client):
    r = client.get(f"{BASE_URL}/api/magazzino/disponibilita", params={"q": "iphone 12 qa"})
    assert r.status_code == 200
    groups = r.json()
    assert groups, "nessun gruppo trovato"
    g = next((x for x in groups if x["nome"] == "Display Apple iPhone 12 QA"), None)
    assert g is not None
    assert g["marca"] == "Apple"
    assert g["tipologia"] == "display"
    assert "stores" in g and len(g["stores"]) >= 1
    assert "in_ordine" in g["stores"][0]


# --- (2) Flusso ordina / arrivo su riparazione TEST_ -----------------------
@pytest.fixture(scope="module")
def test_servizio(client):
    r = client.get(f"{BASE_URL}/api/servizi", params={"tipo": "riparazione"})
    assert r.status_code == 200
    servizi = r.json()
    if isinstance(servizi, dict) and "servizi" in servizi:
        servizi = servizi["servizi"]
    cand = None
    for s in servizi:
        disp = (s.get("dispositivo") or "").upper()
        stato = s.get("stato")
        if disp.startswith("TEST_") and stato in ("ingresso", "preventivo", "in_lavorazione"):
            cand = s
            break
    if not cand:
        pytest.skip("Nessuna riparazione TEST_ disponibile in stato ingresso/preventivo/in_lavorazione")
    # Get full detail
    detail = client.get(f"{BASE_URL}/api/servizi/{cand['id']}").json()
    QA_SERVICES_STATE[detail["id"]] = {
        "stato_iniziale": detail.get("stato"),
        "ricambi_iniziali_len": len(detail.get("ricambi_usati") or []),
    }
    return detail


def test_ordina_ricambio(client, test_servizio):
    sid = test_servizio["id"]
    payload = {"marca": "Apple", "modello": "iPhone 12 QA-ORD", "tipologia": "batteria", "quantita": 1}
    r = client.post(f"{BASE_URL}/api/servizi/{sid}/ricambi/ordina", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["giacenza"] == -1
    assert d["in_ordine"] is True
    QA_ITEMS.append(d["item_id"])
    # verifica articolo
    it = client.get(f"{BASE_URL}/api/magazzino", params={"in_ordine": "true"}).json()
    matched = [i for i in it if i["id"] == d["item_id"]]
    assert matched, "articolo non presente con in_ordine=true"
    assert matched[0]["categoria"] == "ricambi"
    assert matched[0]["quantita"] == -1
    # verifica servizio stato + ricambi_usati
    svc = client.get(f"{BASE_URL}/api/servizi/{sid}").json()
    assert svc["stato"] == "attesa_ricambio_carico"
    assert svc["ricambi_usati"][-1]["in_ordine"] is True
    assert svc["ricambi_usati"][-1]["item_id"] == d["item_id"]
    # da-ordinare
    ord_list = client.get(f"{BASE_URL}/api/magazzino/da-ordinare").json()
    m = next((i for i in ord_list if i["id"] == d["item_id"]), None)
    assert m is not None
    assert m["da_ordinare"] == 1
    assert m["ordine_servizio_numero"] == svc.get("numero_riparazione")


def test_movimento_giacenza_zero_non_in_ordine(client):
    # crea articolo senza in_ordine con quantita 0
    payload = {"marca": "Apple", "modello": "iPhone 12 QA-MOV", "tipologia": "accessorio",
               "categoria": "accessori", "store_id": MORBEGNO_ID, "quantita": 0, "nome": ""}
    r = client.post(f"{BASE_URL}/api/magazzino", json=payload)
    assert r.status_code == 200
    iid = r.json()["id"]
    QA_ITEMS.append(iid)
    mv = client.post(f"{BASE_URL}/api/magazzino/{iid}/movimento", json={"delta": -1})
    assert mv.status_code == 400
    assert "insufficiente" in mv.text.lower() or "giacenza" in mv.text.lower()


def test_movimento_plus_su_in_ordine_equivalente_arrivo(client, test_servizio):
    sid = test_servizio["id"]
    # articolo in ordine è l'ultimo aggiunto tramite ordina - lo troviamo
    ord_list = client.get(f"{BASE_URL}/api/magazzino/da-ordinare").json()
    target = next((i for i in ord_list if i.get("ordine_servizio_id") == sid), None)
    if target is None:
        pytest.skip("Nessun articolo in ordine")
    iid = target["id"]
    r = client.post(f"{BASE_URL}/api/magazzino/{iid}/movimento", json={"delta": 1})
    assert r.status_code == 200, r.text
    d = r.json()
    # arrivo_ricambio ritorna {status, quantita, in_ordine, riparazioni_sbloccate}
    assert d.get("quantita") == 0
    assert d.get("in_ordine") is False
    assert sid or True
    # servizio → in_lavorazione, ricambio not in_ordine
    svc = client.get(f"{BASE_URL}/api/servizi/{sid}").json()
    assert svc["stato"] == "in_lavorazione"
    last = svc["ricambi_usati"][-1]
    assert last["in_ordine"] is False


def test_delete_ricambio_ripristina(client, test_servizio):
    sid = test_servizio["id"]
    svc = client.get(f"{BASE_URL}/api/servizi/{sid}").json()
    usati = svc.get("ricambi_usati") or []
    if not usati:
        pytest.skip("nessun ricambio da rimuovere")
    idx = len(usati) - 1
    item_id = usati[idx]["item_id"]
    before = client.get(f"{BASE_URL}/api/magazzino", params={"q": ""}).json()
    q_before = next((i["quantita"] for i in before if i["id"] == item_id), None)
    r = client.delete(f"{BASE_URL}/api/servizi/{sid}/ricambi/{idx}")
    assert r.status_code == 200
    after = client.get(f"{BASE_URL}/api/magazzino").json()
    q_after = next((i["quantita"] for i in after if i["id"] == item_id), None)
    assert q_after == (q_before or 0) + usati[idx]["quantita"]


# --- (3) Cross-store -------------------------------------------------------
def test_cross_store_ricambio(client, test_servizio):
    sid = test_servizio["id"]
    svc_store = test_servizio.get("venditore_id")
    # trova un negozio diverso
    stores = client.get(f"{BASE_URL}/api/stores").json()
    if isinstance(stores, dict) and "stores" in stores:
        stores = stores["stores"]
    other = next((s for s in stores if s.get("id") and s["id"] != svc_store), None)
    if not other:
        pytest.skip("nessun altro negozio disponibile")
    # crea articolo QA nell'altro negozio con quantita 1
    payload = {"marca": "Apple", "modello": "iPhone 12 QA-XSTORE", "tipologia": "batteria",
               "categoria": "ricambi", "store_id": other["id"], "quantita": 1, "nome": ""}
    r = client.post(f"{BASE_URL}/api/magazzino", json=payload)
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    QA_ITEMS.append(iid)

    # conta notifiche esistenti per lo store sorgente
    from pymongo import MongoClient
    env = {}
    with open("/app/backend/.env") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"').strip("'")
    mc = MongoClient(env["MONGO_URL"])
    dbn = mc[env["DB_NAME"]]
    before_notif = dbn.notifiche.count_documents({"store_id": other["id"]})

    r2 = client.post(f"{BASE_URL}/api/servizi/{sid}/ricambi", json={"magazzino_id": iid, "quantita": 1})
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d.get("altro_negozio") is True
    assert d.get("giacenza") == 0

    # verifica ricambi_usati
    svc = client.get(f"{BASE_URL}/api/servizi/{sid}").json()
    last = svc["ricambi_usati"][-1]
    assert last.get("da_store_id") == other["id"]

    # attende notifica async
    time.sleep(2)
    after_notif = dbn.notifiche.count_documents({"store_id": other["id"]})
    assert after_notif > before_notif, "nessuna notifica creata per store sorgente"

    # giacenza insufficiente → 400 con 'Metti in ordine'
    r3 = client.post(f"{BASE_URL}/api/servizi/{sid}/ricambi", json={"magazzino_id": iid, "quantita": 1})
    assert r3.status_code == 400
    assert "metti in ordine" in r3.text.lower()
