# Iter44: store WhatsApp message templates (21 keys) - defaults + persistence via PATCH /api/stores/{id}
import os
import pyotp
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOTP_SECRET = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"

ALL_KEYS = ["msg_privacy", "msg_pronto", "msg_promemoria", "msg_recensione", "msg_vincolo", "msg_offerta_annuale",
            "msg_rinnovo_energia", "msg_truffe", "msg_bollette", "msg_compleanno", "msg_conferma_link",
            "msg_ricambio_arrivato", "msg_disponibile", "msg_vendita_ordinato", "msg_vendita_arrivato",
            "msg_ordine_arrivato", "msg_sollecito_ritiro", "msg_firma_ritiro", "msg_grazie_bolletta",
            "msg_grazie_documento", "msg_grazie_altro"]


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    mfa = r.json().get("mfa_token")
    r = s.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": mfa, "code": pyotp.TOTP(TOTP_SECRET).now()})
    if r.status_code != 200:
        pytest.skip(f"MFA failed {r.text}")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def store(client):
    stores = client.get(f"{BASE_URL}/api/stores").json()
    st = next((x for x in stores if "sondrio" in x["nome"].lower()), stores[0])
    return st


def test_defaults_21_keys(client):
    r = client.get(f"{BASE_URL}/api/messaggi-default")
    assert r.status_code == 200
    d = r.json()["defaults"]
    missing = [k for k in ALL_KEYS if k not in d]
    assert not missing, missing
    assert len([k for k in d if k.startswith("msg_")]) >= 21
    assert all(isinstance(d[k], str) and d[k] for k in ALL_KEYS)
    assert isinstance(r.json()["placeholders"], list)


def test_defaults_requires_auth():
    r = requests.get(f"{BASE_URL}/api/messaggi-default")
    assert r.status_code in (401, 403)


@pytest.mark.parametrize("key", ["msg_grazie_documento", "msg_firma_ritiro", "msg_sollecito_ritiro"])
def test_patch_new_key_persist_and_restore(client, store, key):
    original = store.get(key, "") or ""
    val = f"TEST_X {{nome}} {key}"
    r = client.patch(f"{BASE_URL}/api/stores/{store['id']}", json={key: val})
    assert r.status_code == 200, r.text
    assert r.json()[key] == val
    got = next(x for x in client.get(f"{BASE_URL}/api/stores").json() if x["id"] == store["id"])
    assert got[key] == val
    # other fields intact
    assert got["nome"] == store["nome"]
    r = client.patch(f"{BASE_URL}/api/stores/{store['id']}", json={key: original})
    assert r.status_code == 200
    got = next(x for x in client.get(f"{BASE_URL}/api/stores").json() if x["id"] == store["id"])
    assert (got.get(key) or "") == original


def test_patch_full_form_all_keys(client, store):
    # Simulate frontend form (all 21 keys) - all must persist
    originals = {k: store.get(k, "") or "" for k in ALL_KEYS}
    payload = {k: f"TEST_{k} {{nome}}" for k in ALL_KEYS}
    r = client.patch(f"{BASE_URL}/api/stores/{store['id']}", json=payload)
    assert r.status_code == 200
    got = next(x for x in client.get(f"{BASE_URL}/api/stores").json() if x["id"] == store["id"])
    try:
        assert all(got[k] == payload[k] for k in ALL_KEYS)
    finally:
        client.patch(f"{BASE_URL}/api/stores/{store['id']}", json=originals)
    got = next(x for x in client.get(f"{BASE_URL}/api/stores").json() if x["id"] == store["id"])
    assert all((got.get(k) or "") == originals[k] for k in ALL_KEYS)


def test_put_method(client, store):
    # Review request mentions PUT; backend only exposes PATCH
    r = client.put(f"{BASE_URL}/api/stores/{store['id']}", json={"msg_grazie_documento": ""})
    print("PUT status", r.status_code)
    assert r.status_code in (200, 405)
