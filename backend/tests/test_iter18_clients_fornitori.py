"""Iter 18: test bug fix ClientForm prefill, fornitori idempotente, /clients CRUD (civico/cap/comune/iban/note/date), /clients/{id}/collegati."""
import os
import time
import pytest
import pyotp
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://utility-renewals.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rsriparazioni@gmail.com"
ADMIN_PW = "Devis2026!"
TOTP_SECRET = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    if data.get("mfa_required"):
        code = pyotp.TOTP(TOTP_SECRET).now()
        r2 = s.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": data["mfa_token"], "code": code}, timeout=20)
        assert r2.status_code == 200, r2.text
        data = r2.json()
    token = data.get("token") or data.get("access_token")
    assert token, data
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def api():
    return _login()


@pytest.fixture(scope="module")
def created_ids():
    return {"clients": [], "fornitori_names": []}


# ---- Meta / Fornitori idempotenti ----
def test_meta_ok(api):
    r = api.get(f"{BASE_URL}/api/meta")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "suppliers" in d and isinstance(d["suppliers"], list)


def test_fornitori_idempotent_case_insensitive(api, created_ids):
    name = "QA Energia Test"
    r1 = api.post(f"{BASE_URL}/api/fornitori", json={"nome": name})
    assert r1.status_code == 200, r1.text
    assert r1.json()["nome"].lower() == name.lower()
    created_ids["fornitori_names"].append(r1.json()["nome"])

    # 2nd call with different case: must NOT duplicate
    r2 = api.post(f"{BASE_URL}/api/fornitori", json={"nome": "qa energia TEST"})
    assert r2.status_code == 200
    # Meta must contain it exactly once
    meta = api.get(f"{BASE_URL}/api/meta").json()["suppliers"]
    occurrences = sum(1 for s in meta if s.lower() == name.lower())
    assert occurrences == 1, f"Fornitore duplicato in meta: {occurrences}"

    # Too short
    r3 = api.post(f"{BASE_URL}/api/fornitori", json={"nome": "a"})
    assert r3.status_code == 400


# ---- Client CRUD: civico/cap/comune/iban/note/date persisted ----
def test_client_create_and_persist_all_fields(api, created_ids):
    payload = {
        "nome": "QA_Mario",
        "cognome": "QA_Rossi",
        "tipo_cliente": "ditta_individuale",
        "codice_fiscale": "RSSMRA80A01H501U",
        "p_iva": "12345678903",
        "indirizzo": "Via Verdi",
        "civico": "12/A",
        "cap": "23100",
        "comune": "Sondrio",
        "provincia": "SO",
        "iban": "IT60X0542811101000000123456",
        "telefono": "3331112222",
        "email": "qa@example.com",
        "tipo_bolletta": "luce",
        "fornitore_provenienza": "QA Energia Test",
        "data_verifica": "2026-02-01",
        "data_cambio": "2026-03-01",
        "note": "QA note testo lungo",
    }
    r = api.post(f"{BASE_URL}/api/clients", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    cid = body.get("id") or body.get("client", {}).get("id")
    assert cid
    created_ids["clients"].append(cid)

    # GET must return all fields
    g = api.get(f"{BASE_URL}/api/clients/{cid}").json()
    for k in ["indirizzo", "civico", "cap", "comune", "provincia", "iban", "note",
              "data_verifica", "data_cambio", "codice_fiscale", "p_iva"]:
        assert (g.get(k) or "") == payload[k], f"Campo {k} mismatch: {g.get(k)!r} vs {payload[k]!r}"
    assert g.get("tipo_cliente") == "ditta_individuale"


def test_patch_partial_only_phone_preserves_other_fields(api, created_ids):
    """Regression: PATCH con corpo completo NON deve azzerare i campi presenti quando li ripassiamo intatti."""
    assert created_ids["clients"], "prerequisite fallita"
    cid = created_ids["clients"][0]
    current = api.get(f"{BASE_URL}/api/clients/{cid}").json()
    # Simuliamo il fix: form ricarica GET e poi PATCH con tutti i campi cambiando solo telefono
    body = {k: (current.get(k) or "") for k in [
        "nome", "cognome", "tipo_cliente", "codice_fiscale", "p_iva", "indirizzo", "civico",
        "cap", "comune", "provincia", "iban", "email", "telefono", "tipo_bolletta",
        "fornitore_provenienza", "nuovo_fornitore", "note", "data_verifica", "data_cambio",
        "data_contratto", "tipo_contratto", "lavorazione", "origine", "venditore_id",
        "operatore_id", "gestione", "pod", "pdr"
    ]}
    body["telefono"] = "3339998888"
    r = api.patch(f"{BASE_URL}/api/clients/{cid}", json=body)
    assert r.status_code == 200, r.text

    g = api.get(f"{BASE_URL}/api/clients/{cid}").json()
    assert g["telefono"] == "3339998888"
    assert g["iban"] == "IT60X0542811101000000123456"
    assert g["indirizzo"] == "Via Verdi"
    assert g["civico"] == "12/A"
    assert g["cap"] == "23100"
    assert g["note"] == "QA note testo lungo"
    assert g["data_verifica"] == "2026-02-01"
    assert g["data_cambio"] == "2026-03-01"


# ---- Client collegati: stessa persona (CF/tel), escluso se stesso ----
def test_collegati_by_cf_and_phone(api, created_ids):
    assert created_ids["clients"]
    cid1 = created_ids["clients"][0]
    payload = {
        "nome": "QA_Mario",
        "cognome": "QA_Rossi",
        "tipo_cliente": "ditta_individuale",
        "codice_fiscale": "RSSMRA80A01H501U",
        "p_iva": "12345678903",
        "telefono": "3339998888",
        "tipo_bolletta": "gas",
        "indirizzo": "Via Verdi",
        "civico": "12/A",
        "cap": "23100",
        "comune": "Sondrio",
        "provincia": "SO",
    }
    r = api.post(f"{BASE_URL}/api/clients", json=payload)
    assert r.status_code == 200, r.text
    cid2 = r.json().get("id") or r.json().get("client", {}).get("id")
    assert cid2
    created_ids["clients"].append(cid2)

    coll = api.get(f"{BASE_URL}/api/clients/{cid1}/collegati").json()
    ids = [c["id"] for c in coll]
    assert cid2 in ids
    assert cid1 not in ids, "il cliente non deve trovarsi tra i propri collegati"


def test_list_filter_tipo_cliente(api):
    r = api.get(f"{BASE_URL}/api/clients?tipo_cliente=ditta_individuale")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("clients", []))
    # non deve crashare, ammesso vuoto
    assert isinstance(items, list)


# ---- Cleanup ----
def test_zzz_cleanup(api, created_ids):
    for cid in created_ids["clients"]:
        api.delete(f"{BASE_URL}/api/clients/{cid}")
    # Rimozione fornitore QA (solo custom)
    for name in created_ids["fornitori_names"]:
        # nessun endpoint DELETE fornitore standard: lo puliamo direttamente sarebbe fuori scope
        pass
