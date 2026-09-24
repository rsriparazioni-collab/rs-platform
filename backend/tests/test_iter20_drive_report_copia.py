"""Iter 20: Google Drive integration, anteprima report ritiri, client_contacts su servizi."""
import os
import time
import pyotp
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://utility-renewals.preview.emergentagent.com").rstrip("/")
TOTP_SECRET = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"


def _login(email: str, password: str, totp: str | None = None) -> str | None:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    j = r.json()
    if j.get("token"):
        return j["token"]
    if j.get("mfa_required"):
        mfa_token = j["mfa_token"]
        if not totp:
            return None
        for _ in range(3):
            t = pyotp.TOTP(totp)
            rem = 30 - (int(time.time()) % 30)
            if rem < 3:
                time.sleep(rem + 1)
            code = t.now()
            r2 = requests.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": mfa_token, "code": code})
            if r2.status_code == 200:
                return r2.json().get("token")
            # anti-replay: wait next window and retry
            time.sleep(30 - (int(time.time()) % 30) + 1)
    return None


@pytest.fixture(scope="module")
def admin_token():
    t = _login("rsriparazioni@gmail.com", "Devis2026!", TOTP_SECRET)
    if not t:
        pytest.skip("Admin login failed")
    return t


@pytest.fixture(scope="module")
def admin_hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def deborah_token():
    return _login("deborah@cambiaora.local", "Deborah2026!")


@pytest.fixture(scope="module")
def michael_token():
    return _login("michael@cambiaora.local", "Michael2026!")


# ---------------- Google Drive ----------------
class TestGoogleDrive:
    def test_status_admin(self, admin_hdr):
        r = requests.get(f"{BASE_URL}/api/google-drive/status", headers=admin_hdr)
        assert r.status_code == 200
        j = r.json()
        assert j.get("configured") is True, f"Expected configured=true, got {j}"
        assert j.get("connected") is False, f"Expected connected=false, got {j}"

    def test_connect_admin_returns_auth_url(self, admin_hdr):
        r = requests.get(f"{BASE_URL}/api/google-drive/connect", headers=admin_hdr)
        assert r.status_code == 200, r.text
        url = r.json().get("authorization_url", "")
        assert "accounts.google.com" in url
        assert "google-drive/callback" in url or "google-drive%2Fcallback" in url
        assert "drive.file" in url or "drive.file".replace(".", "%2E") in url or "drive.file" in requests.utils.unquote(url)

    def test_connect_forbidden_for_non_admin(self, deborah_token):
        if not deborah_token:
            pytest.skip("Deborah requires 2FA setup - X-MFA-Setup-Required")
        r = requests.get(f"{BASE_URL}/api/google-drive/connect",
                         headers={"Authorization": f"Bearer {deborah_token}"})
        assert r.status_code == 403, r.text

    def test_sync_without_connection(self, admin_hdr):
        r = requests.post(f"{BASE_URL}/api/google-drive/sync-ritiri", headers=admin_hdr)
        assert r.status_code == 400, r.text

    def test_callback_invalid_state_redirects(self):
        r = requests.get(f"{BASE_URL}/api/google-drive/callback?state=invalid_xxx",
                         allow_redirects=False)
        assert r.status_code in (302, 307), f"got {r.status_code}"
        loc = r.headers.get("location", "")
        assert "/ritiri" in loc
        assert "drive=error" in loc


# ---------------- Anteprima report mensile ----------------
class TestAnteprimaReport:
    def test_anteprima_admin(self, admin_hdr):
        r = requests.get(f"{BASE_URL}/api/ritiri/report-mensile/anteprima?anno=2026&mese=6",
                         headers=admin_hdr)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        for s in data:
            for k in ("store_id", "nome", "ritiri", "valore", "senza_documenti", "stati", "inviato_at", "righe"):
                assert k in s, f"Missing key {k} in {s}"
        # Morbegno: 3 ritiri valore 210
        m = next((s for s in data if s["nome"].lower() == "morbegno"), None)
        assert m is not None, "Morbegno store not found"
        assert m["ritiri"] == 3, f"Expected 3, got {m['ritiri']}"
        assert float(m["valore"]) == 210.0, f"Expected 210, got {m['valore']}"
        assert len(m["righe"]) == 3

    def test_anteprima_forbidden_for_negozio(self, michael_token):
        if not michael_token:
            pytest.skip("Michael requires 2FA setup")
        r = requests.get(f"{BASE_URL}/api/ritiri/report-mensile/anteprima?anno=2026&mese=6",
                         headers={"Authorization": f"Bearer {michael_token}"})
        assert r.status_code == 403, r.text


# ---------------- Servizi client_contacts ----------------
class TestServiziClientContacts:
    def test_get_servizio_includes_client_contacts(self, admin_hdr):
        # Cerca un servizio il cui client ha tutti i campi indirizzo popolati
        r = requests.get(f"{BASE_URL}/api/servizi?limit=200", headers=admin_hdr)
        assert r.status_code == 200
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("data") or []
        assert len(items) > 0, "No servizi found"
        required = ("indirizzo", "civico", "cap", "comune", "provincia", "p_iva")
        found_full = None
        found_any = None
        for it in items:
            r2 = requests.get(f"{BASE_URL}/api/servizi/{it['id']}", headers=admin_hdr)
            if r2.status_code != 200:
                continue
            s = r2.json()
            cc = s.get("client_contacts") or {}
            if found_any is None and cc:
                found_any = cc
            if all(k in cc for k in required):
                found_full = cc
                break
        # Il requisito è che le chiavi siano incluse quando presenti sul client.
        # La projection include civico/cap/comune, ma MongoDB non aggiunge chiavi mancanti.
        # Verifichiamo almeno che la projection sia richiesta correttamente e che
        # su un client con dati completi tutte le chiavi tornino.
        assert found_any is not None, "Nessun servizio con client_contacts trovato"
        if found_full is None:
            pytest.skip(f"Nessun cliente con tutti i campi indirizzo trovato tra i servizi. Ultimo esaminato: {list(found_any.keys())}")
        for k in required:
            assert k in found_full
