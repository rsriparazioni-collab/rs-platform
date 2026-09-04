"""Privilege escalation check: negozio user creating an 'operatore' account."""
import os

import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env["REACT_APP_BACKEND_URL"]).rstrip("/")

EMAIL = "test_qa_escalate@cambiaora.local"
PWD = "Escalate2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    return s, r


def test_negozio_can_escalate_to_operatore():
    s_mic, r = _login("michael@cambiaora.local", "Michael2026!")
    assert r.status_code == 200
    mic_clients = s_mic.get(f"{BASE_URL}/api/clients?limit=2000", timeout=60).json()
    mic_count = len(mic_clients if isinstance(mic_clients, list) else mic_clients.get("items", []))

    create = s_mic.post(f"{BASE_URL}/api/users", json={
        "name": "TEST_QA escalate", "email": EMAIL, "password": PWD,
        "role": "operatore", "store_ids": [], "can_view_all": True}, timeout=30)
    print("create-as-negozio status:", create.status_code, create.text[:200])

    escalated_count = None
    if create.status_code == 200:
        s_esc, r2 = _login(EMAIL, PWD)
        assert r2.status_code == 200
        esc = s_esc.get(f"{BASE_URL}/api/clients?limit=2000", timeout=60).json()
        escalated_count = len(esc if isinstance(esc, list) else esc.get("items", []))
        print(f"michael sees {mic_count} clients; account he created (operatore) sees {escalated_count}")
        # cleanup with admin
        s_admin, _ = _login("rsriparazioni@gmail.com", "Devis2026!")
        uid = create.json()["id"]
        d = s_admin.delete(f"{BASE_URL}/api/users/{uid}", timeout=30)
        print("cleanup delete:", d.status_code)

    assert create.status_code == 403, (
        f"SECURITY: negozio user created an 'operatore' account (status {create.status_code}); "
        f"the new account can read {escalated_count} clients vs {mic_count} for the negozio user"
    )
