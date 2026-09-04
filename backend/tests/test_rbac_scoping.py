"""RBAC scoping checks for negozio users (Michael / Lorenzo) + cookie auth."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

ACCOUNTS = {
    "admin": ("rsriparazioni@gmail.com", "Devis2026!"),
    "operatore": ("deborah@cambiaora.local", "Deborah2026!"),
    "michael": ("michael@cambiaora.local", "Michael2026!"),
    "lorenzo": ("lorenzo@cambiaora.local", "Lorenzo2026!"),
}


def login(who):
    email, password = ACCOUNTS[who]
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert "gu_token" in s.cookies, "cookie gu_token not set"
    return s, r.json()


@pytest.mark.parametrize("who", ["admin", "operatore", "michael", "lorenzo"])
def test_login_and_me_via_cookie_only(who):
    s, payload = login(who)
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert me.status_code == 200
    assert me.json()["email"] == ACCOUNTS[who][0]
    assert me.json()["role"] == payload["user"]["role"]


def test_negozio_client_scope_matches_own_stores():
    s_admin, _ = login("admin")
    s_mic, mic = login("michael")

    stores = s_admin.get(f"{BASE_URL}/api/stores", timeout=30).json()
    my_store_ids = set(mic["user"].get("store_ids") or [])
    assert my_store_ids, "michael has no store_ids"

    admin_clients = s_admin.get(f"{BASE_URL}/api/clients?limit=2000", timeout=60).json()
    admin_list = admin_clients if isinstance(admin_clients, list) else admin_clients.get("items", [])
    expected = [c for c in admin_list if c.get("venditore_id") in my_store_ids]

    mic_clients = s_mic.get(f"{BASE_URL}/api/clients?limit=2000", timeout=60).json()
    mic_list = mic_clients if isinstance(mic_clients, list) else mic_clients.get("items", [])

    outside = [c for c in mic_list if c.get("venditore_id") not in my_store_ids]
    print("admin total:", len(admin_list), "michael total:", len(mic_list),
          "expected(own stores):", len(expected), "outside scope:", len(outside),
          "store names:", {st["id"]: st["nome"] for st in stores if st["id"] in my_store_ids})
    assert not outside, f"{len(outside)} clients returned outside michael's stores (e.g. venditore_id={outside[0].get('venditore_id')})"
    assert len(mic_list) == len(expected)


def test_negozio_cannot_list_users_or_stores():
    s, _ = login("michael")
    assert s.get(f"{BASE_URL}/api/users", timeout=30).status_code == 403
    assert s.get(f"{BASE_URL}/api/operators/stats", timeout=30).status_code == 403


def test_negozio_cannot_create_user():
    s, _ = login("michael")
    # negozio NON può creare operatori o admin (escalation bloccata)
    r = s.post(f"{BASE_URL}/api/users", json={
        "name": "TEST_QA_neg", "email": "test_qa_neg@cambiaora.local",
        "password": "Test2026!", "role": "operatore", "can_view_all": True, "store_ids": []
    }, timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
    # negozio PUÒ creare solo utenti negozio sui propri store, senza can_view_all
    s_admin, _ = login("admin")
    r2 = s.post(f"{BASE_URL}/api/users", json={
        "name": "TEST_QA_neg", "email": "test_qa_neg@cambiaora.local",
        "password": "Test2026!", "role": "negozio", "can_view_all": True,
        "store_ids": ["id-esterno-non-suo"]
    }, timeout=30)
    assert r2.status_code == 200, f"expected 200, got {r2.status_code}: {r2.text[:200]}"
    created = r2.json()
    assert created["role"] == "negozio"
    assert not created["can_view_all"]
    _, u2r = login("michael")
    u2 = u2r["user"]
    assert all(x in u2["store_ids"] for x in created["store_ids"])
    # cleanup
    s_admin.delete(f"{BASE_URL}/api/users/{created['id']}", timeout=30)


def test_logout_clears_cookie():
    s, _ = login("admin")
    r = s.post(f"{BASE_URL}/api/auth/logout", timeout=30)
    assert r.status_code == 200
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert me.status_code == 401
