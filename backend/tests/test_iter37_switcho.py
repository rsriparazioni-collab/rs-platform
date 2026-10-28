# Iteration 37: Switcho integration (incolla, webhook inbox, segnalazioni actions, config, attachment tipo)
import os
import io
import uuid
import pytest
import pyotp
import requests
from pymongo import MongoClient
from dotenv import dotenv_values

FE = dotenv_values("/app/frontend/.env")
BE = dotenv_values("/app/backend/.env")
BASE_URL = FE["REACT_APP_BACKEND_URL"].rstrip("/")
SECRET = BE["WEBHOOK_CRON_SECRET"]
TOTP = "ZNL4MQSH7OUEIOECQ6TI346P6NWNPNPV"
STORE_ID = "348642fd-364f-48ab-897b-83c6236b061f"  # Morbegno
db = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
STATE = {}


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    r = ses.post(f"{BASE_URL}/api/auth/login", json={"email": "rsriparazioni@gmail.com", "password": "EnricoRS@26"})
    assert r.status_code == 200, r.text
    r = ses.post(f"{BASE_URL}/api/auth/login/mfa", json={"mfa_token": r.json()["mfa_token"], "code": pyotp.TOTP(TOTP).now()})
    assert r.status_code == 200, r.text
    assert "gu_token" in ses.cookies
    return ses


def _mk(s, nome, cognome, tel):
    r = s.post(f"{BASE_URL}/api/clients", json={"nome": nome, "cognome": cognome, "gestione": "cambiaora", "tipo_bolletta": "luce",
                                                "lavorazione": "cambiare", "telefono": tel, "venditore_id": STORE_ID})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# Switcho - incolla two paragraphs
def test_incolla_two_messages(s):
    STATE["a"] = _mk(s, "Testa", "Bolletta", "3330000001")
    STATE["b"] = _mk(s, "Testb", "Link", "3330000002")
    testo = ("per la pratica di Testa Bolletta presso Segnoverde ci serve una bolletta del punto di fornitura\n\n"
             "[14:56, 23/10/2026] +39 329 989 9503: Invitiamo Testb Link a confermare il link ricevuto da Lene. Il cliente ha tempo per firmare entro 48 ore")
    r = s.post(f"{BASE_URL}/api/switcho/incolla", json={"testo": testo})
    assert r.status_code == 200, r.text
    d = r.json()
    print("incolla:", d)
    assert d["messaggi"] == 2
    segs = d["segnalazioni"]
    assert len(segs) == 2
    sa = next(x for x in segs if x["client_id"] == STATE["a"])
    sb = next(x for x in segs if x["client_id"] == STATE["b"])
    print("AI flags:", sa["ai"], sb["ai"], sa["confidenza"], sb["confidenza"])
    STATE["seg_a"], STATE["seg_b"] = sa["id"], sb["id"]
    assert sa["categoria"] == "documenti"
    assert sb["categoria"] == "conferma_link"
    ca = db.clients.find_one({"id": STATE["a"]})
    cb = db.clients.find_one({"id": STATE["b"]})
    assert ca["lavorazione"] == "attesa_documenti"
    assert cb["lavorazione"] == "in_attesa_ok"
    assert "WhatsApp al cliente inviato" in sb["azioni"]
    assert cb.get("conferma_link_sent_at")
    assert db.wa_log.find_one({"client_id": STATE["b"], "tipo": "conferma_link"})
    logs = list(db.lavorazioni_log.find({"client_id": {"$in": [STATE["a"], STATE["b"]]}}))
    assert any(l["operatore_name"].startswith("Switcho") for l in logs)


# Switcho - unknown name then abbina
def test_unknown_then_abbina(s):
    r = s.post(f"{BASE_URL}/api/switcho/incolla", json={"testo": "Sollecitiamo Pinco Pallino a confermare il link ricevuto da Lene"})
    assert r.status_code == 200
    seg = r.json()["segnalazioni"][0]
    assert seg["client_id"] is None
    assert "cliente non riconosciuto: da abbinare" in seg["azioni"]
    STATE["seg_u"] = seg["id"]
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{seg['id']}/abbina", json={"client_id": STATE["b"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["client_name"] == "Link Testb"
    assert d["azioni"] != ["cliente non riconosciuto: da abbinare"]
    print("abbina azioni:", d["azioni"])
    g = db.switcho_segnalazioni.find_one({"id": seg["id"]})
    assert g["client_id"] == STATE["b"]


def test_list_segnalazioni(s):
    r = s.get(f"{BASE_URL}/api/switcho/segnalazioni")
    assert r.status_code == 200
    assert all(x["stato"] == "aperta" for x in r.json())
    ids = [x["id"] for x in r.json()]
    assert STATE["seg_a"] in ids
    r2 = s.get(f"{BASE_URL}/api/switcho/segnalazioni?stato=tutte")
    assert r2.status_code == 200 and len(r2.json()) >= len(r.json())


def test_categoria_change(s):
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{STATE['seg_a']}/categoria", json={"categoria": "annullata_firma"})
    assert r.status_code == 200, r.text
    assert r.json()["categoria"] == "annullata_firma"
    assert db.clients.find_one({"id": STATE["a"]})["lavorazione"] == "annullato"
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{STATE['seg_a']}/categoria", json={"categoria": "boh"})
    assert r.status_code == 400


def test_chiudi(s):
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{STATE['seg_a']}/chiudi")
    assert r.status_code == 200
    ids = [x["id"] for x in s.get(f"{BASE_URL}/api/switcho/segnalazioni").json()]
    assert STATE["seg_a"] not in ids
    assert s.post(f"{BASE_URL}/api/switcho/segnalazioni/nonexist/chiudi").status_code == 404


def test_avvisa_cliente(s):
    before = db.wa_log.count_documents({"client_id": STATE["b"], "tipo": "conferma_link"})
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{STATE['seg_b']}/avvisa-cliente")
    assert r.status_code == 200, r.text
    after = db.wa_log.count_documents({"client_id": STATE["b"], "tipo": "conferma_link"})
    assert after == before + 1


def test_rispondi_no_group(s):
    r = s.post(f"{BASE_URL}/api/switcho/segnalazioni/{STATE['seg_b']}/rispondi", json={"testo": "ok"})
    assert r.status_code == 400
    assert "ID gruppo Switcho non configurato" in r.json()["detail"]


def test_config_and_snippet(s):
    r = s.get(f"{BASE_URL}/api/switcho/config")
    assert r.status_code == 200
    c = r.json()
    assert c["mittente"] == "393299899503" and "webhook_url" in c
    body = {k: c[k] for k in ("gruppo_jid", "mittente", "session_risposta", "auto_avviso_cliente", "attivo")}
    r = s.put(f"{BASE_URL}/api/switcho/config", json=body)
    assert r.status_code == 200 and r.json()["mittente"] == "393299899503"
    r = s.get(f"{BASE_URL}/api/switcho/snippet")
    assert r.status_code == 200 and "messages.upsert" in r.json()["codice"]


def test_config_put_non_admin():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "deborah@cambiaora.local", "password": "Deborah2026!"})
    if r.status_code != 200 or not r.json().get("token"):
        pytest.skip(f"operatore login not usable: {r.status_code}")
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    r = requests.put(f"{BASE_URL}/api/switcho/config", json={"mittente": "x"}, headers=h)
    assert r.status_code == 403


def test_webhook_inbox():
    url = f"{BASE_URL}/api/whatsapp/inbox"
    mid = f"TEST_{uuid.uuid4()}"
    STATE["mid"] = mid
    body = {"text": "Sollecitiamo Pinco Pallino a confermare il link", "sender": "393299899503", "group_id": "x@g.us", "message_id": mid}
    assert requests.post(url, json=body).status_code == 401
    r = requests.post(url, json=body, headers={"X-Webhook-Secret": SECRET})
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["segnalazioni"] == 1, r.text
    r = requests.post(url, json=body, headers={"X-Webhook-Secret": SECRET})
    assert r.json()["status"] == "ok" and r.json()["segnalazioni"] == 0
    r = requests.post(url, json={**body, "sender": "391111111111", "message_id": mid + "x"}, headers={"X-Webhook-Secret": SECRET})
    assert r.json()["status"] == "ignorato"


# Attachments tipo
def test_attachment_tipo(s):
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000050001")
    r = s.post(f"{BASE_URL}/api/clients/{STATE['a']}/attachments", files={"file": ("TEST_b.png", io.BytesIO(png), "image/png")}, data={"tipo": "bolletta"})
    assert r.status_code == 200, r.text
    print("attachment response:", r.json())
    r2 = s.post(f"{BASE_URL}/api/clients/{STATE['a']}/attachments", files={"file": ("TEST_b.png", io.BytesIO(png), "image/png")}, data={"tipo": "xxx"})
    assert r2.status_code == 400
    assert r.json().get("tipo") == "bolletta"
