"""Iter 23 - Test Compensi module (regole, calcolo, plafond, trattenute, per-ipro, backup alert, SIM fields)."""
import os
import subprocess
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

TIRANO = "f5f56f75-766c-4289-bfd0-a64ede3edbf8"
GROSIO = "d6f4d1f5-1294-4a5e-a8fd-8b7de5e61505"
SONDALO = "f136192b-0a09-4f70-b185-175362557ddf"
IPRO = "687bda8e-90fc-497d-a5a0-b2be79ed3c2d"

# State shared across tests
STATE = {
    "token": None,
    "regola_cambiaora_id": "f350149c-faac-409f-afc2-9d7925f354ce",
    "regola_extra_mnp_iliad_id": "244cdded-aecb-486c-8a5a-1599323c5574",
    "regola_eolo_gara_id": "aa1d7784-1483-44b2-8f47-a82d4630cec9",
    "client_id": None,
    "servizi_ids": [],
    "servizio_internet_id": None,
    "plafond_mov_id": None,
    "regole_created": [],
}


def _login():
    if STATE["token"]:
        return STATE["token"]
    out = subprocess.check_output(["bash", "/app/backend/tests/login_tok.sh"], text=True).strip()
    STATE["token"] = out
    return out


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login()}", "Content-Type": "application/json"})
    yield s


# -------------------- Meta --------------------
def test_meta(client):
    r = client.get(f"{BASE_URL}/api/compensi/meta")
    assert r.status_code == 200
    d = r.json()
    assert set(d["voci"].keys()) == {"fisso_mensile", "cambiaora", "sim", "internet", "fisso", "enel"}
    stores = {s["nome"]: s for s in d["stores"]}
    assert stores["Tirano"]["trattenuta_pct"] == 15 and stores["Tirano"]["trattenuta_iva"] is False
    assert stores["Sondalo"]["trattenuta_pct"] == 15 and stores["Sondalo"]["trattenuta_iva"] is False
    assert stores["Grosio"]["trattenuta_pct"] == 15 and stores["Grosio"]["trattenuta_iva"] is True
    assert "Iliad" in d["provenienze"] and "WindTre" in d["provenienze"]
    assert len(d["users"]) > 0


def test_regole_seed_count(client):
    r = client.get(f"{BASE_URL}/api/compensi/regole")
    assert r.status_code == 200
    assert len(r.json()) == 13


def test_regole_crud(client):
    # Create
    payload = {"nome": "TEST_regola_iter23", "voce": "sim", "importo": 10, "destinatario_tipo": "store"}
    r = client.post(f"{BASE_URL}/api/compensi/regole", json=payload)
    assert r.status_code == 200
    rid = r.json()["id"]
    STATE["regole_created"].append(rid)
    # Update
    r = client.put(f"{BASE_URL}/api/compensi/regole/{rid}", json={**payload, "importo": 20})
    assert r.status_code == 200 and r.json()["importo"] == 20
    # Bad voce
    r = client.post(f"{BASE_URL}/api/compensi/regole", json={**payload, "voce": "invalida"})
    assert r.status_code == 400
    r = client.put(f"{BASE_URL}/api/compensi/regole/{rid}", json={**payload, "voce": "xxx"})
    assert r.status_code == 400
    # Delete
    r = client.delete(f"{BASE_URL}/api/compensi/regole/{rid}")
    assert r.status_code == 200
    STATE["regole_created"].remove(rid)
    # 404
    r = client.delete(f"{BASE_URL}/api/compensi/regole/nonexistent")
    assert r.status_code == 404


# -------------------- Scenario Calcolo cambiaora --------------------
def test_scenario_cambiaora_calcolo(client):
    # Create test client
    payload = {
        "cognome": "TEST_ITER23", "nome": "CambioOra", "telefono": "3300000023",
        "gestione": "cambiaora", "lavorazione": "cambio_effettuato",
        "data_contratto": "2026-09-10", "venditore_id": TIRANO,
    }
    r = client.post(f"{BASE_URL}/api/clients", json=payload)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    STATE["client_id"] = cid
    # Mark paid
    r = client.post(f"{BASE_URL}/api/clients/{cid}/mark-paid")
    assert r.status_code == 200
    # Set regola importo=20
    seed_get = client.get(f"{BASE_URL}/api/compensi/regole").json()
    rule = next(x for x in seed_get if x["id"] == STATE["regola_cambiaora_id"])
    upd = {**rule, "importo": 20}
    # Remove read-only keys
    for k in ("id", "created_at", "updated_at"):
        upd.pop(k, None)
    r = client.put(f"{BASE_URL}/api/compensi/regole/{STATE['regola_cambiaora_id']}", json=upd)
    assert r.status_code == 200 and r.json()["importo"] == 20

    # Calcolo settembre 2026 competenza
    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    assert r.status_code == 200
    d = r.json()
    tirano = next((x for x in d["destinatari"] if x["id"] == TIRANO), None)
    assert tirano is not None, "Tirano not in destinatari"
    riga = next((x for x in tirano["righe"] if x["voce"] == "cambiaora" and x["regola_id"] == STATE["regola_cambiaora_id"]), None)
    assert riga is not None, f"cambiaora rule row not in Tirano: {tirano['righe']}"
    assert riga["conteggio"] >= 1
    assert riga["importo_unitario"] == 20
    # trattenuta 15%, iva=0 (Tirano)
    assert tirano["trattenuta_pct"] == 15
    assert tirano["iva_su_trattenuta"] == 0
    assert abs(tirano["netto"] - tirano["lordo"] * 0.85) < 0.01
    assert riga["pagamento"] == "2026-11"

    # Calcolo per pagamento novembre
    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=11&per_pagamento=true")
    assert r.status_code == 200
    d = r.json()
    tirano = next((x for x in d["destinatari"] if x["id"] == TIRANO), None)
    assert tirano is not None
    riga = next((x for x in tirano["righe"] if x["regola_id"] == STATE["regola_cambiaora_id"]), None)
    assert riga is not None
    assert riga["competenza"] == "2026-09"


# -------------------- Scenario SIM soglia globale --------------------
def test_scenario_sim_mnp_soglia(client):
    for i in range(2):
        payload = {
            "client_id": STATE["client_id"], "tipo": "sim", "operatore_tel": "WINDTRE",
            "tipo_attivazione": "mnp", "provenienza_operatore": "Iliad",
            "data_attivazione": "2026-09-05", "ricarica_iniziale": 10, "costo_sim": 5,
            "venditore_id": GROSIO,
        }
        r = client.post(f"{BASE_URL}/api/servizi", json=payload)
        assert r.status_code == 200, r.text
        STATE["servizi_ids"].append(r.json()["id"])

    # Calcolo: extra MNP Grosio soglia_raggiunta false, totale 0
    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    d = r.json()
    grosio = next((x for x in d["destinatari"] if x["id"] == GROSIO), None)
    assert grosio is not None
    riga = next((x for x in grosio["righe"] if x["regola_id"] == STATE["regola_extra_mnp_iliad_id"]), None)
    assert riga is not None, f"extra MNP rule not found in Grosio: {[r['nome'] for r in grosio['righe']]}"
    assert riga["soglia_raggiunta"] is False
    assert riga["totale"] == 0
    assert grosio["ricariche_da_richiedere"] == 20
    assert grosio["costo_sim"] == 10

    # Modifica regola soglia 1
    rule = next(x for x in client.get(f"{BASE_URL}/api/compensi/regole").json() if x["id"] == STATE["regola_extra_mnp_iliad_id"])
    upd = {k: v for k, v in rule.items() if k not in ("id", "created_at", "updated_at")}
    upd["soglia"] = 1
    r = client.put(f"{BASE_URL}/api/compensi/regole/{STATE['regola_extra_mnp_iliad_id']}", json=upd)
    assert r.status_code == 200

    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    d = r.json()
    grosio = next((x for x in d["destinatari"] if x["id"] == GROSIO), None)
    riga = next((x for x in grosio["righe"] if x["regola_id"] == STATE["regola_extra_mnp_iliad_id"]), None)
    assert riga["soglia_raggiunta"] is True
    assert riga["totale"] == 70  # 2*35
    # Grosio has trattenuta_iva=True: iva_su_trattenuta = trattenuta*0.22
    assert grosio["trattenuta"] > 0
    assert abs(grosio["iva_su_trattenuta"] - grosio["trattenuta"] * 0.22) < 0.01


# -------------------- Scenario gare --------------------
def test_scenario_gara_eolo(client):
    # Set regola eolo gara importo=100
    rule = next(x for x in client.get(f"{BASE_URL}/api/compensi/regole").json() if x["id"] == STATE["regola_eolo_gara_id"])
    upd = {k: v for k, v in rule.items() if k not in ("id", "created_at", "updated_at")}
    upd["importo"] = 100
    r = client.put(f"{BASE_URL}/api/compensi/regole/{STATE['regola_eolo_gara_id']}", json=upd)
    assert r.status_code == 200

    # Create servizio internet Eolo su Sondalo
    payload = {
        "client_id": STATE["client_id"], "tipo": "internet", "operatore_tel": "EOLO",
        "data_attivazione": "2026-09-05", "venditore_id": SONDALO,
    }
    r = client.post(f"{BASE_URL}/api/servizi", json=payload)
    assert r.status_code == 200, r.text
    STATE["servizio_internet_id"] = r.json()["id"]

    # Calcolo: gara_pagata false, gare_in_attesa 100, lordo non include
    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    d = r.json()
    sondalo = next((x for x in d["destinatari"] if x["id"] == SONDALO), None)
    assert sondalo is not None
    riga = next((x for x in sondalo["righe"] if x["regola_id"] == STATE["regola_eolo_gara_id"]), None)
    assert riga is not None
    assert riga["gara_pagata"] is False
    assert sondalo["gare_in_attesa"] == 100
    # lordo doesn't include 100
    lordo_eolo_gara = sum(rw["totale"] for rw in sondalo["righe"] if rw["regola_id"] == STATE["regola_eolo_gara_id"] and rw["gara_pagata"])
    assert lordo_eolo_gara == 0

    # Segna pagata
    r = client.post(f"{BASE_URL}/api/compensi/gare/pagata",
                    json={"regola_id": STATE["regola_eolo_gara_id"], "mese": "2026-09", "pagata": True})
    assert r.status_code == 200

    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    d = r.json()
    sondalo = next((x for x in d["destinatari"] if x["id"] == SONDALO), None)
    assert sondalo["lordo"] >= 100


# -------------------- Per Ipro --------------------
def test_per_ipro_admin(client):
    cid = STATE["client_id"]
    r = client.post(f"{BASE_URL}/api/clients/{cid}/per-ipro", json={"per_ipro": True})
    assert r.status_code == 200 and r.json()["per_ipro"] is True

    r = client.get(f"{BASE_URL}/api/compensi/calcolo?anno=2026&mese=9")
    d = r.json()
    tirano = next((x for x in d["destinatari"] if x["id"] == TIRANO), None)
    ipro = next((x for x in d["destinatari"] if x["id"] == IPRO), None)
    if tirano:
        cambia_rows = [rw for rw in tirano["righe"] if rw["voce"] == "cambiaora"]
        assert all(rw["conteggio"] == 0 for rw in cambia_rows) or not cambia_rows
    assert ipro is not None
    cambia_ipro = next((rw for rw in ipro["righe"] if rw["voce"] == "cambiaora"), None)
    assert cambia_ipro is not None and cambia_ipro["conteggio"] >= 1


# -------------------- Plafond --------------------
def test_plafond(client):
    r = client.post(f"{BASE_URL}/api/compensi/plafond",
                    json={"store_id": "", "importo": 100, "causale": "TEST_iter23"})
    assert r.status_code == 200
    STATE["plafond_mov_id"] = r.json()["id"]

    r = client.get(f"{BASE_URL}/api/compensi/plafond")
    assert r.status_code == 200
    d = r.json()
    globale = next((s for s in d["saldi"] if s["store_id"] == ""), None)
    assert globale is not None
    assert globale["carichi"] >= 100
    # Ricariche >= 20 (2 SIM da 10)
    assert globale["ricariche"] >= 20

    r = client.delete(f"{BASE_URL}/api/compensi/plafond/{STATE['plafond_mov_id']}")
    assert r.status_code == 200


# -------------------- Trattenute --------------------
def test_trattenute(client):
    r = client.patch(f"{BASE_URL}/api/compensi/trattenute/{TIRANO}",
                     json={"trattenuta_pct": 10, "trattenuta_iva": False})
    assert r.status_code == 200
    meta = client.get(f"{BASE_URL}/api/compensi/meta").json()
    tirano = next(s for s in meta["stores"] if s["id"] == TIRANO)
    assert tirano["trattenuta_pct"] == 10
    # Restore
    r = client.patch(f"{BASE_URL}/api/compensi/trattenute/{TIRANO}",
                     json={"trattenuta_pct": 15, "trattenuta_iva": False})
    assert r.status_code == 200


# -------------------- Notifiche backup --------------------
def test_notifiche_backup_admin(client):
    r = client.get(f"{BASE_URL}/api/notifiche")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    backup_scaduti = [n for n in items if n.get("tipo") == "backup_scaduto"]
    # backup recente: no notifica
    assert len(backup_scaduti) == 0, f"Backup scaduto notification present: {backup_scaduti}"


# -------------------- Users can_assign_ipro --------------------
def test_user_can_assign_ipro(client):
    users = client.get(f"{BASE_URL}/api/users").json()
    deb = next((u for u in users if u["email"] == "deborah@cambiaora.local"), None)
    assert deb is not None
    assert deb.get("can_assign_ipro") is True, f"Deborah should have can_assign_ipro=true: {deb}"

    # PATCH michael user
    michael = next((u for u in users if u["email"] == "michael@cambiaora.local"), None)
    if michael:
        orig = michael.get("can_assign_ipro", False)
        r = client.patch(f"{BASE_URL}/api/users/{michael['id']}", json={"can_assign_ipro": True})
        assert r.status_code == 200
        m2 = next(u for u in client.get(f"{BASE_URL}/api/users").json() if u["id"] == michael["id"])
        assert m2.get("can_assign_ipro") is True
        # restore
        client.patch(f"{BASE_URL}/api/users/{michael['id']}", json={"can_assign_ipro": orig})


# -------------------- Cleanup --------------------
def test_zz_cleanup(client):
    # Reset per_ipro
    if STATE["client_id"]:
        client.post(f"{BASE_URL}/api/clients/{STATE['client_id']}/per-ipro", json={"per_ipro": False})
    # Delete servizi
    for sid in STATE["servizi_ids"]:
        client.delete(f"{BASE_URL}/api/servizi/{sid}")
    if STATE["servizio_internet_id"]:
        client.delete(f"{BASE_URL}/api/servizi/{STATE['servizio_internet_id']}")
    # Delete client
    if STATE["client_id"]:
        client.delete(f"{BASE_URL}/api/clients/{STATE['client_id']}")
    # Reset regole seed importi & soglia
    seed_get = client.get(f"{BASE_URL}/api/compensi/regole").json()
    for target in ("f350149c-faac-409f-afc2-9d7925f354ce", "aa1d7784-1483-44b2-8f47-a82d4630cec9"):
        rule = next((x for x in seed_get if x["id"] == target), None)
        if rule:
            upd = {k: v for k, v in rule.items() if k not in ("id", "created_at", "updated_at")}
            upd["importo"] = 0
            client.put(f"{BASE_URL}/api/compensi/regole/{target}", json=upd)
    # Reset extra MNP soglia=15
    rule = next((x for x in seed_get if x["id"] == "244cdded-aecb-486c-8a5a-1599323c5574"), None)
    if rule:
        upd = {k: v for k, v in rule.items() if k not in ("id", "created_at", "updated_at")}
        upd["soglia"] = 15
        client.put(f"{BASE_URL}/api/compensi/regole/244cdded-aecb-486c-8a5a-1599323c5574", json=upd)
    # Remove gara pagata mark
    client.post(f"{BASE_URL}/api/compensi/gare/pagata",
                json={"regola_id": "aa1d7784-1483-44b2-8f47-a82d4630cec9", "mese": "2026-09", "pagata": False})
