from dotenv import load_dotenv
load_dotenv()

import os
import re
import hmac
import io
import uuid
import hashlib
import ipaddress
import logging
from datetime import datetime, date, timezone, timedelta
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import csv
import bcrypt
import jwt
import httpx
import pandas as pd
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)

SUPPLIERS = [
    "Enel Energia", "Eni Plenitude", "A2A Energia", "Edison Energia", "Hera Comm",
    "Iren Luce e Gas", "E.ON Energia", "Acea Energia", "Engie Italia", "Sorgenia",
    "Illumia", "Alperia", "Estra Energie", "Dolomiti Energia", "Axpo Italia",
    "Green Network Energy", "NeN", "Octopus Energy", "Tate", "Pulsee", "Wekiwi",
    "Repower", "AGSM AIM Energia", "Ascotrade", "Bluenergy Group", "Unogas",
    "Gas Sales", "Vivigas", "Energit", "Egea", "EstEnergy", "Optima Italia",
    "Audax Energia", "Eva Energia", "Nord Energia", "Altri (maggior tutela)"
]

LAVORAZIONI = [
    "cambiare", "non_cambiare", "cambio_effettuato", "in_quotazione",
    "richieste_bollette", "in_attesa_ok", "problema_tecnico", "da_quotare",
    "contattare_cliente", "non_vuole_cambiare", "passa_in_negozio",
    "attesa_documenti", "rinnovato"
]

# ---------------- Auth helpers ----------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

def serialize_user(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
            "store_ids": u.get("store_ids", []), "can_view_all": u.get("can_view_all", False),
            "active": u.get("active", True)}

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Non autenticato")
    try:
        payload = jwt.decode(creds.credentials, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user or not user.get("active", True):
            raise HTTPException(status_code=401, detail="Utente non trovato")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user

def client_scope_filter(user: dict) -> dict:
    if user["role"] == "admin" or user.get("can_view_all"):
        return {}
    return {"venditore_id": {"$in": user.get("store_ids", [])}}

# ---------------- Business logic ----------------

def effective_pagato(pagato: bool, last_payment_date: Optional[str]) -> bool:
    if not pagato:
        return False
    if not last_payment_date:
        return True
    try:
        paid_on = date.fromisoformat(last_payment_date[:10])
    except ValueError:
        return bool(pagato)
    return date.today() < paid_on + relativedelta(months=6)

def compute_dates(c: dict) -> dict:
    dc = c.get("data_contratto")
    if dc:
        try:
            d0 = date.fromisoformat(dc[:10])
            att = d0 + relativedelta(months=2)
            rin = d0 + relativedelta(months=10)
            scad = att + relativedelta(months=12)
            c["data_attivazione"] = att.isoformat()
            c["data_rinnovo"] = rin.isoformat()
            c["data_scadenza"] = scad.isoformat()
            c["giorni_al_rinnovo"] = (rin - date.today()).days
        except ValueError:
            pass
    c["pagato_effettivo"] = effective_pagato(c.get("pagato", False), c.get("last_payment_date"))
    return c

async def build_alerts(user: dict) -> dict:
    scope = client_scope_filter(user)
    clients = await db.clients.find(scope, {"_id": 0}).to_list(5000)
    stores = await db.stores.find({}, {"_id": 0}).to_list(500)
    today = date.today()
    rinnovi, pagamenti_clienti, pagamenti_negozi = [], [], []
    for c in clients:
        compute_dates(c)
        gr = c.get("giorni_al_rinnovo")
        if gr is not None and -30 <= gr <= 45 and c.get("lavorazione") != "rinnovato":
            rinnovi.append({"client_id": c["id"], "nome": c.get("nome", ""), "cognome": c.get("cognome", ""),
                            "data_rinnovo": c["data_rinnovo"], "giorni": gr,
                            "tipo_bolletta": c.get("tipo_bolletta", ""), "lavorazione": c.get("lavorazione", "")})
        if c.get("pagato") and not c.get("pagato_effettivo"):
            pagamenti_clienti.append({"client_id": c["id"], "nome": c.get("nome", ""), "cognome": c.get("cognome", ""),
                                      "last_payment_date": c.get("last_payment_date")})
    for s in stores:
        if s.get("pagato") and not effective_pagato(s.get("pagato", False), s.get("last_payment_date")):
            pagamenti_negozi.append({"store_id": s["id"], "nome": s.get("nome", ""),
                                     "referente": s.get("referente", ""), "last_payment_date": s.get("last_payment_date")})
    rinnovi.sort(key=lambda x: x["giorni"])
    return {"rinnovi": rinnovi, "pagamenti_clienti": pagamenti_clienti, "pagamenti_negozi": pagamenti_negozi}

# ---------------- Email (managed Resend) ----------------

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)

def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []

def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")

async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Optional[str]:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                          headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise HTTPException(status_code=502, detail="Invio email fallito")

async def send_digest_email():
    admin_user = {"role": "admin", "can_view_all": True, "store_ids": []}
    alerts = await build_alerts(admin_user)
    total = len(alerts["rinnovi"]) + len(alerts["pagamenti_clienti"]) + len(alerts["pagamenti_negozi"])
    if total == 0:
        logger.info("Digest: nessun alert, email non inviata")
        return None
    app_url = os.environ.get("FRONTEND_URL", "")
    rows_r = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(r["cognome"])} {escape(r["nome"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(r["tipo_bolletta"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(r["data_rinnovo"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{r["giorni"]} gg</td></tr>'
        for r in alerts["rinnovi"])
    rows_s = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(s["nome"])} ({escape(s["referente"])})</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">Ultimo pagamento: {escape(str(s["last_payment_date"] or "-"))}</td></tr>'
        for s in alerts["pagamenti_negozi"])
    sec_r = (f'<h3 style="color:#0f172a">Rinnovi in scadenza ({len(alerts["rinnovi"])})</h3>'
             f'<table width="100%" style="border-collapse:collapse;font-size:14px">{rows_r}</table>') if alerts["rinnovi"] else ""
    sec_s = (f'<h3 style="color:#0f172a">Negozi da ripagare ({len(alerts["pagamenti_negozi"])})</h3>'
             f'<table width="100%" style="border-collapse:collapse;font-size:14px">{rows_s}</table>') if alerts["pagamenti_negozi"] else ""
    html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
            f'<h2 style="color:#0284c7;margin:0 0 12px">Riepilogo alert giornaliero</h2>'
            f'<p>Ci sono <strong>{total}</strong> elementi che richiedono attenzione.</p>'
            f'{sec_r}{sec_s}'
            f'<p style="margin-top:16px"><a href="{escape(app_url)}">Apri il gestionale</a></p>'
            f'<p style="font-size:12px;color:#888">Inviato da {escape(EMAIL_FROM_NAME)}. Non chiediamo mai password o dati di pagamento via email.</p>'
            f'</td></tr></table>')
    try:
        return await send_email(to=os.environ["ALERT_EMAIL"], subject=f"Alert utenze: {total} elementi da gestire", html=html)
    except Exception as e:
        logger.error(f"Digest email non inviata: {getattr(e, 'detail', str(e))}")
        return None

# ---------------- Auth routes ----------------

class LoginInput(BaseModel):
    email: str
    password: str

@api_router.post("/auth/login")
async def login(input: LoginInput):
    email = input.email.strip().lower()
    identifier = f"login:{email}"
    attempts = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempts and attempts.get("count", 0) >= 5:
        locked_until = attempts.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova tra 15 minuti.")
        await db.login_attempts.delete_one({"identifier": identifier})
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(input.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1},
             "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True)
        raise HTTPException(status_code=401, detail="Email o password non corretti")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account disattivato")
    await db.login_attempts.delete_one({"identifier": identifier})
    return {"token": create_token(user["id"]), "user": serialize_user(user)}

@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return serialize_user(user)

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"status": "ok"}

# ---------------- Users (admin) ----------------

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "negozio"
    store_ids: List[str] = []
    can_view_all: bool = False

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    store_ids: Optional[List[str]] = None
    can_view_all: Optional[bool] = None
    active: Optional[bool] = None
    password: Optional[str] = None

@api_router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users

@api_router.post("/users")
async def create_user(input: UserCreate, admin: dict = Depends(require_admin)):
    email = input.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email già registrata")
    if input.role not in ("admin", "operatore", "negozio"):
        raise HTTPException(status_code=400, detail="Ruolo non valido")
    user = {"id": str(uuid.uuid4()), "name": input.name, "email": email,
            "password_hash": hash_password(input.password), "role": input.role,
            "store_ids": input.store_ids, "can_view_all": input.can_view_all,
            "active": True, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(user)
    return serialize_user(user)

@api_router.patch("/users/{user_id}")
async def update_user(user_id: str, input: UserUpdate, admin: dict = Depends(require_admin)):
    updates = {k: v for k, v in input.model_dump().items() if v is not None}
    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))
    if not updates:
        raise HTTPException(status_code=400, detail="Nessuna modifica")
    res = await db.users.update_one({"id": user_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    return serialize_user(user)

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Non puoi eliminare il tuo account")
    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"status": "ok"}

# ---------------- Stores (venditori/negozi) ----------------

class StoreCreate(BaseModel):
    nome: str
    referente: str = ""
    tipo: str = "negozio"
    note: str = ""

class StoreUpdate(BaseModel):
    nome: Optional[str] = None
    referente: Optional[str] = None
    tipo: Optional[str] = None
    note: Optional[str] = None

@api_router.get("/stores")
async def list_stores(user: dict = Depends(get_current_user)):
    stores = await db.stores.find({}, {"_id": 0}).to_list(500)
    if not (user["role"] == "admin" or user.get("can_view_all")):
        ids = set(user.get("store_ids", []))
        stores = [s for s in stores if s["id"] in ids]
    month_start = date.today().replace(day=1).isoformat()
    for s in stores:
        s["pagato_effettivo"] = effective_pagato(s.get("pagato", False), s.get("last_payment_date"))
        s["totale_clienti"] = await db.clients.count_documents({"venditore_id": s["id"]})
        s["contratti_mese"] = await db.clients.count_documents(
            {"venditore_id": s["id"], "data_contratto": {"$gte": month_start}})
    return stores

@api_router.post("/stores")
async def create_store(input: StoreCreate, admin: dict = Depends(require_admin)):
    store = {"id": str(uuid.uuid4()), "nome": input.nome, "referente": input.referente,
             "tipo": input.tipo, "note": input.note, "pagato": False, "last_payment_date": None,
             "created_at": datetime.now(timezone.utc).isoformat()}
    await db.stores.insert_one(store)
    store.pop("_id", None)
    return store

@api_router.patch("/stores/{store_id}")
async def update_store(store_id: str, input: StoreUpdate, admin: dict = Depends(require_admin)):
    updates = {k: v for k, v in input.model_dump().items() if v is not None}
    res = await db.stores.update_one({"id": store_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Negozio non trovato")
    return await db.stores.find_one({"id": store_id}, {"_id": 0})

@api_router.post("/stores/{store_id}/mark-paid")
async def mark_store_paid(store_id: str, admin: dict = Depends(require_admin)):
    res = await db.stores.update_one({"id": store_id},
        {"$set": {"pagato": True, "last_payment_date": date.today().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Negozio non trovato")
    return {"status": "ok", "last_payment_date": date.today().isoformat()}

# ---------------- Clients (utenze) ----------------

class ClientInput(BaseModel):
    nome: str
    cognome: str
    tipo_cliente: str = "privato"
    codice_fiscale: str = ""
    p_iva: str = ""
    indirizzo: str = ""
    pod: str = ""
    pdr: str = ""
    iban: str = ""
    email: str = ""
    telefono: str = ""
    kw_potenza: Optional[float] = None
    tipo_bolletta: str = "luce"
    fornitore_provenienza: str = ""
    costo_kwh_attuale: Optional[float] = None
    spese_fisse_attuale: Optional[float] = None
    costo_smc_attuale: Optional[float] = None
    data_contratto: Optional[str] = None
    data_verifica: Optional[str] = None
    data_cambio: Optional[str] = None
    tipo_contratto: str = "fisso"
    nuovo_fornitore: str = ""
    costo_kwh_nuovo: Optional[float] = None
    spese_fisse_nuovo: Optional[float] = None
    costo_smc_nuovo: Optional[float] = None
    privacy_firmata: bool = False
    note: str = ""
    lavorazione: str = "da_quotare"
    venditore_id: str = ""
    operatore_id: str = ""

@api_router.get("/clients")
async def list_clients(user: dict = Depends(get_current_user),
                       lavorazione: str = "", tipo_bolletta: str = "",
                       venditore_id: str = "", q: str = ""):
    scope = client_scope_filter(user)
    if lavorazione:
        scope["lavorazione"] = lavorazione
    if tipo_bolletta:
        scope["tipo_bolletta"] = tipo_bolletta
    if venditore_id and (user["role"] == "admin" or user.get("can_view_all")):
        scope["venditore_id"] = venditore_id
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        scope["$or"] = [{"nome": rx}, {"cognome": rx}, {"codice_fiscale": rx},
                        {"pod": rx}, {"pdr": rx}, {"telefono": rx}, {"email": rx}]
    clients = await db.clients.find(scope, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return [compute_dates(c) for c in clients]

@api_router.post("/clients")
async def create_client(input: ClientInput, user: dict = Depends(get_current_user)):
    data = input.model_dump()
    if user["role"] == "negozio" and data["venditore_id"] not in user.get("store_ids", []):
        if user.get("store_ids"):
            data["venditore_id"] = user["store_ids"][0]
    data.update({"id": str(uuid.uuid4()), "pagato": False, "last_payment_date": None,
                 "created_by": user["id"], "created_at": datetime.now(timezone.utc).isoformat(),
                 "updated_at": datetime.now(timezone.utc).isoformat()})
    await db.clients.insert_one(data)
    await log_lavorazione(data, user, data["lavorazione"], "Cliente inserito")
    data.pop("_id", None)
    return compute_dates(data)

@api_router.get("/clients/{client_id}")
async def get_client(client_id: str, user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    scope["id"] = client_id
    c = await db.clients.find_one(scope, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    history = await db.lavorazioni_log.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    c["history"] = history
    return compute_dates(c)

@api_router.patch("/clients/{client_id}")
async def update_client(client_id: str, input: ClientInput, user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    scope["id"] = client_id
    old = await db.clients.find_one(scope, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    data = input.model_dump()
    if user["role"] == "negozio":
        data["venditore_id"] = old.get("venditore_id", "")
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one({"id": client_id}, {"$set": data})
    if data["lavorazione"] != old.get("lavorazione"):
        await log_lavorazione({**old, **data}, user, data["lavorazione"], "Cambio stato lavorazione")
    updated = await db.clients.find_one({"id": client_id}, {"_id": 0})
    return compute_dates(updated)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, admin: dict = Depends(require_admin)):
    res = await db.clients.delete_one({"id": client_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    await db.lavorazioni_log.delete_many({"client_id": client_id})
    return {"status": "ok"}

@api_router.post("/clients/{client_id}/mark-paid")
async def mark_client_paid(client_id: str, user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    scope["id"] = client_id
    res = await db.clients.update_one(scope,
        {"$set": {"pagato": True, "last_payment_date": date.today().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return {"status": "ok", "last_payment_date": date.today().isoformat()}

async def log_lavorazione(client_doc: dict, user: dict, status: str, note: str):
    await db.lavorazioni_log.insert_one({
        "id": str(uuid.uuid4()), "client_id": client_doc["id"],
        "client_name": f"{client_doc.get('cognome', '')} {client_doc.get('nome', '')}".strip(),
        "operatore_id": client_doc.get("operatore_id") or user["id"],
        "operatore_name": user["name"], "status": status, "note": note,
        "created_at": datetime.now(timezone.utc).isoformat()})

# ---------------- Meta, Dashboard, Alerts, Operatori ----------------

@api_router.get("/meta")
async def get_meta(user: dict = Depends(get_current_user)):
    stores = await db.stores.find({}, {"_id": 0}).to_list(500)
    if not (user["role"] == "admin" or user.get("can_view_all")):
        ids = set(user.get("store_ids", []))
        stores = [s for s in stores if s["id"] in ids]
    operators = await db.users.find({"role": {"$in": ["operatore", "admin"]}, "active": True},
                                    {"_id": 0, "password_hash": 0}).to_list(200)
    return {"suppliers": SUPPLIERS, "lavorazioni": LAVORAZIONI,
            "stores": [{"id": s["id"], "nome": s["nome"], "referente": s.get("referente", "")} for s in stores],
            "operators": [{"id": o["id"], "name": o["name"]} for o in operators]}

@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    clients = await db.clients.find(scope, {"_id": 0}).to_list(5000)
    month_start = date.today().replace(day=1).isoformat()
    stats = {"totale_clienti": len(clients), "luce": 0, "gas": 0,
             "contratti_mese": 0, "rinnovi_30gg": 0, "non_pagati": 0,
             "per_lavorazione": {}, "per_negozio_mese": {}}
    for c in clients:
        compute_dates(c)
        if c.get("tipo_bolletta") == "gas":
            stats["gas"] += 1
        else:
            stats["luce"] += 1
        if (c.get("data_contratto") or "") >= month_start:
            stats["contratti_mese"] += 1
            vid = c.get("venditore_id", "")
            stats["per_negozio_mese"][vid] = stats["per_negozio_mese"].get(vid, 0) + 1
        gr = c.get("giorni_al_rinnovo")
        if gr is not None and 0 <= gr <= 30 and c.get("lavorazione") != "rinnovato":
            stats["rinnovi_30gg"] += 1
        if not c.get("pagato_effettivo"):
            stats["non_pagati"] += 1
        lav = c.get("lavorazione", "da_quotare")
        stats["per_lavorazione"][lav] = stats["per_lavorazione"].get(lav, 0) + 1
    return stats

@api_router.get("/alerts")
async def get_alerts(user: dict = Depends(get_current_user)):
    return await build_alerts(user)

@api_router.post("/alerts/send-digest")
async def send_digest_now(admin: dict = Depends(require_admin)):
    email_id = await send_digest_email()
    if email_id is None:
        return {"status": "ok", "message": "Nessun alert attivo, email non inviata"}
    return {"status": "ok", "email_id": email_id}

@api_router.get("/operators/stats")
async def operators_stats(user: dict = Depends(get_current_user)):
    if user["role"] == "negozio":
        raise HTTPException(status_code=403, detail="Accesso non consentito")
    operators = await db.users.find({"role": {"$in": ["operatore", "admin"]}},
                                    {"_id": 0, "password_hash": 0}).to_list(200)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0).isoformat()
    result = []
    for op in operators:
        logs = await db.lavorazioni_log.find(
            {"operatore_id": op["id"], "created_at": {"$gte": month_start}}, {"_id": 0}).to_list(5000)
        per_status = {}
        for l in logs:
            per_status[l["status"]] = per_status.get(l["status"], 0) + 1
        tot_clients = await db.clients.count_documents({"operatore_id": op["id"]})
        result.append({"id": op["id"], "name": op["name"], "role": op["role"],
                       "lavorazioni_mese": len(logs), "per_status": per_status,
                       "clienti_gestiti": tot_clients,
                       "chiusi_mese": per_status.get("cambio_effettuato", 0) + per_status.get("rinnovato", 0)})
    return result

# ---------------- Import Google Sheet ----------------

HEADER_MAP = {
    "nome": "nome", "cognome": "cognome", "ragione sociale": "cognome",
    "codice fiscale": "codice_fiscale", "cf": "codice_fiscale",
    "p iva": "p_iva", "piva": "p_iva", "partita iva": "p_iva",
    "indirizzo": "indirizzo", "pod": "pod", "pdr": "pdr", "iban": "iban",
    "mail": "email", "email": "email", "e mail": "email",
    "telefono": "telefono", "tel": "telefono", "cellulare": "telefono",
    "kw": "kw_potenza", "potenza": "kw_potenza", "potenza kw": "kw_potenza", "potenza luce": "kw_potenza",
    "tipo bolletta": "tipo_bolletta", "tipo": "tipo_bolletta", "bolletta": "tipo_bolletta",
    "fornitore": "fornitore_provenienza", "fornitore di provenienza": "fornitore_provenienza",
    "fornitore attuale": "fornitore_provenienza",
    "costo al kw": "costo_kwh_attuale", "costo kwh": "costo_kwh_attuale",
    "costo al kwh": "costo_kwh_attuale", "prezzo kwh": "costo_kwh_attuale",
    "spese fisse": "spese_fisse_attuale", "spese fisse attuali": "spese_fisse_attuale",
    "costo smc": "costo_smc_attuale", "costo al smc": "costo_smc_attuale", "prezzo smc": "costo_smc_attuale",
    "data contratto": "data_contratto", "data di contratto": "data_contratto",
    "data verifica": "data_verifica", "data di verifica": "data_verifica",
    "data cambio": "data_cambio", "data di cambio": "data_cambio",
    "tipo contratto": "tipo_contratto", "fisso o variabile": "tipo_contratto",
    "nuovo fornitore": "nuovo_fornitore", "fornitore nuovo": "nuovo_fornitore",
    "costo kwh nuovo": "costo_kwh_nuovo", "nuovo costo kwh": "costo_kwh_nuovo", "nuovo costo al kw": "costo_kwh_nuovo",
    "spese fisse nuovo": "spese_fisse_nuovo", "nuove spese fisse": "spese_fisse_nuovo",
    "costo smc nuovo": "costo_smc_nuovo", "nuovo costo smc": "costo_smc_nuovo",
    "privacy": "privacy_firmata", "privacy firmata": "privacy_firmata",
    "pagato": "pagato", "note": "note",
    "lavorazione": "lavorazione", "stato": "lavorazione", "tipologia lavorazione": "lavorazione",
}

LAV_BY_LABEL = {
    "cambiare": "cambiare", "da cambiare": "cambiare",
    "non cambiare": "non_cambiare", "cambio effettuato": "cambio_effettuato",
    "in quotazione": "in_quotazione", "richieste bollette": "richieste_bollette",
    "richieste le bollette": "richieste_bollette", "in attesa ok": "in_attesa_ok",
    "in attesa ok cliente": "in_attesa_ok", "problema tecnico": "problema_tecnico",
    "da quotare": "da_quotare", "contattare cliente": "contattare_cliente",
    "non vuole cambiare": "non_vuole_cambiare", "passa in negozio": "passa_in_negozio",
    "attesa documenti": "attesa_documenti", "rinnovato": "rinnovato",
    "chieste le bollette": "richieste_bollette", "in attesa di ok del cliente": "in_attesa_ok",
    "attesa ok cliente": "in_attesa_ok", "in attesa di ok cliente": "in_attesa_ok",
}
LAV_BY_LABEL.update({l.replace("_", " "): l for l in LAVORAZIONI})

def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[._/\\-]", " ", str(h)).strip().lower())

def _parse_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    try:
        return float(re.sub(r"[^\d,.\-]", "", str(v)).replace(",", "."))
    except ValueError:
        return None

def _parse_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    try:
        return pd.to_datetime(str(v).strip(), dayfirst=True).date().isoformat()
    except Exception:
        return None

def _parse_bool(v) -> bool:
    return str(v).strip().lower() in ("si", "sì", "yes", "true", "1", "x", "ok", "pagato", "firmata")

def _norm_lavorazione(v) -> str:
    return LAV_BY_LABEL.get(str(v).strip().lower(), "da_quotare")

def _parse_date_flex(v):
    v = str(v).strip()
    if not v:
        return None
    if re.fullmatch(r"\d{5}", v):
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", v)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    return _parse_date(v)

def _parse_gestionale_csv(text: str, store_id: str, admin: dict):
    rows = list(csv.reader(io.StringIO(text)))
    hdr_i = None
    for i, r in enumerate(rows[:10]):
        if any(re.sub(r"[^a-z0-9 ]", "", str(c).lower()).strip() == "nome cognome" for c in r):
            hdr_i = i
            break
    if hdr_i is None:
        return None, "Intestazioni 'nome cognome' non trovate"
    now = datetime.now(timezone.utc).isoformat()
    docs, skipped = [], 0
    for r in rows[hdr_i + 1:]:
        starts = []
        for j, c in enumerate(r):
            c = str(c).strip()
            if re.fullmatch(r"\d{1,4}", c) and j + 1 < len(r) and str(r[j + 1]).strip():
                window = [str(x).strip().upper() for x in r[j:j + 12]]
                if "LUCE" in window or "GAS" in window:
                    starts.append(j)
        if not starts:
            skipped += 1
        for s in starts:
            b = [str(x).strip() for x in r[s:s + 22]] + [""] * max(0, 22 - len(r[s:s + 22]))
            servizio = b[10].upper()
            if servizio not in ("LUCE", "GAS"):
                skipped += 1
                continue
            toks = b[1].split()
            if not toks:
                skipped += 1
                continue
            tar = [float(n.replace(",", ".")) for n in re.findall(r"\d+[.,]\d+|\d+", b[16])]
            prezzo_n, fisse_n = None, None
            if len(tar) == 2:
                prezzo_n, fisse_n = tar
            elif len(tar) == 1 and tar[0] < 5:
                prezzo_n = tar[0]
            note = b[20]
            if b[16] and len(tar) > 2:
                note = (note + " | Tariffa nuova: " + b[16]).strip(" |")
            lav_raw = b[21].strip().lower()
            lav = _norm_lavorazione(lav_raw)
            if lav_raw and lav == "da_quotare" and lav_raw != "da quotare":
                note = (note + " | Stato foglio: " + b[21]).strip(" |")
            if b[19].strip().lower() == "annullato":
                note = (note + " | Pagamento: annullato").strip(" |")
            pagato = _parse_bool(b[19])
            is_gas = servizio == "GAS"
            docs.append({
                "id": str(uuid.uuid4()),
                "nome": toks[0], "cognome": " ".join(toks[1:]),
                "tipo_cliente": "business" if b[3] else "privato",
                "codice_fiscale": b[2].upper(), "p_iva": b[3], "indirizzo": b[4],
                "pod": "" if is_gas else b[5].upper(), "pdr": b[5] if is_gas else "",
                "iban": b[6].upper(), "email": b[7], "telefono": b[8],
                "kw_potenza": _parse_float(b[9]),
                "tipo_bolletta": "gas" if is_gas else "luce",
                "fornitore_provenienza": b[11],
                "costo_kwh_attuale": None, "spese_fisse_attuale": None, "costo_smc_attuale": None,
                "data_contratto": _parse_date_flex(b[14]),
                "data_verifica": _parse_date_flex(b[12]),
                "data_cambio": _parse_date_flex(b[13]),
                "tipo_contratto": "variabile" if "var" in b[15].lower() else "fisso",
                "nuovo_fornitore": b[17],
                "costo_kwh_nuovo": None if is_gas else prezzo_n,
                "spese_fisse_nuovo": fisse_n,
                "costo_smc_nuovo": prezzo_n if is_gas else None,
                "privacy_firmata": False,
                "note": note,
                "lavorazione": lav,
                "venditore_id": store_id, "operatore_id": "",
                "pagato": pagato,
                "last_payment_date": date.today().isoformat() if pagato else None,
                "created_by": admin["id"], "created_at": now, "updated_at": now,
            })
    if not docs:
        return None, "Nessun cliente riconosciuto nel formato gestionale"
    return (docs, skipped), None

def _parse_any_csv(text: str, store_id: str, admin: dict):
    head = text[:2000].lower()
    if "nome cognome" in head and "servizio" in head:
        return _parse_gestionale_csv(text, store_id, admin)
    return _parse_sheet_csv(text, store_id, admin)

def _parse_sheet_csv(text: str, store_id: str, admin: dict):
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str)
    except Exception:
        return None, "Formato del foglio non leggibile"
    col_map = {}
    for col in df.columns:
        field = HEADER_MAP.get(_norm_header(col))
        if field and field not in col_map.values():
            col_map[col] = field
    if "nome" not in col_map.values() and "cognome" not in col_map.values():
        return None, f"Colonne 'nome'/'cognome' non trovate. Intestazioni lette: {', '.join(str(c) for c in df.columns[:15])}"
    now = datetime.now(timezone.utc).isoformat()
    docs, skipped = [], 0
    for _, row in df.iterrows():
        data = {field: (row[col] if pd.notna(row[col]) else "") for col, field in col_map.items()}
        nome = str(data.get("nome", "")).strip()
        cognome = str(data.get("cognome", "")).strip()
        if not nome and not cognome:
            skipped += 1
            continue
        tb = str(data.get("tipo_bolletta", "")).strip().lower()
        tc = str(data.get("tipo_contratto", "")).strip().lower()
        pagato = _parse_bool(data.get("pagato", ""))
        docs.append({
            "id": str(uuid.uuid4()),
            "nome": nome, "cognome": cognome,
            "tipo_cliente": "business" if str(data.get("p_iva", "")).strip() else "privato",
            "codice_fiscale": str(data.get("codice_fiscale", "")).strip().upper(),
            "p_iva": str(data.get("p_iva", "")).strip(),
            "indirizzo": str(data.get("indirizzo", "")).strip(),
            "pod": str(data.get("pod", "")).strip().upper(),
            "pdr": str(data.get("pdr", "")).strip(),
            "iban": str(data.get("iban", "")).strip().upper(),
            "email": str(data.get("email", "")).strip(),
            "telefono": str(data.get("telefono", "")).strip(),
            "kw_potenza": _parse_float(data.get("kw_potenza")),
            "tipo_bolletta": "gas" if "gas" in tb else "luce",
            "fornitore_provenienza": str(data.get("fornitore_provenienza", "")).strip(),
            "costo_kwh_attuale": _parse_float(data.get("costo_kwh_attuale")),
            "spese_fisse_attuale": _parse_float(data.get("spese_fisse_attuale")),
            "costo_smc_attuale": _parse_float(data.get("costo_smc_attuale")),
            "data_contratto": _parse_date(data.get("data_contratto")),
            "data_verifica": _parse_date(data.get("data_verifica")),
            "data_cambio": _parse_date(data.get("data_cambio")),
            "tipo_contratto": "variabile" if "var" in tc else "fisso",
            "nuovo_fornitore": str(data.get("nuovo_fornitore", "")).strip(),
            "costo_kwh_nuovo": _parse_float(data.get("costo_kwh_nuovo")),
            "spese_fisse_nuovo": _parse_float(data.get("spese_fisse_nuovo")),
            "costo_smc_nuovo": _parse_float(data.get("costo_smc_nuovo")),
            "privacy_firmata": _parse_bool(data.get("privacy_firmata", "")),
            "note": str(data.get("note", "")).strip(),
            "lavorazione": _norm_lavorazione(data.get("lavorazione", "")),
            "venditore_id": store_id, "operatore_id": "",
            "pagato": pagato,
            "last_payment_date": date.today().isoformat() if pagato else None,
            "created_by": admin["id"], "created_at": now, "updated_at": now,
        })
    return (docs, skipped), None

async def _insert_imported(docs: list, admin: dict):
    now = datetime.now(timezone.utc).isoformat()
    await db.clients.insert_many(docs)
    await db.lavorazioni_log.insert_many([
        {"id": str(uuid.uuid4()), "client_id": d["id"], "client_name": f"{d['cognome']} {d['nome']}".strip(),
         "operatore_id": admin["id"], "operatore_name": admin["name"],
         "status": d["lavorazione"], "note": "Importato da Google Sheet", "created_at": now}
        for d in docs])

class SheetImportInput(BaseModel):
    sheet_url: str
    store_id: str = ""
    all_tabs: bool = False
    sheet_name: str = ""

@api_router.post("/import/google-sheet")
async def import_google_sheet(input: SheetImportInput, admin: dict = Depends(require_admin)):
    m = re.search(r"/d/([a-zA-Z0-9\-_]+)", input.sheet_url)
    if not m:
        raise HTTPException(status_code=400, detail="Link Google Sheet non valido")
    sheet_id = m.group(1)
    gid_m = re.search(r"gid=(\d+)", input.sheet_url)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http_client:
        if input.all_tabs:
            stores = await db.stores.find({}, {"_id": 0}).to_list(500)
            fallback_resp = await http_client.get(
                f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=__non_esiste__")
            if fallback_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Impossibile leggere il foglio. Verifica che sia condiviso: 'Chiunque abbia il link può visualizzare'.")
            fallback_hash = hashlib.sha256(fallback_resp.text.encode()).hexdigest()
            report, total_imported = [], 0
            for s in stores:
                r = await http_client.get(
                    f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={s['nome']}")
                if r.status_code != 200 or hashlib.sha256(r.text.encode()).hexdigest() == fallback_hash:
                    report.append({"store": s["nome"], "status": "pagina_non_trovata", "imported": 0})
                    continue
                parsed, err = _parse_any_csv(r.text, s["id"], admin)
                if err:
                    report.append({"store": s["nome"], "status": "errore", "detail": err, "imported": 0})
                    continue
                docs, skipped = parsed
                if docs:
                    await _insert_imported(docs, admin)
                total_imported += len(docs)
                report.append({"store": s["nome"], "status": "ok", "imported": len(docs), "skipped": skipped})
            return {"mode": "all_tabs", "total_imported": total_imported, "report": report,
                    "hint": "Le pagine segnate come non trovate devono avere lo stesso nome del negozio, oppure importale singolarmente dal link della pagina (contiene gid)."}

        if input.sheet_name:
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={input.sheet_name}"
        else:
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_m.group(1) if gid_m else '0'}"
        resp = await http_client.get(csv_url)
    if resp.status_code != 200 or ("text/csv" not in resp.headers.get("content-type", "") and "text/plain" not in resp.headers.get("content-type", "")):
        raise HTTPException(status_code=400, detail="Impossibile leggere il foglio. Verifica che sia condiviso: 'Chiunque abbia il link può visualizzare'.")
    parsed, err = _parse_any_csv(resp.text, input.store_id, admin)
    if err:
        raise HTTPException(status_code=400, detail=err)
    docs, skipped = parsed
    if docs:
        await _insert_imported(docs, admin)
    return {"imported": len(docs), "skipped": skipped}

# ---------------- Cron ----------------

@api_router.post("/cron/daily-digest")
async def cron_daily_digest(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not token or not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(send_digest_email)
    return {"status": "accepted"}

@api_router.get("/")
async def root():
    return {"message": "Gestionale Utenze API"}

# ---------------- Seed ----------------

SEED_STORES = [
    {"nome": "Tirano", "referente": "Michael", "tipo": "negozio"},
    {"nome": "Sondalo", "referente": "Lorenzo", "tipo": "negozio"},
    {"nome": "Sondrio", "referente": "Michael", "tipo": "negozio"},
    {"nome": "Sondrio Grosio", "referente": "Michael", "tipo": "negozio"},
    {"nome": "Deriu", "referente": "Deriu", "tipo": "negozio"},
    {"nome": "Gravedona", "referente": "Kevin", "tipo": "negozio"},
    {"nome": "Devis (Freelance)", "referente": "Devis", "tipo": "freelance"},
]

SEED_USERS = [
    {"name": "Deborah", "email": "deborah@cambiaora.local", "password": "Deborah2026!",
     "role": "operatore", "can_view_all": True, "stores": []},
    {"name": "Michael", "email": "michael@cambiaora.local", "password": "Michael2026!",
     "role": "negozio", "can_view_all": False, "stores": ["Tirano", "Sondrio", "Sondrio Grosio"]},
    {"name": "Lorenzo", "email": "lorenzo@cambiaora.local", "password": "Lorenzo2026!",
     "role": "negozio", "can_view_all": False, "stores": ["Sondalo"]},
    {"name": "Kevin", "email": "kevin@cambiaora.local", "password": "Kevin2026!",
     "role": "negozio", "can_view_all": False, "stores": ["Gravedona"]},
]

async def seed_data():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.clients.create_index("venditore_id")
    await db.clients.create_index("lavorazione")
    await db.lavorazioni_log.create_index("operatore_id")

    admin_email = os.environ["ADMIN_EMAIL"].strip().lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "name": "Devis", "email": admin_email,
                                   "password_hash": hash_password(admin_password), "role": "admin",
                                   "store_ids": [], "can_view_all": True, "active": True,
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_password)}})

    if await db.stores.count_documents({}) == 0:
        for s in SEED_STORES:
            await db.stores.insert_one({"id": str(uuid.uuid4()), **s, "note": "", "pagato": False,
                                        "last_payment_date": None,
                                        "created_at": datetime.now(timezone.utc).isoformat()})

    stores = {s["nome"]: s["id"] for s in await db.stores.find({}, {"_id": 0}).to_list(100)}
    for su in SEED_USERS:
        if not await db.users.find_one({"email": su["email"]}):
            await db.users.insert_one({"id": str(uuid.uuid4()), "name": su["name"], "email": su["email"],
                                       "password_hash": hash_password(su["password"]), "role": su["role"],
                                       "store_ids": [stores[n] for n in su["stores"] if n in stores],
                                       "can_view_all": su["can_view_all"], "active": True,
                                       "created_at": datetime.now(timezone.utc).isoformat()})

    if await db.clients.count_documents({}) == 0:
        deborah = await db.users.find_one({"email": "deborah@cambiaora.local"}, {"_id": 0})
        op_id = deborah["id"] if deborah else ""
        today = date.today()
        samples = [
            ("Mario", "Rossi", "privato", "luce", "Enel Energia", "cambio_effettuato", "Tirano", 10, True, 7),
            ("Giuseppe", "Bianchi", "privato", "gas", "Eni Plenitude", "rinnovato", "Sondalo", 11, True, 2),
            ("Valtellina Eco", "Srl", "business", "luce", "A2A Energia", "in_quotazione", "Tirano", 1, False, None),
            ("Anna", "Verdi", "privato", "luce", "Sorgenia", "richieste_bollette", "Gravedona", 3, False, None),
            ("Luca", "Fontana", "privato", "gas", "Hera Comm", "attesa_documenti", "Sondrio", 9, True, 5),
            ("Bar al Lago", "Sas", "business", "luce", "Illumia", "contattare_cliente", "Gravedona", 0, False, None),
            ("Paola", "Neri", "privato", "gas", "NeN", "da_quotare", "Sondalo", 2, False, None),
            ("Franco", "Colombo", "privato", "luce", "Octopus Energy", "in_attesa_ok", "Deriu", 10, True, 4),
            ("Agriturismo Pizzo", "Srl", "business", "gas", "Dolomiti Energia", "passa_in_negozio", "Sondrio Grosio", 6, False, None),
            ("Sara", "Galli", "privato", "luce", "Tate", "problema_tecnico", "Tirano", 4, False, None),
        ]
        for nome, cognome, tipo_c, bolletta, forn, lav, store_name, mesi_fa, pagato, pag_mesi_fa in samples:
            dc = today - relativedelta(months=mesi_fa)
            doc = {"id": str(uuid.uuid4()), "nome": nome, "cognome": cognome, "tipo_cliente": tipo_c,
                   "codice_fiscale": "RSSMRA80A01F205X" if tipo_c == "privato" else "",
                   "p_iva": "01234567890" if tipo_c == "business" else "",
                   "indirizzo": "Via Roma 1, 23100 Sondrio", "pod": "IT001E12345678" if bolletta == "luce" else "",
                   "pdr": "12345678901234" if bolletta == "gas" else "", "iban": "IT60X0542811101000000123456",
                   "email": f"{nome.lower().replace(' ', '')}@esempio.it", "telefono": "3331234567",
                   "kw_potenza": 3.0 if bolletta == "luce" else None, "tipo_bolletta": bolletta,
                   "fornitore_provenienza": forn,
                   "costo_kwh_attuale": 0.32 if bolletta == "luce" else None,
                   "spese_fisse_attuale": 10.0,
                   "costo_smc_attuale": 1.15 if bolletta == "gas" else None,
                   "data_contratto": dc.isoformat(), "data_verifica": None, "data_cambio": None,
                   "tipo_contratto": "fisso", "nuovo_fornitore": "Sorgenia",
                   "costo_kwh_nuovo": 0.24 if bolletta == "luce" else None, "spese_fisse_nuovo": 8.0,
                   "costo_smc_nuovo": 0.89 if bolletta == "gas" else None,
                   "privacy_firmata": True, "note": "", "lavorazione": lav,
                   "venditore_id": stores.get(store_name, ""), "operatore_id": op_id,
                   "pagato": pagato,
                   "last_payment_date": (today - relativedelta(months=pag_mesi_fa)).isoformat() if pag_mesi_fa is not None else None,
                   "created_by": op_id, "created_at": datetime.now(timezone.utc).isoformat(),
                   "updated_at": datetime.now(timezone.utc).isoformat()}
            await db.clients.insert_one(doc)
            await db.lavorazioni_log.insert_one({
                "id": str(uuid.uuid4()), "client_id": doc["id"],
                "client_name": f"{cognome} {nome}", "operatore_id": op_id,
                "operatore_name": "Deborah", "status": lav, "note": "Cliente inserito",
                "created_at": datetime.now(timezone.utc).isoformat()})

@app.on_event("startup")
async def startup():
    await seed_data()

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
