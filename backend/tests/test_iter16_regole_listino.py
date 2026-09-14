"""Iter 16 tests: Regole prezzi riparazioni, calcolo prezzo, listino fornitori, bolla PDF."""
import os
import io
import pytest
import pyotp
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
be = dotenv_values("/app/backend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE}/api"
TOTP_SECRET = os.environ.get("TEST_ADMIN_TOTP_SECRET") or be.get("TEST_ADMIN_TOTP_SECRET") or "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"


def _login_with_mfa(email, password, totp_secret=None):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    if d.get("mfa_required"):
        code = pyotp.TOTP(totp_secret).now()
        r2 = requests.post(f"{API}/auth/login/mfa", json={"mfa_token": d["mfa_token"], "code": code}, timeout=30)
        assert r2.status_code == 200, r2.text[:400]
        d = r2.json()
    return d["token"], d["user"]


@pytest.fixture(scope="module")
def admin_headers():
    tok, _ = _login_with_mfa("rsriparazioni@gmail.com", "Devis2026!", TOTP_SECRET)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def michael_headers():
    # Michael has no 2FA; may return X-MFA-Setup-Required header on protected routes
    r = requests.post(f"{API}/auth/login", json={"email": "michael@cambiaora.local", "password": "Michael2026!"}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    if d.get("mfa_required"):
        pytest.skip("Michael unexpectedly has MFA in preview")
    return {"Authorization": f"Bearer {d['token']}", "Content-Type": "application/json"}


# ---------- Regole prezzi ----------
class TestRegolePrezzi:
    def test_get_regole(self, admin_headers):
        r = requests.get(f"{API}/regole-prezzi", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "regole" in data and "tipologie" in data
        assert len(data["regole"]) == 9
        display_ip = next(r for r in data["regole"] if r["label"] == "Display iPhone")
        assert display_ip["manodopera"] == 40
        assert display_ip["ricarico_pct"] == 60

    def test_put_regole_admin_and_revert(self, admin_headers):
        # Fetch current
        cur = requests.get(f"{API}/regole-prezzi", headers=admin_headers, timeout=30).json()["regole"]
        # Modify Display iPhone manodopera 40 -> 41
        payload = []
        for r in cur:
            item = {k: r[k] for k in ("tipologia", "marca", "label", "manodopera", "ricarico_pct", "prezzo_min", "prezzo_max")}
            if item["label"] == "Display iPhone":
                item["manodopera"] = 41
            payload.append(item)
        r = requests.put(f"{API}/regole-prezzi", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, r.text[:400]
        upd = next(x for x in r.json()["regole"] if x["label"] == "Display iPhone")
        assert upd["manodopera"] == 41
        # GET reflects
        g = requests.get(f"{API}/regole-prezzi", headers=admin_headers, timeout=30).json()
        assert next(x for x in g["regole"] if x["label"] == "Display iPhone")["manodopera"] == 41

        # Revert
        for item in payload:
            if item["label"] == "Display iPhone":
                item["manodopera"] = 40
        r2 = requests.put(f"{API}/regole-prezzi", headers=admin_headers, json=payload, timeout=30)
        assert r2.status_code == 200
        rev = next(x for x in r2.json()["regole"] if x["label"] == "Display iPhone")
        assert rev["manodopera"] == 40

    def test_put_regole_not_admin_forbidden(self, michael_headers, admin_headers):
        cur = requests.get(f"{API}/regole-prezzi", headers=admin_headers, timeout=30).json()["regole"]
        payload = [{k: r[k] for k in ("tipologia", "marca", "label", "manodopera", "ricarico_pct", "prezzo_min", "prezzo_max")} for r in cur]
        r = requests.put(f"{API}/regole-prezzi", headers=michael_headers, json=payload, timeout=30)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}"


# ---------- Prezzo consigliato via /api/servizi ----------
class TestCalcoloPrezzoServizio:
    @pytest.fixture(scope="class")
    def cliente_id(self, admin_headers):
        r = requests.get(f"{API}/clients", headers=admin_headers, params={"limit": 5}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("clients") or []
        assert items, "No clients found"
        return items[0]["id"]

    def test_riparazione_iphone_display(self, admin_headers, cliente_id):
        payload = {
            "tipo": "riparazione",
            "client_id": cliente_id,
            "dispositivo": "TEST_ iPhone 13",
            "problema": "display rotto",
            "con_ricambio": True,
            "tipo_ricambio": "display",
            "costo_componente": 80,
            "minuti_lavoro": 30,
        }
        r = requests.post(f"{API}/servizi", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        s = r.json()
        assert s.get("prezzo_consigliato") == 205.0, f"iPhone display expected 205.0 got {s.get('prezzo_consigliato')}"
        sid = s["id"]

        # PATCH -> Samsung Galaxy S23 costo 180 => 385.0 (PATCH expects full ServizioInput body)
        payload2 = {**payload, "dispositivo": "TEST_ Samsung Galaxy S23", "costo_componente": 180}
        pr = requests.patch(f"{API}/servizi/{sid}", headers=admin_headers, json=payload2, timeout=30)
        assert pr.status_code == 200, pr.text[:400]
        assert pr.json().get("prezzo_consigliato") == 385.0, f"Samsung expected 385.0 got {pr.json().get('prezzo_consigliato')}"

        # PATCH -> con_ricambio False minuti 45 => 45.0
        payload3 = {**payload2, "con_ricambio": False, "tipo_ricambio": "", "minuti_lavoro": 45}
        pr2 = requests.patch(f"{API}/servizi/{sid}", headers=admin_headers, json=payload3, timeout=30)
        assert pr2.status_code == 200, pr2.text[:400]
        assert pr2.json().get("prezzo_consigliato") == 45.0, f"software expected 45.0 got {pr2.json().get('prezzo_consigliato')}"

        # Cleanup
        d = requests.delete(f"{API}/servizi/{sid}", headers=admin_headers, timeout=30)
        assert d.status_code in (200, 204)


# ---------- Listino fornitori ----------
class TestListinoFornitori:
    def test_parse_fattura_pdf(self, admin_headers):
        pdf_path = "/tmp/fattura_test.pdf"
        if not os.path.exists(pdf_path):
            # Generate simple pdf with fpdf if missing
            try:
                from fpdf import FPDF
            except ImportError:
                pytest.skip("fpdf not available and pdf missing")
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=10)
            for ln in [
                "SIFAR GROUP SRL  Fattura n. 1234 del 12/09/2026",
                "Codice  Descrizione  Q.ta  Prezzo  Totale",
                "DISP-IP13-OLED Display iPhone 13 OLED Hard  2  79,00  158,00",
                "BAT-S22 Batteria Samsung Galaxy S22 originale  1  18,50  18,50",
                "CON-XRED12 Connettore ricarica Xiaomi Redmi 12 flat  3  4,20  12,60",
                "Totale imponibile  189,10",
            ]:
                pdf.cell(0, 6, ln, ln=1)
            pdf.output(pdf_path)
        with open(pdf_path, "rb") as f:
            files = {"file": ("fattura_test.pdf", f, "application/pdf")}
            hdr = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
            r = requests.post(f"{API}/listino/parse-fattura", headers=hdr, files=files, timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("fornitore") == "Sifar"
        prezzi = [row["prezzo_netto"] for row in data["righe"]]
        assert 79.0 in prezzi and 18.5 in prezzi and 4.2 in prezzi, f"got {prezzi}"
        assert len(data["righe"]) >= 3
        for r_ in data["righe"]:
            assert "codice" in r_ and "descrizione" in r_ and "prezzo_netto" in r_

    def test_parse_fattura_not_pdf_400(self, admin_headers):
        hdr = {k: v for k, v in admin_headers.items() if k != "Content-Type"}
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        r = requests.post(f"{API}/listino/parse-fattura", headers=hdr, files=files, timeout=30)
        assert r.status_code == 400

    def test_listino_crud_and_search(self, admin_headers):
        righe = [
            {"codice": "TEST_DISP01", "descrizione": "TEST_ Display iPhone 13 OLED", "prezzo_netto": 79.0, "fornitore": "Sifar", "tipologia": "display", "marca": "apple"},
            {"codice": "TEST_BAT01", "descrizione": "TEST_ Batteria Samsung Galaxy S22", "prezzo_netto": 18.5, "fornitore": "Sifar", "tipologia": "batteria", "marca": "samsung"},
        ]
        r = requests.post(f"{API}/listino", headers=admin_headers, json=righe, timeout=30)
        assert r.status_code == 200, r.text[:400]
        assert r.json().get("salvate") == 2

        # Search
        g = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "TEST_ display"}, timeout=30)
        assert g.status_code == 200
        results = g.json()
        assert any("TEST_DISP01" == row.get("codice") for row in results), f"got {results}"

        # Cleanup: get all TEST_ rows and delete
        all_test = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "TEST_"}, timeout=30).json()
        for row in all_test:
            if row.get("descrizione", "").startswith("TEST_"):
                requests.delete(f"{API}/listino/{row['id']}", headers=admin_headers, timeout=30)
        # Verify gone
        after = requests.get(f"{API}/listino", headers=admin_headers, params={"q": "TEST_"}, timeout=30).json()
        assert not any(r.get("descrizione", "").startswith("TEST_") for r in after)

    def test_listino_post_not_admin_403(self, michael_headers):
        r = requests.post(f"{API}/listino", headers=michael_headers,
                          json=[{"descrizione": "TEST_x", "prezzo_netto": 1.0}], timeout=30)
        assert r.status_code == 403


# ---------- Bolla ritiro PDF ----------
class TestBollaRitiroPDF:
    def test_bolla_pdf_contains_sections(self, admin_headers):
        # Try existing ritiro first
        rits = requests.get(f"{API}/ritiri", headers=admin_headers, timeout=30).json()
        if isinstance(rits, dict):
            rits = rits.get("items") or rits.get("ritiri") or []
        if rits:
            rid = rits[0]["id"]
            pr = requests.get(f"{API}/ritiri/{rid}/pdf", headers=admin_headers, timeout=60)
            assert pr.status_code == 200
            content = pr.content
        else:
            # No ritiri in DB — call _build_bolla_pdf directly with a sample dict
            import sys
            sys.path.insert(0, "/app/backend")
            from server import _build_bolla_pdf
            content = _build_bolla_pdf({
                "numero": "RIT-TEST-001", "data_ritiro": "2026-01-01",
                "nome": "Mario", "cognome": "Rossi", "codice_fiscale": "RSSMRA80A01H501U",
                "numero_documento": "AB1234567",
                "marca": "Apple", "modello": "iPhone 13",
                "imei": "353000000000001", "prezzo_ritiro": 100.0, "n_allegati": 2,
            })
        assert content[:4] == b"%PDF"
        import pymupdf
        doc = pymupdf.open("pdf", content)
        text = "\n".join(p.get_text() for p in doc).upper()
        for kw in ("DATI CLIENTE", "ARTICOLO RITIRATO", "FIRMA CLIENTE", "PREZZO RITIRO"):
            assert kw in text, f"Missing '{kw}' in PDF text"
