"""Iter 24 - Gara WindTre/Very regolamento tests."""
import os
import subprocess
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")

TIRANO_ID = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"
MESE = "2026-08"


@pytest.fixture(scope="module")
def token():
    out = subprocess.check_output(["bash", "/app/backend/tests/login_tok.sh"], text=True).strip()
    assert out and len(out) > 40, f"bad token: {out}"
    return out


@pytest.fixture(scope="module")
def api(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_id(api):
    r = api.get(f"{BASE}/api/auth/me")
    return r.json()["id"]


@pytest.fixture(scope="module")
def clean_prev(api):
    # Delete any leftover TEST_ITER24 clients/servizi
    r = api.get(f"{BASE}/api/clients", params={"q": "TEST_ITER24"})
    for c in r.json():
        for s in api.get(f"{BASE}/api/servizi", params={"client_id": c["id"]}).json():
            api.delete(f"{BASE}/api/servizi/{s['id']}")
        api.delete(f"{BASE}/api/clients/{c['id']}")
    yield
    # teardown same
    r = api.get(f"{BASE}/api/clients", params={"q": "TEST_ITER24"})
    for c in r.json():
        for s in api.get(f"{BASE}/api/servizi", params={"client_id": c["id"]}).json():
            api.delete(f"{BASE}/api/servizi/{s['id']}")
        api.delete(f"{BASE}/api/clients/{c['id']}")


# ---------- Tariffe defaults ----------
def test_get_tariffe_defaults(api):
    r = api.get(f"{BASE}/api/gara-windtre/tariffe")
    assert r.status_code == 200
    t = r.json()
    assert t["fisso_soglie"] == [1, 3, 8, 17]
    assert t["fisso_consumer"]["FTTH"] == [115, 126, 148, 170]
    assert t["convergente_extra"] == 30
    assert t["wt_soglie"] == [5, 18, 38]
    assert t["very_soglie"] == [5, 10, 15, 35]
    assert t["extra_mnp_soglia_rete"] == 15


def test_put_tariffe_upsert(api):
    r = api.put(f"{BASE}/api/gara-windtre/tariffe", json={"tariffe": {"convergente_extra": 30}})
    assert r.status_code == 200
    assert r.json()["convergente_extra"] == 30


# ---------- Scenario setup ----------
@pytest.fixture(scope="module")
def scenario(api, admin_id, clean_prev):
    """Create clients and servizi for the full scenario, return dict with ids."""
    # 2 clients: privato + societa
    r1 = api.post(f"{BASE}/api/clients", json={
        "nome": "TEST_ITER24", "cognome": "Priv", "tipo_cliente": "privato",
        "telefono": "3330000001", "venditore_id": TIRANO_ID, "origine": "telefonia"
    })
    assert r1.status_code in (200, 201), r1.text
    priv = r1.json()["id"]

    r2 = api.post(f"{BASE}/api/clients", json={
        "nome": "TEST_ITER24", "cognome": "Soc", "tipo_cliente": "societa",
        "p_iva": "12345678901", "codice_fiscale": "12345678901",
        "telefono": "3330000002", "venditore_id": TIRANO_ID, "origine": "telefonia"
    })
    assert r2.status_code in (200, 201), r2.text
    soc = r2.json()["id"]

    servizi_ids = {}

    def crea(chiave, payload):
        payload = {**payload, "venditore_id": TIRANO_ID, "operatore_id": admin_id}
        r = api.post(f"{BASE}/api/servizi", json=payload)
        assert r.status_code in (200, 201), f"{chiave}: {r.status_code} {r.text}"
        servizi_ids[chiave] = r.json()["id"]

    # (a) internet WINDTRE FTTH privato
    crea("a", {"client_id": priv, "tipo": "internet", "operatore_tel": "WINDTRE",
               "categoria_prodotto": "FTTH", "data_attivazione": "2026-08-01", "importo": 30})
    # (b) fisso WINDTRE FTTC privato convergente
    crea("b", {"client_id": priv, "tipo": "fisso", "operatore_tel": "WINDTRE",
               "categoria_prodotto": "FTTC", "convergente": True,
               "data_attivazione": "2026-08-02", "importo": 25})
    # (c) internet WINDTRE FTTH societa
    crea("c", {"client_id": soc, "tipo": "internet", "operatore_tel": "WINDTRE",
               "categoria_prodotto": "FTTH", "data_attivazione": "2026-08-03", "importo": 40})
    # (d) internet WINDTRE FTTH privato -> count 3
    crea("d", {"client_id": priv, "tipo": "internet", "operatore_tel": "WINDTRE",
               "categoria_prodotto": "FTTH", "data_attivazione": "2026-08-04", "importo": 30})
    # (e) sim WINDTRE nuovo -> NO MNP 0
    crea("e", {"client_id": priv, "tipo": "sim", "operatore_tel": "WINDTRE",
               "tipo_attivazione": "nuovo", "data_attivazione": "2026-08-05", "importo": 9.99})
    # (f) 5 sim WINDTRE mnp Iliad canone<=9.99
    for i in range(5):
        crea(f"f{i}", {"client_id": priv, "tipo": "sim", "operatore_tel": "WINDTRE",
                       "tipo_attivazione": "mnp", "provenienza_operatore": "Iliad",
                       "importo": 5, "data_attivazione": f"2026-08-{10+i:02d}"})
    # (g) 1 sim WINDTRE mnp tied societa canone 12.99
    crea("g", {"client_id": soc, "tipo": "sim", "operatore_tel": "WINDTRE",
               "tipo_attivazione": "mnp", "importo": 12.99, "tied": True,
               "data_attivazione": "2026-08-20"})
    # (h) 3 sim VERY mnp canone 7.99 -> soglia not reached
    for i in range(3):
        crea(f"h{i}", {"client_id": priv, "tipo": "sim", "operatore_tel": "VERY",
                       "tipo_attivazione": "mnp", "importo": 7.99,
                       "data_attivazione": f"2026-08-{22+i:02d}"})
    # (i) internet WINDTRE FTTH esito annullata -> excluded
    crea("i", {"client_id": priv, "tipo": "internet", "operatore_tel": "WINDTRE",
               "categoria_prodotto": "FTTH", "esito_attivazione": "annullata",
               "data_attivazione": "2026-08-27", "importo": 30})

    yield {"priv": priv, "soc": soc, "servizi": servizi_ids}


# ---------- Calcolo tests ----------
def test_calcolo_soglie_e_totale(api, scenario):
    r = api.get(f"{BASE}/api/gara-windtre/calcolo", params={"anno": 2026, "mese": 8})
    assert r.status_code == 200, r.text
    d = r.json()
    soglie = d["soglie"]
    assert soglie.get("FTTH", {}).get("conteggio") == 3, f"FTTH count: {soglie}"
    assert soglie.get("Mobile WindTre", {}).get("conteggio") == 6, f"WT count: {soglie}"
    assert soglie.get("Mobile Very", {}).get("conteggio") == 3, f"Very count: {soglie}"
    assert d["mnp_rete"] == 9
    assert d["extra_mnp_attivo"] is False

    # Map compensi by servizio id
    per_id = {a["id"]: a for a in d["attivazioni"]}
    s = scenario["servizi"]
    # FTTH count=3 -> soglia 'da 3' idx=1: consumer=126, piva=170
    assert per_id[s["a"]]["compenso_finale"] == 126.0, per_id[s["a"]]
    assert per_id[s["d"]]["compenso_finale"] == 126.0
    assert per_id[s["c"]]["compenso_finale"] == 170.0
    # FTTC categoria separata: count=1 -> idx=0 -> 115-22=93 + convergente 30 = 123
    assert per_id[s["b"]]["compenso_finale"] == 123.0, per_id[s["b"]]
    # NO MNP -> 0
    assert per_id[s["e"]]["compenso_finale"] == 0.0
    # WT 6 mnp -> idx 0 (>=5) canone<=9.99 -> 24
    for i in range(5):
        assert per_id[s[f"f{i}"]]["compenso_finale"] == 24.0
    # tied piva canone 12.99>9.99 -> 26 + tied 12 + piva 15 = 53
    assert per_id[s["g"]]["compenso_finale"] == 53.0
    # Very count 3 < 5 -> 0
    for i in range(3):
        assert per_id[s[f"h{i}"]]["compenso_finale"] == 0.0
    # esito annullata
    assert per_id[s["i"]]["compenso_finale"] == 0.0
    assert per_id[s["i"]]["riconosciuta"] is False

    # totale = 126+123+170+126 + 24*5 + 53 = 718
    atteso = 126 + 123 + 170 + 126 + 24*5 + 53
    assert d["totale_rete"] == float(atteso), f"totale_rete {d['totale_rete']} vs atteso {atteso}"


def test_ripartizione_premio(api, scenario):
    r = api.post(f"{BASE}/api/gara-windtre/premio", json={"mese": MESE, "premio_totale": 1000})
    assert r.status_code == 200
    r = api.get(f"{BASE}/api/gara-windtre/calcolo", params={"anno": 2026, "mese": 8})
    d = r.json()
    assert d["premio_totale"] == 1000
    rip = d["ripartizione"]
    assert len(rip) == 1, rip
    assert rip[0]["store_id"] == TIRANO_ID
    assert rip[0]["quota"] == 1000.0
    # inseritore admin ha 100% del generato del negozio
    ins = rip[0]["inseritori"]
    assert len(ins) == 1
    assert ins[0]["quota"] == 1000.0


def test_extra_mnp_attivo(api, scenario):
    # Lower threshold to 9
    r = api.put(f"{BASE}/api/gara-windtre/tariffe", json={"tariffe": {"extra_mnp_soglia_rete": 9}})
    assert r.status_code == 200
    try:
        r = api.get(f"{BASE}/api/gara-windtre/calcolo", params={"anno": 2026, "mese": 8})
        d = r.json()
        assert d["extra_mnp_attivo"] is True
        # 5 Iliad +35 each, g (provenienza vuota) +20
        # totale_rete = 729 + 175 + 20 = 924
        atteso = 126 + 123 + 170 + 126 + 24*5 + 53 + 5*35 + 20
        assert d["totale_rete"] == float(atteso), f"got {d['totale_rete']} vs {atteso}"
    finally:
        api.put(f"{BASE}/api/gara-windtre/tariffe", json={"tariffe": {"extra_mnp_soglia_rete": 15}})


def test_integrazione_compensi(api, scenario, admin_id):
    r = api.get(f"{BASE}/api/compensi/calcolo", params={"anno": 2026, "mese": 8})
    assert r.status_code == 200, r.text
    d = r.json()
    tirano = next((x for x in d["destinatari"] if x["id"] == TIRANO_ID), None)
    assert tirano, "Tirano destinatario missing"
    riga_gara = next((r for r in tirano["righe"] if r["regola_id"] == "gara_windtre"), None)
    assert riga_gara, f"riga gara_windtre missing: {[r['regola_id'] for r in tirano['righe']]}"
    atteso = 126 + 123 + 170 + 126 + 24*5 + 53
    assert riga_gara["totale"] == float(atteso), riga_gara
    # trattenuta 15% Tirano
    assert tirano["trattenuta_pct"] == 15

    # anche user admin (Enrico) ha la riga
    user_row = next((x for x in d["destinatari"] if x["tipo"] == "user" and x["id"] == admin_id), None)
    assert user_row, "admin user destinatario missing"
    riga_u = next((r for r in user_row["righe"] if r["regola_id"] == "gara_windtre"), None)
    assert riga_u and riga_u["totale"] == float(atteso), riga_u
