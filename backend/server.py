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
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse, Response
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
            "active": u.get("active", True),
            "sections": u.get("sections") or ["energia", "riparazioni", "telefonia"]}

async def get_current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = request.cookies.get("gu_token") or (creds.credentials if creds else None)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
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
    paid_on = None
    try:
        paid_on = date.fromisoformat(last_payment_date[:10])
    except ValueError:
        return True
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
    projection = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "data_contratto": 1,
                  "lavorazione": 1, "tipo_bolletta": 1, "pagato": 1, "last_payment_date": 1}
    clients = await db.clients.find(scope, projection).to_list(5000)
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
    mscope = magazzino_scope(user)
    mscope["quantita"] = {"$lte": 2}
    low = await db.magazzino.find(mscope, {"_id": 0, "id": 1, "nome": 1, "categoria": 1, "quantita": 1, "store_id": 1}).to_list(500)
    smap = {s["id"]: s.get("nome", "") for s in stores}
    sotto_scorta = [{"id": i["id"], "nome": i["nome"], "categoria": i.get("categoria", ""),
                     "quantita": i.get("quantita", 0), "store_name": smap.get(i.get("store_id", ""), "-")} for i in low]
    return {"rinnovi": rinnovi, "pagamenti_clienti": pagamenti_clienti, "pagamenti_negozi": pagamenti_negozi,
            "sotto_scorta": sotto_scorta}

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
    from fastapi.responses import JSONResponse
    token = create_token(user["id"])
    resp = JSONResponse({"token": token, "user": serialize_user(user)})
    resp.set_cookie("gu_token", token, httponly=True, secure=True, samesite="lax", max_age=86400)
    return resp

@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return serialize_user(user)

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("gu_token")
    return resp

# ---------------- Users (admin) ----------------

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "negozio"
    store_ids: List[str] = []
    can_view_all: bool = False
    sections: List[str] = []

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    store_ids: Optional[List[str]] = None
    can_view_all: Optional[bool] = None
    active: Optional[bool] = None
    password: Optional[str] = None
    sections: Optional[List[str]] = None

@api_router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users

@api_router.post("/users")
async def create_user(input: UserCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        # Non-admin: solo account negozio, senza vista globale, limitati ai propri negozi
        if input.role != "negozio":
            raise HTTPException(status_code=403, detail="Puoi creare solo utenti di tipo Negozio")
        input.can_view_all = False
        own = user.get("store_ids", [])
        input.store_ids = [s for s in input.store_ids if s in own] or own[:1]
        caller_sections = user.get("sections") or ["energia", "riparazioni", "telefonia"]
        input.sections = [s for s in input.sections if s in caller_sections] or caller_sections
    email = input.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email già registrata")
    if input.role not in ("admin", "operatore", "negozio", "tecnico"):
        raise HTTPException(status_code=400, detail="Ruolo non valido")
    user = {"id": str(uuid.uuid4()), "name": input.name, "email": email,
            "password_hash": hash_password(input.password), "role": input.role,
            "store_ids": input.store_ids, "can_view_all": input.can_view_all,
            "sections": input.sections or ["energia", "riparazioni", "telefonia"],
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
    review_link: str = ""

class StoreUpdate(BaseModel):
    nome: Optional[str] = None
    referente: Optional[str] = None
    tipo: Optional[str] = None
    note: Optional[str] = None
    review_link: Optional[str] = None

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
             "tipo": input.tipo, "note": input.note, "review_link": input.review_link,
             "pagato": False, "last_payment_date": None,
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
    provincia: str = ""
    venditore_pagato: bool = False

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
    proj = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "tipo_cliente": 1, "p_iva": 1,
            "telefono": 1, "email": 1, "codice_fiscale": 1, "pod": 1, "pdr": 1,
            "tipo_bolletta": 1, "fornitore_provenienza": 1, "lavorazione": 1,
            "data_contratto": 1, "venditore_id": 1, "pagato": 1, "last_payment_date": 1,
            "privacy_firmata": 1, "created_at": 1}
    clients = await db.clients.find(scope, proj).sort("created_at", -1).to_list(5000)
    tipi_per_client = {}
    async for row in db.servizi.aggregate([{"$group": {"_id": "$client_id", "tipi": {"$addToSet": "$tipo"}}}]):
        tipi_per_client[row["_id"]] = row["tipi"]
    out = []
    for c in clients:
        compute_dates(c)
        tipi = set(tipi_per_client.get(c["id"], []))
        cats = set()
        if c.get("data_contratto"):
            cats.add("energia")
        if tipi & {"sim", "internet", "fisso"}:
            cats.add("telefonia")
        if tipi & {"riparazione", "accessori", "vendita"}:
            cats.add("riparazioni")
        c["premium_step"] = len(cats)
        out.append(c)
    return out

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
    tipi = {s["tipo"] async for s in db.servizi.find({"client_id": client_id}, {"_id": 0, "tipo": 1})}
    cats = set()
    if c.get("data_contratto"):
        cats.add("energia")
    if tipi & {"sim", "internet", "fisso"}:
        cats.add("telefonia")
    if tipi & {"riparazione", "accessori", "vendita"}:
        cats.add("riparazioni")
    c["premium_step"] = len(cats)
    return compute_dates(c)

@api_router.patch("/clients/{client_id}")
async def update_client(client_id: str, input: ClientInput, user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    scope["id"] = client_id
    old = await db.clients.find_one(scope, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    data = input.model_dump(exclude_unset=True)
    if user["role"] == "negozio":
        data.pop("venditore_id", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one({"id": client_id}, {"$set": data})
    if data.get("lavorazione") and data["lavorazione"] != old.get("lavorazione"):
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

# ---------------- Venditori ----------------

class VenditoreInput(BaseModel):
    nome: str
    store_id: str = ""
    tipo: str = "interno"
    attivo: bool = True

@api_router.get("/venditori")
async def list_venditori(user: dict = Depends(get_current_user)):
    venditori = await db.venditori.find({}, {"_id": 0}).sort("nome", 1).to_list(200)
    store_ids = [v["store_id"] for v in venditori if v.get("store_id")]
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(100)
    smap = {s["id"]: s["nome"] for s in stores}
    for v in venditori:
        v["store_name"] = smap.get(v.get("store_id", ""), "Esterno")
        v["vendite"] = await db.clients.count_documents({"operatore_id": v["id"]})
        v["da_pagare"] = await db.clients.count_documents({"operatore_id": v["id"], "venditore_pagato": {"$ne": True}})
    return venditori

@api_router.post("/venditori")
async def create_venditore(input: VenditoreInput, admin: dict = Depends(require_admin)):
    data = input.model_dump()
    data.update({"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()})
    await db.venditori.insert_one(data)
    data.pop("_id", None)
    return data

@api_router.patch("/venditori/{venditore_id}")
async def update_venditore(venditore_id: str, input: VenditoreInput, admin: dict = Depends(require_admin)):
    res = await db.venditori.update_one({"id": venditore_id}, {"$set": input.model_dump(exclude_unset=True)})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Venditore non trovato")
    return await db.venditori.find_one({"id": venditore_id}, {"_id": 0})

@api_router.delete("/venditori/{venditore_id}")
async def delete_venditore(venditore_id: str, admin: dict = Depends(require_admin)):
    res = await db.venditori.delete_one({"id": venditore_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Venditore non trovato")
    return {"status": "ok"}

@api_router.get("/venditori/{venditore_id}/vendite")
async def vendite_venditore(venditore_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "operatore") and not user.get("can_view_all"):
        raise HTTPException(status_code=403, detail="Non autorizzato")
    clients = await db.clients.find({"operatore_id": venditore_id},
        {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "data_contratto": 1, "lavorazione": 1,
         "venditore_pagato": 1, "venditore_id": 1, "created_at": 1}).sort("created_at", -1).to_list(2000)
    store_ids = list({c.get("venditore_id") for c in clients if c.get("venditore_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(100)
    smap = {s["id"]: s["nome"] for s in stores}
    for c in clients:
        c["store_name"] = smap.get(c.get("venditore_id", ""), "-")
        c.pop("venditore_id", None)
    return clients

@api_router.post("/clients/{client_id}/venditore-pagato")
async def toggle_venditore_pagato(client_id: str, user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    scope["id"] = client_id
    c = await db.clients.find_one(scope, {"_id": 0, "venditore_pagato": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    new_val = not c.get("venditore_pagato", False)
    await db.clients.update_one({"id": client_id}, {"$set": {"venditore_pagato": new_val}})
    return {"venditore_pagato": new_val}


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
            "tel_operators": {"sim": SIM_OPERATORS, "internet": INTERNET_OPERATORS, "fisso": FISSO_OPERATORS},
            "rip_stati": RIP_STATI, "servizio_tipi": SERVIZIO_TIPI,
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
    svc_scope = servizio_scope(user)
    stats["servizi_attivi"] = await db.servizi.count_documents(
        {**svc_scope, "stato": {"$nin": ["consegnato", "non_riparabile"]}})
    vinc = await db.servizi.find({**svc_scope, "vincolo_mesi": {"$nin": [None, 0]},
                                  "data_attivazione": {"$ne": None}},
                                 {"_id": 0, "data_attivazione": 1, "vincolo_mesi": 1}).to_list(5000)
    stats["vincoli_60gg"] = 0
    for v in vinc:
        try:
            scad = date.fromisoformat(str(v["data_attivazione"])[:10]) + relativedelta(months=int(v["vincolo_mesi"]))
            if 0 <= (scad - date.today()).days <= 60:
                stats["vincoli_60gg"] += 1
        except (ValueError, TypeError):
            pass
    return stats

@api_router.get("/alerts")
async def get_alerts(user: dict = Depends(get_current_user)):
    return await build_alerts(user)

@api_router.get("/scadenze-settimana")
async def scadenze_settimana(user: dict = Depends(get_current_user)):
    sections = user_sections(user)
    out = {"rinnovi": [], "vincoli": [], "riparazioni_pronte": []}
    if "energia" in sections:
        scope = client_scope_filter(user)
        projection = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "data_contratto": 1,
                      "lavorazione": 1, "tipo_bolletta": 1, "pagato": 1, "last_payment_date": 1}
        clients = await db.clients.find(scope, projection).to_list(5000)
        for c in clients:
            compute_dates(c)
            gr = c.get("giorni_al_rinnovo")
            if gr is not None and 0 <= gr <= 7 and c.get("lavorazione") != "rinnovato":
                out["rinnovi"].append({"client_id": c["id"], "nome": c.get("nome", ""), "cognome": c.get("cognome", ""),
                                       "data_rinnovo": c["data_rinnovo"], "giorni": gr,
                                       "tipo_bolletta": c.get("tipo_bolletta", "")})
        out["rinnovi"].sort(key=lambda x: x["giorni"])
    if "telefonia" in sections:
        svc_scope = servizio_scope(user)
        svc_scope.update({"vincolo_mesi": {"$nin": [None, 0]}, "data_attivazione": {"$ne": None}})
        vinc = await db.servizi.find(svc_scope, {"_id": 0}).to_list(5000)
        names = await clients_name_map(list({s["client_id"] for s in vinc}))
        for s in vinc:
            ser = serialize_servizio(s, names.get(s["client_id"], ""))
            g = ser.get("giorni_alla_scadenza")
            if g is not None and 0 <= g <= 7:
                out["vincoli"].append({"id": s["id"], "client_name": ser["client_name"], "tipo": s["tipo"],
                                       "operatore_tel": s.get("operatore_tel", ""), "numero": s.get("numero", ""),
                                       "scadenza_vincolo": ser["scadenza_vincolo"], "giorni": g})
        out["vincoli"].sort(key=lambda x: x["giorni"])
    if "riparazioni" in sections:
        svc_scope = servizio_scope(user)
        svc_scope["tipo"] = "riparazione"
        svc_scope["stato"] = "pronto"
        rips = await db.servizi.find(svc_scope, {"_id": 0, "id": 1, "client_id": 1, "dispositivo": 1,
                                                 "problema": 1, "updated_at": 1}).to_list(1000)
        names = await clients_name_map(list({s["client_id"] for s in rips}))
        out["riparazioni_pronte"] = [
            {"id": s["id"], "client_name": names.get(s["client_id"], ""),
             "dispositivo": s.get("dispositivo", ""), "problema": s.get("problema", "")}
            for s in rips]
    out["totale"] = len(out["rinnovi"]) + len(out["vincoli"]) + len(out["riparazioni_pronte"])
    return out


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
    "venditore": "venditore", "venduto da": "venditore",
}

VENDITORE_ALIASES = {"davis": "devis", "debby": "deborah", "debora": "deborah"}

async def _venditori_name_map():
    m = {}
    async for v in db.venditori.find({"attivo": {"$ne": False}}, {"_id": 0, "id": 1, "nome": 1}):
        nome = str(v.get("nome", "")).strip().lower()
        if nome:
            m[nome] = v["id"]
    return m

def _venditore_match(raw, vend_map: dict, fallback_id: str):
    v = re.sub(r"\s+", " ", str(raw or "").strip().lower())
    if not v:
        return "", False
    pagato = "pagat" in v
    v = re.sub(r"\bpagat[oa]?\b", "", v).strip()
    vid = vend_map.get(v) or vend_map.get(VENDITORE_ALIASES.get(v, "")) or fallback_id
    return vid, pagato

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

def _find_gestionale_blocks(r: list) -> list:
    starts = []
    for j, c in enumerate(r):
        c = str(c).strip()
        if re.fullmatch(r"\d{1,4}", c) and j + 1 < len(r) and str(r[j + 1]).strip():
            window = [str(x).strip().upper() for x in r[j:j + 12]]
            if "LUCE" in window or "GAS" in window:
                starts.append(j)
    return starts

def _gestionale_block_to_doc(b: list, store_id: str, admin: dict, now: str,
                             vend_map: Optional[dict] = None, vend_fallback: str = "") -> Optional[dict]:
    servizio = b[10].upper()
    if servizio not in ("LUCE", "GAS"):
        return None
    toks = b[1].split()
    if not toks:
        return None
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
    op_id, vend_pagato = _venditore_match(b[22], vend_map or {}, vend_fallback)
    is_gas = servizio == "GAS"
    return {
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
        "venditore_id": store_id, "operatore_id": op_id,
        "venditore_pagato": vend_pagato,
        "pagato": pagato,
        "last_payment_date": date.today().isoformat() if pagato else None,
        "created_by": admin["id"], "created_at": now, "updated_at": now,
    }

def _parse_gestionale_csv(text: str, store_id: str, admin: dict,
                          vend_map: Optional[dict] = None, vend_fallback: str = ""):
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
        starts = _find_gestionale_blocks(r)
        if not starts:
            skipped += 1
        for s in starts:
            b = [str(x).strip() for x in r[s:s + 23]] + [""] * max(0, 23 - len(r[s:s + 23]))
            doc = _gestionale_block_to_doc(b, store_id, admin, now, vend_map, vend_fallback)
            if doc:
                docs.append(doc)
            else:
                skipped += 1
    if not docs:
        return None, "Nessun cliente riconosciuto nel formato gestionale"
    return (docs, skipped), None

def _parse_any_csv(text: str, store_id: str, admin: dict,
                   vend_map: Optional[dict] = None, vend_fallback: str = ""):
    head = text[:2000].lower()
    if "nome cognome" in head and "servizio" in head:
        return _parse_gestionale_csv(text, store_id, admin, vend_map, vend_fallback)
    return _parse_sheet_csv(text, store_id, admin, vend_map, vend_fallback)

def _build_col_map(df) -> dict:
    col_map = {}
    for col in df.columns:
        field = HEADER_MAP.get(_norm_header(col))
        if field and field not in col_map.values():
            col_map[col] = field
    return col_map

def _row_to_doc(data: dict, store_id: str, admin: dict, now: str,
                vend_map: Optional[dict] = None, vend_fallback: str = "") -> dict:
    tb = str(data.get("tipo_bolletta", "")).strip().lower()
    tc = str(data.get("tipo_contratto", "")).strip().lower()
    pagato = _parse_bool(data.get("pagato", ""))
    op_id, vend_pagato = _venditore_match(data.get("venditore", ""), vend_map or {}, vend_fallback)
    return {
        "id": str(uuid.uuid4()),
        "nome": str(data.get("nome", "")).strip(), "cognome": str(data.get("cognome", "")).strip(),
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
        "venditore_id": store_id, "operatore_id": op_id,
        "venditore_pagato": vend_pagato,
        "pagato": pagato,
        "last_payment_date": date.today().isoformat() if pagato else None,
        "created_by": admin["id"], "created_at": now, "updated_at": now,
    }

def _parse_sheet_csv(text: str, store_id: str, admin: dict,
                     vend_map: Optional[dict] = None, vend_fallback: str = ""):
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str)
    except Exception:
        return None, "Formato del foglio non leggibile"
    col_map = _build_col_map(df)
    if "nome" not in col_map.values() and "cognome" not in col_map.values():
        return None, f"Colonne 'nome'/'cognome' non trovate. Intestazioni lette: {', '.join(str(c) for c in df.columns[:15])}"
    now = datetime.now(timezone.utc).isoformat()
    docs, skipped = [], 0
    for _, row in df.iterrows():
        data = {field: (row[col] if pd.notna(row[col]) else "") for col, field in col_map.items()}
        if not str(data.get("nome", "")).strip() and not str(data.get("cognome", "")).strip():
            skipped += 1
            continue
        docs.append(_row_to_doc(data, store_id, admin, now, vend_map, vend_fallback))
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

async def _fetch_tab_csv(http_client, sheet_id: str, gid: Optional[str] = None, sheet_name: str = ""):
    if sheet_name:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    else:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid or '0'}"
    return await http_client.get(url)

async def _import_store_tab(http_client, sheet_id: str, store: dict, fallback_hash: str, admin: dict,
                            vend_map: Optional[dict] = None, vend_fallback: str = "") -> dict:
    r = await _fetch_tab_csv(http_client, sheet_id, sheet_name=store["nome"])
    if r.status_code != 200 or hashlib.sha256(r.text.encode()).hexdigest() == fallback_hash:
        return {"store": store["nome"], "status": "pagina_non_trovata", "imported": 0}
    parsed, err = _parse_any_csv(r.text, store["id"], admin, vend_map, vend_fallback)
    if err:
        return {"store": store["nome"], "status": "errore", "detail": err, "imported": 0}
    docs, skipped = parsed
    if docs:
        await _insert_imported(docs, admin)
    return {"store": store["nome"], "status": "ok", "imported": len(docs), "skipped": skipped}

@api_router.post("/import/google-sheet")
async def import_google_sheet(input: SheetImportInput, admin: dict = Depends(require_admin)):
    m = re.search(r"/d/([a-zA-Z0-9\-_]+)", input.sheet_url)
    if not m:
        raise HTTPException(status_code=400, detail="Link Google Sheet non valido")
    sheet_id = m.group(1)
    gid_m = re.search(r"gid=(\d+)", input.sheet_url)
    vend_map = await _venditori_name_map()
    vend_fallback = vend_map.get("enrico", "")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http_client:
        if input.all_tabs:
            stores = await db.stores.find({}, {"_id": 0}).to_list(500)
            fallback_resp = await _fetch_tab_csv(http_client, sheet_id, sheet_name="__non_esiste__")
            if fallback_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Impossibile leggere il foglio. Verifica che sia condiviso: 'Chiunque abbia il link può visualizzare'.")
            fallback_hash = hashlib.sha256(fallback_resp.text.encode()).hexdigest()
            report, total_imported = [], 0
            for s in stores:
                rep = await _import_store_tab(http_client, sheet_id, s, fallback_hash, admin,
                                              vend_map, vend_fallback)
                report.append(rep)
                total_imported += rep["imported"]
            return {"mode": "all_tabs", "total_imported": total_imported, "report": report,
                    "hint": "Le pagine segnate come non trovate devono avere lo stesso nome del negozio, oppure importale singolarmente dal link della pagina (contiene gid)."}

        resp = await _fetch_tab_csv(http_client, sheet_id,
                                    gid=gid_m.group(1) if gid_m else None,
                                    sheet_name=input.sheet_name)
    if resp.status_code != 200 or ("text/csv" not in resp.headers.get("content-type", "") and "text/plain" not in resp.headers.get("content-type", "")):
        raise HTTPException(status_code=400, detail="Impossibile leggere il foglio. Verifica che sia condiviso: 'Chiunque abbia il link può visualizzare'.")
    parsed, err = _parse_any_csv(resp.text, input.store_id, admin, vend_map, vend_fallback)
    if err:
        raise HTTPException(status_code=400, detail=err)
    docs, skipped = parsed
    if docs:
        await _insert_imported(docs, admin)
    return {"imported": len(docs), "skipped": skipped}

# ---------------- Object Storage (allegati bollette/documenti) ----------------

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "gestionale-utenze"
storage_key = None

def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = httpx.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = httpx.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = httpx.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

async def get_scoped_client(client_id: str, user: dict) -> dict:
    scope = client_scope_filter(user)
    scope["id"] = client_id
    c = await db.clients.find_one(scope, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return c

@api_router.post("/clients/{client_id}/attachments")
async def upload_attachment(client_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    await get_scoped_client(client_id, user)
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    if ext not in ("pdf", "jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Formato non supportato (PDF, JPG, PNG, WEBP)")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 15 MB)")
    path = f"{APP_NAME}/attachments/{client_id}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    doc = {"id": str(uuid.uuid4()), "client_id": client_id, "storage_path": result["path"],
           "original_filename": file.filename, "content_type": file.content_type,
           "size": result["size"], "is_deleted": False, "uploaded_by": user["id"],
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.attachments.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/clients/{client_id}/attachments")
async def list_attachments(client_id: str, user: dict = Depends(get_current_user)):
    await get_scoped_client(client_id, user)
    return await db.attachments.find({"client_id": client_id, "is_deleted": False}, {"_id": 0}).to_list(200)

async def _check_attachment_scope(rec: dict, user: dict):
    if rec.get("client_id"):
        await get_scoped_client(rec["client_id"], user)
    else:
        await get_scoped_servizio(rec["servizio_id"], user)

@api_router.get("/attachments/{att_id}/download")
async def download_attachment(att_id: str, user: dict = Depends(get_current_user)):
    rec = await db.attachments.find_one({"id": att_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    await _check_attachment_scope(rec, user)
    data, content_type = get_object(rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type", content_type),
                    headers={"Content-Disposition": f'attachment; filename="{rec["original_filename"]}"'})

@api_router.delete("/attachments/{att_id}")
async def delete_attachment(att_id: str, user: dict = Depends(get_current_user)):
    rec = await db.attachments.find_one({"id": att_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Allegato non trovato")
    await _check_attachment_scope(rec, user)
    await db.attachments.update_one({"id": att_id}, {"$set": {"is_deleted": True}})
    return {"status": "ok"}

@api_router.get("/clients/{client_id}/attachments/merged")
async def merged_pdf(client_id: str, user: dict = Depends(get_current_user)):
    from pypdf import PdfWriter, PdfReader
    client_doc = await get_scoped_client(client_id, user)
    atts = await db.attachments.find({"client_id": client_id, "is_deleted": False,
                                      "content_type": "application/pdf"}, {"_id": 0}).to_list(200)
    if not atts:
        raise HTTPException(status_code=400, detail="Nessun PDF tra gli allegati di questo cliente")
    writer = PdfWriter()
    for att in atts:
        data, _ = get_object(att["storage_path"])
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    fname = f"documenti_{client_doc.get('cognome', 'cliente')}_{client_doc.get('nome', '')}.pdf".replace(" ", "_")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

# ---------------- Numerazione automatica, Magazzino, Ritiri, PDF ----------------

RITIRO_SEEDS = {"morbegno": ("M", 8), "grosio": ("GR", 1), "sondrio": ("SO", 7),
                "gravedona": ("G", 3), "tirano": ("T", 1), "sondalo": ("SA", 1)}

async def next_numero(kind: str, store_id: str, default_prefix: str = "RIP") -> str:
    store = await db.stores.find_one({"id": store_id}, {"_id": 0, "nome": 1})
    sname = (store or {}).get("nome", "").lower()
    prefix, start = default_prefix, 1
    if kind == "ritiro":
        for key, (p, s) in RITIRO_SEEDS.items():
            if key in sname:
                prefix, start = p, s
                break
    ckey = f"{kind}:{store_id}"
    existing = await db.counters.find_one({"_id": ckey})
    if not existing:
        await db.counters.insert_one({"_id": ckey, "prefix": prefix, "seq": start})
        existing = {"prefix": prefix, "seq": start}
    seq = existing["seq"]
    await db.counters.update_one({"_id": ckey}, {"$inc": {"seq": 1}})
    return f"{existing.get('prefix', prefix)}{seq}"

MAGAZZINO_CATEGORIE = ["display", "ricambi", "accessori", "sim", "rigenerati", "altro"]

class MagazzinoInput(BaseModel):
    nome: str
    categoria: str = "altro"
    store_id: str = ""
    quantita: int = 0
    prezzo_acquisto: Optional[float] = None
    prezzo_vendita: Optional[float] = None
    note: str = ""

def magazzino_scope(user: dict) -> dict:
    if user["role"] in ("admin", "tecnico") or user.get("can_view_all"):
        return {}
    return {"store_id": {"$in": user.get("store_ids", [])}}

@api_router.get("/magazzino")
async def list_magazzino(user: dict = Depends(get_current_user), categoria: str = "",
                         venditore_id: str = "", q: str = ""):
    scope = magazzino_scope(user)
    if categoria:
        scope["categoria"] = categoria
    if venditore_id and (user["role"] in ("admin", "tecnico") or user.get("can_view_all")):
        scope["store_id"] = venditore_id
    if q:
        scope["nome"] = {"$regex": re.escape(q), "$options": "i"}
    items = await db.magazzino.find(scope, {"_id": 0}).sort("nome", 1).to_list(5000)
    store_ids = list({i.get("store_id", "") for i in items if i.get("store_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(200)
    smap = {s["id"]: s["nome"] for s in stores}
    for i in items:
        i["store_name"] = smap.get(i.get("store_id", ""), "-")
    return items

@api_router.get("/magazzino/disponibilita")
async def disponibilita_magazzino(user: dict = Depends(get_current_user), q: str = "", categoria: str = ""):
    scope = {}
    if q:
        scope["nome"] = {"$regex": re.escape(q), "$options": "i"}
    if categoria:
        scope["categoria"] = categoria
    items = await db.magazzino.find(scope, {"_id": 0}).to_list(5000)
    store_ids = list({i.get("store_id", "") for i in items if i.get("store_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(200)
    smap = {s["id"]: s["nome"] for s in stores}
    grouped = {}
    for i in items:
        key = (i.get("nome", "").strip().lower(), i.get("categoria", ""))
        g = grouped.setdefault(key, {"nome": i.get("nome", ""), "categoria": i.get("categoria", ""), "stores": []})
        can_price = user["role"] in ("admin", "tecnico") or user.get("can_view_all") \
            or i.get("store_id") in user.get("store_ids", [])
        g["stores"].append({"item_id": i["id"], "store_id": i.get("store_id", ""),
                            "store_name": smap.get(i.get("store_id", ""), "-"),
                            "quantita": i.get("quantita", 0),
                            "prezzo_vendita": i.get("prezzo_vendita") if can_price else None})
    return sorted(grouped.values(), key=lambda x: x["nome"])

@api_router.post("/magazzino")
async def create_magazzino(input: MagazzinoInput, user: dict = Depends(get_current_user)):
    data = input.model_dump()
    if data["categoria"] not in MAGAZZINO_CATEGORIE:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    if user["role"] == "negozio" and user.get("store_ids"):
        data["store_id"] = user["store_ids"][0]
    if not data["store_id"]:
        raise HTTPException(status_code=400, detail="Negozio obbligatorio")
    now = datetime.now(timezone.utc).isoformat()
    data.update({"id": str(uuid.uuid4()), "created_by": user["id"], "created_at": now, "updated_at": now})
    await db.magazzino.insert_one(data)
    data.pop("_id", None)
    return data

@api_router.patch("/magazzino/{item_id}")
async def update_magazzino(item_id: str, input: MagazzinoInput, user: dict = Depends(get_current_user)):
    scope = magazzino_scope(user)
    scope["id"] = item_id
    old = await db.magazzino.find_one(scope, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    data = input.model_dump(exclude_unset=True)
    if user["role"] == "negozio":
        data.pop("store_id", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.magazzino.update_one({"id": item_id}, {"$set": data})
    return await db.magazzino.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/magazzino/{item_id}")
async def delete_magazzino(item_id: str, admin: dict = Depends(require_admin)):
    res = await db.magazzino.delete_one({"id": item_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return {"status": "ok"}

class MovimentoInput(BaseModel):
    delta: int
    motivo: str = ""

@api_router.post("/magazzino/{item_id}/movimento")
async def movimento_magazzino(item_id: str, input: MovimentoInput, user: dict = Depends(get_current_user)):
    scope = magazzino_scope(user)
    scope["id"] = item_id
    item = await db.magazzino.find_one(scope, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    new_q = (item.get("quantita") or 0) + input.delta
    if new_q < 0:
        raise HTTPException(status_code=400, detail="Giacenza insufficiente")
    await db.magazzino.update_one({"id": item_id},
                                  {"$set": {"quantita": new_q, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "ok", "quantita": new_q}

def _xlsx_response(ws_title: str, headers: list, rows: list, fname: str):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = ws_title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        width = max(len(str(c.value or "")) for c in col) + 3
        ws.column_dimensions[col[0].column_letter].width = min(width, 45)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

@api_router.get("/magazzino/export")
async def export_magazzino(user: dict = Depends(get_current_user)):
    items = await db.magazzino.find(magazzino_scope(user), {"_id": 0}).sort("nome", 1).to_list(5000)
    store_ids = list({i.get("store_id", "") for i in items if i.get("store_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(200)
    smap = {s["id"]: s["nome"] for s in stores}
    rows = [[i.get("nome", ""), i.get("categoria", ""), smap.get(i.get("store_id", ""), "-"),
             i.get("quantita", 0), i.get("prezzo_acquisto"), i.get("prezzo_vendita"), i.get("note", "")] for i in items]
    return _xlsx_response("Magazzino", ["Articolo", "Categoria", "Negozio", "Giacenza", "Prezzo acquisto", "Prezzo vendita", "Note"],
                          rows, f"magazzino_{date.today().isoformat()}.xlsx")

@api_router.get("/ritiri/export")
async def export_ritiri(user: dict = Depends(get_current_user)):
    scope = ritiri_scope(user)
    ritiri = await db.ritiri.find(scope, {"_id": 0}).sort("created_at", -1).to_list(5000)
    store_ids = list({r.get("store_id", "") for r in ritiri if r.get("store_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(200)
    smap = {s["id"]: s["nome"] for s in stores}
    rows = [[r.get("numero", ""), _fmt_it(r.get("data_ritiro")), r.get("cognome", ""), r.get("nome", ""),
             r.get("codice_fiscale", ""), r.get("articolo", ""), r.get("imei", ""), r.get("prezzo_ritiro"),
             r.get("numero_documento", ""), r.get("n_allegati", ""), smap.get(r.get("store_id", ""), "-")] for r in ritiri]
    return _xlsx_response("Ritiri", ["N. ritiro", "Data", "Cognome", "Nome", "Codice fiscale", "Articolo", "IMEI",
                                     "Prezzo ritiro", "N. documento", "Allegati", "Negozio"],
                          rows, f"ritiri_usato_{date.today().isoformat()}.xlsx")

class RicambioUsoInput(BaseModel):
    magazzino_id: str
    quantita: int = 1
    prezzo_manuale: Optional[float] = None

@api_router.post("/servizi/{servizio_id}/ricambi")
async def usa_ricambio(servizio_id: str, input: RicambioUsoInput, user: dict = Depends(get_current_user)):
    svc = await get_scoped_servizio(servizio_id, user)
    if svc.get("tipo") != "riparazione":
        raise HTTPException(status_code=400, detail="Ricambi solo per riparazioni")
    item = await db.magazzino.find_one({"id": input.magazzino_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Articolo non trovato in magazzino")
    if item.get("store_id") != svc.get("venditore_id"):
        raise HTTPException(status_code=400, detail="Ricambio di un altro negozio: fai prima uno spostamento di giacenza")
    if input.quantita < 1:
        raise HTTPException(status_code=400, detail="Quantità non valida")
    if (item.get("quantita") or 0) < input.quantita:
        raise HTTPException(status_code=400, detail="Giacenza insufficiente")
    now = datetime.now(timezone.utc).isoformat()
    await db.magazzino.update_one({"id": item["id"]},
                                  {"$inc": {"quantita": -input.quantita}, "$set": {"updated_at": now}})
    prezzo = input.prezzo_manuale if input.prezzo_manuale is not None else item.get("prezzo_vendita")
    uso = {"item_id": item["id"], "nome": item["nome"], "quantita": input.quantita,
           "prezzo_vendita": prezzo, "at": now}
    await db.servizi.update_one({"id": servizio_id},
                                {"$push": {"ricambi_usati": uso}, "$set": {"updated_at": now}})
    return {"status": "ok", "giacenza": (item.get("quantita") or 0) - input.quantita}

@api_router.delete("/servizi/{servizio_id}/ricambi/{index}")
async def annulla_ricambio(servizio_id: str, index: int, user: dict = Depends(get_current_user)):
    svc = await get_scoped_servizio(servizio_id, user)
    usati = list(svc.get("ricambi_usati") or [])
    if index < 0 or index >= len(usati):
        raise HTTPException(status_code=404, detail="Ricambio non trovato")
    uso = usati[index]
    await db.magazzino.update_one({"id": uso["item_id"]},
                                  {"$inc": {"quantita": uso["quantita"]},
                                   "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    usati.pop(index)
    await db.servizi.update_one({"id": servizio_id},
                                {"$set": {"ricambi_usati": usati,
                                          "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "ok"}

def _fmt_it(iso: str) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso or "-")

def _new_pdf(title: str, subtitle: str = ""):
    from fpdf import FPDF
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    logo = "/app/frontend/public/rs-logo.png"
    if os.path.exists(logo):
        pdf.image(logo, x=(210 - 34) / 2, w=34)
        pdf.ln(2)
    pdf.set_font("helvetica", "B", 17)
    pdf.cell(0, 10, title, align="C", new_x="LMARGIN", new_y="NEXT")
    if subtitle:
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 7, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    return pdf

def _pdf_field(pdf, label: str, value: str):
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(55, 9, label)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 9, str(value or "-"), new_x="LMARGIN", new_y="NEXT")

def _pdf_multiline(pdf, label: str, value: str):
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.multi_cell(0, 7, str(value or "-"))
    pdf.ln(1)

def _build_scheda_pdf(svc: dict, client_doc: dict) -> bytes:
    pdf = _new_pdf("Scheda riparazione",
                   f"N. {svc.get('numero_riparazione') or '-'}  -  Data: {_fmt_it(svc.get('created_at'))}")
    tel = (client_doc or {}).get("telefono", "")
    _pdf_field(pdf, "Cliente", svc.get("client_name") or f"{(client_doc or {}).get('cognome', '')} {(client_doc or {}).get('nome', '')}".strip())
    _pdf_field(pdf, "Telefono", tel)
    _pdf_field(pdf, "Dispositivo", svc.get("dispositivo"))
    sblocco = ""
    if svc.get("codice_sblocco_tipo") and svc.get("codice_sblocco_tipo") != "nessuno":
        sblocco = f"{svc['codice_sblocco_tipo']}: {svc.get('codice_sblocco') or '-'}"
    _pdf_field(pdf, "Codice sblocco", sblocco or "Nessuno")
    pdf.ln(2)
    _pdf_multiline(pdf, "Problema riscontrato", svc.get("problema"))
    _pdf_multiline(pdf, "Operazioni svolte", svc.get("operazioni"))
    usati = svc.get("ricambi_usati") or []
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, "Ricambi utilizzati", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    if usati:
        for u in usati:
            pdf.cell(0, 7, f"- {u.get('nome', '')} x{u.get('quantita', 1)}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 7, "Nessun ricambio", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    if svc.get("prezzo_consigliato") is not None:
        _pdf_field(pdf, "Prezzo", f"EUR {svc['prezzo_consigliato']:.2f} (IVA inclusa)")
    pdf.ln(12)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(95, 8, "Firma tecnico: ______________________")
    pdf.cell(0, 8, "Firma cliente: ______________________", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())

@api_router.get("/servizi/{servizio_id}/scheda")
async def scheda_riparazione(servizio_id: str, user: dict = Depends(get_current_user)):
    svc = await get_scoped_servizio(servizio_id, user)
    if svc.get("tipo") != "riparazione":
        raise HTTPException(status_code=400, detail="Scheda disponibile solo per riparazioni")
    client_doc = await db.clients.find_one({"id": svc["client_id"]}, {"_id": 0})
    names = await clients_name_map([svc["client_id"]])
    svc["client_name"] = names.get(svc["client_id"], "")
    svc["prezzo_consigliato"] = calcola_prezzo_riparazione(svc)
    buf = io.BytesIO(_build_scheda_pdf(svc, client_doc or {}))
    fname = f"scheda_{svc.get('numero_riparazione') or servizio_id}.pdf".replace(" ", "_")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

def _build_bolla_pdf(r: dict) -> bytes:
    pdf = _new_pdf("Bolla di ritiro articoli usati",
                   f"N. {r.get('numero', '-')}  -  Data ritiro: {_fmt_it(r.get('data_ritiro'))}")
    pdf.ln(4)
    _pdf_field(pdf, "Nome", r.get("nome"))
    _pdf_field(pdf, "Cognome", r.get("cognome"))
    _pdf_field(pdf, "Codice Fiscale", r.get("codice_fiscale"))
    _pdf_field(pdf, "Articolo", r.get("articolo"))
    _pdf_field(pdf, "IMEI", r.get("imei"))
    prezzo = f"EUR {r['prezzo_ritiro']:.2f}" if r.get("prezzo_ritiro") is not None else "-"
    _pdf_field(pdf, "Prezzo ritiro", prezzo)
    _pdf_field(pdf, "Numero documento", r.get("numero_documento"))
    _pdf_field(pdf, "Si allegano documenti n.", str(r.get("n_allegati", 2)))
    pdf.ln(14)
    pdf.set_font("helvetica", "", 11)
    pdf.cell(95, 8, "Firma negozio: ______________________")
    pdf.cell(0, 8, "Firma cliente: ______________________", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())

class RitiroInput(BaseModel):
    store_id: str = ""
    client_id: str = ""
    nome: str
    cognome: str
    codice_fiscale: str = ""
    articolo: str
    imei: str = ""
    prezzo_ritiro: Optional[float] = None
    numero_documento: str = ""
    n_allegati: int = 2
    data_ritiro: Optional[str] = None

def ritiri_scope(user: dict) -> dict:
    if "riparazioni" not in user_sections(user):
        raise HTTPException(status_code=403, detail="Sezione non abilitata per questo utente")
    if user["role"] == "admin" or user.get("can_view_all"):
        return {}
    return {"store_id": {"$in": user.get("store_ids", [])}}

@api_router.get("/ritiri")
async def list_ritiri(user: dict = Depends(get_current_user), venditore_id: str = "", q: str = ""):
    scope = ritiri_scope(user)
    if venditore_id and (user["role"] == "admin" or user.get("can_view_all")):
        scope["store_id"] = venditore_id
    ritiri = await db.ritiri.find(scope, {"_id": 0}).sort("created_at", -1).to_list(5000)
    if q:
        ql = q.lower()
        ritiri = [r for r in ritiri if ql in f"{r.get('cognome', '')} {r.get('nome', '')}".lower()
                  or ql in r.get("articolo", "").lower() or ql in r.get("numero", "").lower()]
    store_ids = list({r.get("store_id", "") for r in ritiri if r.get("store_id")})
    stores = await db.stores.find({"id": {"$in": store_ids}}, {"_id": 0, "id": 1, "nome": 1}).to_list(200)
    smap = {s["id"]: s["nome"] for s in stores}
    for r in ritiri:
        r["store_name"] = smap.get(r.get("store_id", ""), "-")
    return ritiri

@api_router.post("/ritiri")
async def create_ritiro(input: RitiroInput, user: dict = Depends(get_current_user)):
    ritiri_scope(user)
    data = input.model_dump()
    if user["role"] == "negozio" and user.get("store_ids"):
        data["store_id"] = user["store_ids"][0]
    if not data["store_id"]:
        raise HTTPException(status_code=400, detail="Negozio obbligatorio")
    if not data["nome"].strip() or not data["cognome"].strip() or not data["articolo"].strip():
        raise HTTPException(status_code=400, detail="Nome, cognome e articolo sono obbligatori")
    data["numero"] = await next_numero("ritiro", data["store_id"])
    if not data.get("data_ritiro"):
        data["data_ritiro"] = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    data.update({"id": str(uuid.uuid4()), "created_by": user["id"], "created_at": now})
    pdf_bytes = _build_bolla_pdf(data)
    result = put_object(f"{APP_NAME}/ritiri/{data['numero']}.pdf", pdf_bytes, "application/pdf")
    data["storage_path"] = result["path"]
    await db.ritiri.insert_one(data)
    data.pop("_id", None)
    return data

@api_router.get("/ritiri/{ritiro_id}/pdf")
async def download_bolla(ritiro_id: str, user: dict = Depends(get_current_user)):
    scope = ritiri_scope(user)
    scope["id"] = ritiro_id
    r = await db.ritiri.find_one(scope, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Ritiro non trovato")
    data, _ = get_object(r["storage_path"])
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{r["numero"]}.pdf"'})

@api_router.delete("/ritiri/{ritiro_id}")
async def delete_ritiro(ritiro_id: str, admin: dict = Depends(require_admin)):
    res = await db.ritiri.delete_one({"id": ritiro_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ritiro non trovato")
    return {"status": "ok"}

# ---------------- WhatsApp (Baileys service) ----------------

WA_SERVICE = os.environ.get("WA_SERVICE_URL", "http://127.0.0.1:3001")
WA_SERVICE_KEY = os.environ.get("WA_SERVICE_KEY", "")

def wa_headers() -> dict:
    return {"X-API-Key": WA_SERVICE_KEY} if WA_SERVICE_KEY else {}

PRIVACY_MSG = """RS Group – Grazie per averci scelto!
Ciao {nome}
per procedere con la tua richiesta e completare l'attivazione del servizio, è necessario firmare l'autorizzazione privacy.
Puoi farlo in modo semplice e veloce al link qui sotto:
https://rsriparazioni.it/privacy/
La firma è richiesta per attivare correttamente il servizio (riparazioni, contratti energia o telefonia).
Grazie per la fiducia
RS Group"""

REVIEW_MSG = """Ciao!
Grazie per aver scelto CAMBIAORA
Se ti sei trovato bene, ci farebbe davvero piacere una tua recensione
Basta un clic qui
https://g.page/r/CaSv3O7luiBPEAE/review
Grazie per il supporto"""

async def wa_send(phone: str, message: str, session: str = "default"):
    log = {"phone": phone, "session": session, "message": message[:120],
           "at": datetime.now(timezone.utc).isoformat(), "ok": False, "error": None, "session_used": None}
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(f"{WA_SERVICE}/send", json={"phone": phone, "message": message, "session": session}, headers=wa_headers())
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        log["ok"] = resp.status_code == 200 and bool(data.get("success"))
        log["session_used"] = data.get("session")
        if not log["ok"]:
            log["error"] = data.get("error", "Servizio WhatsApp non disponibile")
            raise HTTPException(status_code=502, detail=log["error"])
        return data
    except HTTPException as e:
        log["error"] = log["error"] or str(e.detail)
        raise
    except Exception as e:
        log["error"] = str(e)
        raise HTTPException(status_code=502, detail=f"Servizio WhatsApp non raggiungibile: {e}")
    finally:
        await db.wa_log.insert_one(log)

PRIVACY_PROXY = "https://rsriparazioni.com/api/proxy.php"

STORE_TO_SITO = {"tirano": "tirano", "sondalo": "sondalo", "sondrio": "sondrio",
                 "sondrio grosio": "grosio", "gravedona": "gravedona"}

async def register_privacy_site(client: dict, store_name: str, categoria: str = "CambiaOra", dettaglio: str = "CambiaOra") -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as hc:
        r1 = await hc.post(f"{PRIVACY_PROXY}?action=generateOtp", json={"email": client["email"]})
        d1 = r1.json()
        if d1.get("result") != "ok":
            raise HTTPException(status_code=502, detail=f"Generazione OTP fallita: {d1.get('message', 'errore')}")
        reg = {
            "nome": client.get("nome", ""), "cognome": client.get("cognome", ""),
            "codiceFiscale": client.get("codice_fiscale", ""), "telefono": client.get("telefono", ""),
            "email": client["email"],
            "servizioCategoria": categoria, "servizioDettaglio": dettaglio,
            "negozio": STORE_TO_SITO.get(store_name.strip().lower(), ""),
            "privacyAccepted": True, "otp": d1.get("otp", ""),
        }
        r2 = await hc.post(f"{PRIVACY_PROXY}?action=register", json=reg)
        d2 = r2.json()
        if d2.get("result") != "ok":
            raise HTTPException(status_code=502, detail=f"Registrazione privacy fallita: {d2.get('message', 'errore')}")
    return d2

@api_router.get("/whatsapp/log")
async def whatsapp_log(admin: dict = Depends(require_admin)):
    return await db.wa_log.find({}, {"_id": 0}).sort("at", -1).to_list(50)

@api_router.get("/whatsapp/sessions-summary")
async def whatsapp_sessions_summary(admin: dict = Depends(require_admin)):
    totale = await db.stores.count_documents({}) + 1
    try:
        async with httpx.AsyncClient(timeout=5) as http_client:
            resp = await http_client.get(f"{WA_SERVICE}/status", headers=wa_headers())
        sessions = resp.json().get("sessions", [])
        connessi = len([s for s in sessions if s.get("connected")])
        return {"connessi": connessi, "totale": totale}
    except Exception:
        return {"connessi": None, "totale": totale}

@api_router.get("/whatsapp/status")
async def whatsapp_status(admin: dict = Depends(require_admin)):
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            resp = await http_client.get(f"{WA_SERVICE}/status", headers=wa_headers())
        return resp.json()
    except Exception:
        return {"connected": False, "user": None, "has_qr": False, "service_down": True}

@api_router.get("/whatsapp/qr")
async def whatsapp_qr(session: str = "default", admin: dict = Depends(require_admin)):
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            resp = await http_client.get(f"{WA_SERVICE}/qr", params={"session": session}, headers=wa_headers())
        return resp.json()
    except Exception:
        return {"qr": None, "connected": False}

class PairInput(BaseModel):
    phone: str
    session: str = "default"

@api_router.post("/whatsapp/pair")
async def whatsapp_pair(input: PairInput, admin: dict = Depends(require_admin)):
    try:
        async with httpx.AsyncClient(timeout=25) as http_client:
            resp = await http_client.post(f"{WA_SERVICE}/pair", json={"phone": input.phone, "session": input.session}, headers=wa_headers())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("error", "Pairing fallito"))
        return resp.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Servizio WhatsApp non raggiungibile")

@api_router.post("/clients/{client_id}/whatsapp/privacy")
async def whatsapp_privacy(client_id: str, user: dict = Depends(get_current_user)):
    c = await get_scoped_client(client_id, user)
    if not c.get("telefono"):
        raise HTTPException(status_code=400, detail="Il cliente non ha un numero di telefono")
    registered, reg_error = False, None
    if c.get("email"):
        try:
            store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0})
            await register_privacy_site(c, (store or {}).get("nome", ""))
            registered = True
        except Exception as e:
            reg_error = getattr(e, "detail", str(e))
            logger.error(f"Registrazione privacy sito fallita per {client_id}: {reg_error}")
    wa_error = None
    try:
        await wa_send(c["telefono"], PRIVACY_MSG.format(nome=c.get("nome", "")), session=c.get("venditore_id") or "default")
    except Exception as e:
        wa_error = getattr(e, "detail", str(e))
    if wa_error and not registered:
        raise HTTPException(status_code=502, detail=f"WhatsApp: {wa_error}")
    now = datetime.now(timezone.utc)
    updates = {}
    if not wa_error:
        updates["privacy_msg_sent_at"] = now.isoformat()
        await db.whatsapp_queue.insert_one({
            "id": str(uuid.uuid4()), "client_id": client_id, "phone": c["telefono"],
            "type": "review", "message": REVIEW_MSG, "send_after": (now + timedelta(minutes=5)).isoformat(),
            "session": c.get("venditore_id") or "default",
            "sent": False, "created_at": now.isoformat()})
    if registered:
        updates["privacy_firmata"] = True
        updates["privacy_registered_at"] = now.isoformat()
    if updates:
        await db.clients.update_one({"id": client_id}, {"$set": updates})
    return {"status": "ok", "privacy_registered": registered, "registration_error": reg_error,
            "wa_error": wa_error, "review_scheduled_at": (now + timedelta(minutes=5)).isoformat() if not wa_error else None}

@api_router.post("/clients/{client_id}/whatsapp/review")
async def whatsapp_review(client_id: str, user: dict = Depends(get_current_user)):
    c = await get_scoped_client(client_id, user)
    if not c.get("telefono"):
        raise HTTPException(status_code=400, detail="Il cliente non ha un numero di telefono")
    await wa_send(c["telefono"], REVIEW_MSG, session=c.get("venditore_id") or "default")
    await db.clients.update_one({"id": client_id},
                                {"$set": {"review_msg_sent_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "ok"}

async def process_whatsapp_queue():
    now = datetime.now(timezone.utc).isoformat()
    due = await db.whatsapp_queue.find({"sent": False, "send_after": {"$lte": now}}, {"_id": 0}).to_list(100)
    sent_count = 0
    for item in due:
        try:
            await wa_send(item["phone"], item.get("message") or REVIEW_MSG, session=item.get("session", "default"))
            await db.whatsapp_queue.update_one({"id": item["id"]}, {"$set": {"sent": True, "sent_at": now}})
            await db.clients.update_one({"id": item["client_id"]}, {"$set": {"review_msg_sent_at": now}})
            sent_count += 1
        except Exception as e:
            logger.error(f"WhatsApp queue send fallito per {item['id']}: {getattr(e, 'detail', str(e))}")
    if sent_count:
        logger.info(f"WhatsApp queue: {sent_count} recensioni inviate")

# ---------------- Export Excel ----------------

EXPORT_COLUMNS = [
    ("cognome", "Cognome"), ("nome", "Nome"), ("codice_fiscale", "Codice Fiscale"), ("p_iva", "P.IVA"),
    ("indirizzo", "Indirizzo"), ("telefono", "Telefono"), ("email", "Email"), ("iban", "IBAN"),
    ("tipo_bolletta", "Tipo"), ("pod", "POD"), ("pdr", "PDR"), ("kw_potenza", "kW"),
    ("fornitore_provenienza", "Fornitore attuale"), ("nuovo_fornitore", "Nuovo fornitore"),
    ("tipo_contratto", "Tipo contratto"), ("costo_kwh_nuovo", "€/kWh nuovo"),
    ("costo_smc_nuovo", "€/Smc nuovo"), ("spese_fisse_nuovo", "Spese fisse nuove"),
    ("data_contratto", "Data contratto"), ("data_attivazione", "Attivazione"),
    ("data_rinnovo", "Rinnovo (10 mesi)"), ("data_scadenza", "Scadenza"),
    ("data_verifica", "Data verifica"), ("data_cambio", "Data cambio"),
    ("lavorazione_label", "Lavorazione"), ("pagato_label", "Pagato"),
    ("privacy_label", "Privacy firmata"), ("negozio_nome", "Negozio"), ("note", "Note"),
]

@api_router.get("/export/clients.xlsx")
async def export_clients(user: dict = Depends(get_current_user)):
    scope = client_scope_filter(user)
    proj = {"_id": 0, "id": 1, "cognome": 1, "nome": 1, "codice_fiscale": 1, "p_iva": 1,
            "indirizzo": 1, "telefono": 1, "email": 1, "iban": 1, "tipo_bolletta": 1, "pod": 1,
            "pdr": 1, "kw_potenza": 1, "fornitore_provenienza": 1, "nuovo_fornitore": 1,
            "tipo_contratto": 1, "costo_kwh_nuovo": 1, "costo_smc_nuovo": 1, "spese_fisse_nuovo": 1,
            "data_contratto": 1, "data_verifica": 1, "data_cambio": 1, "lavorazione": 1,
            "pagato": 1, "last_payment_date": 1, "privacy_firmata": 1, "venditore_id": 1, "note": 1}
    clients = await db.clients.find(scope, proj).sort("cognome", 1).to_list(10000)
    stores = {s["id"]: s["nome"] for s in await db.stores.find({}, {"_id": 0}).to_list(500)}
    lav_labels = {"cambiare": "Da Cambiare", "non_cambiare": "Non Cambiare", "cambio_effettuato": "Cambio Effettuato",
                  "in_quotazione": "In Quotazione", "richieste_bollette": "Richieste Bollette",
                  "in_attesa_ok": "In Attesa OK Cliente", "problema_tecnico": "Problema Tecnico",
                  "da_quotare": "Da Quotare", "contattare_cliente": "Contattare Cliente",
                  "non_vuole_cambiare": "Non Vuole Cambiare", "passa_in_negozio": "Passa in Negozio",
                  "attesa_documenti": "Attesa Documenti", "rinnovato": "Rinnovato"}
    rows = []
    for c in clients:
        compute_dates(c)
        c["lavorazione_label"] = lav_labels.get(c.get("lavorazione"), c.get("lavorazione", ""))
        c["pagato_label"] = "Pagato" if c["pagato_effettivo"] else "Non pagato"
        c["privacy_label"] = "Sì" if c.get("privacy_firmata") else "No"
        c["negozio_nome"] = stores.get(c.get("venditore_id"), "")
        rows.append({label: c.get(key, "") for key, label in EXPORT_COLUMNS})
    df = pd.DataFrame(rows, columns=[label for _, label in EXPORT_COLUMNS])
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Clienti")
    buf.seek(0)
    fname = f"report_clienti_{date.today().isoformat()}.xlsx"
    return StreamingResponse(buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

# ---------------- Servizi (riparazioni / telefonia) ----------------

RIP_STATI = ["ingresso", "attesa_ricambio_cliente", "attesa_ricambio_carico", "in_attesa_cliente",
             "preventivo", "in_lavorazione", "pronto", "consegnato", "non_riparabile"]

SERVIZIO_TIPI = ["riparazione", "accessori", "vendita", "sim", "internet", "fisso"]

TIPO_TO_SECTION = {"riparazione": "riparazioni", "accessori": "telefonia", "vendita": "telefonia",
                   "sim": "telefonia", "internet": "telefonia", "fisso": "telefonia"}

SIM_OPERATORS = ["WINDTRE", "FASTWEB", "TIM", "VERY", "KENA", "HO", "DIGI", "ILIAD"]
FISSO_OPERATORS = ["TIM", "WindTre", "Fastweb", "Vodafone", "Iliad", "Eolo"]
INTERNET_OPERATORS = ["WINDTRE", "ENELFIBRA", "EOLO", "FASTWEB", "ILIAD", "TIM", "Vodafone"]

ALL_SECTIONS = ["energia", "riparazioni", "telefonia"]

def user_sections(user: dict) -> list:
    secs = user.get("sections")
    return secs if secs else ALL_SECTIONS

def servizio_scope(user: dict, tipo: str = "") -> dict:
    sections = user_sections(user)
    if user["role"] == "tecnico":
        allowed = ["riparazione"] if "riparazioni" in sections else []
        base = {}
    else:
        allowed = [t for t, sec in TIPO_TO_SECTION.items() if sec in sections]
        if user["role"] == "admin" or user.get("can_view_all"):
            base = {}
        else:
            base = {"venditore_id": {"$in": user.get("store_ids", [])}}
    if tipo:
        if tipo not in allowed:
            raise HTTPException(status_code=403, detail="Sezione non abilitata per questo utente")
        base["tipo"] = tipo
    else:
        base["tipo"] = {"$in": allowed} if allowed else "__nessuno__"
    return base

def calcola_prezzo_riparazione(s: dict) -> Optional[float]:
    if s.get("tipo") != "riparazione":
        return None
    minuti = max(int(s.get("minuti_lavoro") or 0), 30)
    lavoro = minuti * 0.22775
    if s.get("con_ricambio"):
        base = float(s.get("costo_componente") or 0) + 2.0 + lavoro + 60.0
    else:
        base = 30.0 + lavoro
    return round(base * 1.22, 2)

def serialize_servizio(s: dict, client_name: str = "") -> dict:
    out = {k: v for k, v in s.items() if k != "_id"}
    out["client_name"] = client_name
    if s.get("data_attivazione") and s.get("vincolo_mesi"):
        try:
            scad = date.fromisoformat(str(s["data_attivazione"])[:10]) + relativedelta(months=int(s["vincolo_mesi"]))
            out["scadenza_vincolo"] = scad.isoformat()
            out["giorni_alla_scadenza"] = (scad - date.today()).days
        except (ValueError, TypeError):
            pass
    out["prezzo_consigliato"] = calcola_prezzo_riparazione(s)
    return out

async def get_scoped_servizio(servizio_id: str, user: dict) -> dict:
    scope = servizio_scope(user)
    scope["id"] = servizio_id
    s = await db.servizi.find_one(scope, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Servizio non trovato")
    return s

async def clients_name_map(client_ids: list) -> dict:
    if not client_ids:
        return {}
    docs = await db.clients.find({"id": {"$in": client_ids}}, {"_id": 0, "id": 1, "nome": 1, "cognome": 1}).to_list(10000)
    return {d["id"]: f"{d.get('cognome', '')} {d.get('nome', '')}".strip() for d in docs}

class ServizioInput(BaseModel):
    client_id: str
    tipo: str
    venditore_id: str = ""
    operatore_id: str = ""
    stato: str = "ingresso"
    dispositivo: str = ""
    problema: str = ""
    con_ricambio: bool = False
    costo_componente: Optional[float] = None
    minuti_lavoro: Optional[int] = None
    prodotto: str = ""
    operatore_tel: str = ""
    numero: str = ""
    iccid: str = ""
    data_attivazione: Optional[str] = None
    vincolo_mesi: Optional[int] = None
    importo: Optional[float] = None
    pagato: bool = False
    note: str = ""
    codice_sblocco_tipo: str = ""
    codice_sblocco: str = ""
    account_email: str = ""
    account_password: str = ""
    operazioni: str = ""
    cliente_contattato: bool = False

@api_router.get("/servizi")
async def list_servizi(user: dict = Depends(get_current_user), tipo: str = "", stato: str = "",
                       venditore_id: str = "", q: str = ""):
    scope = servizio_scope(user, tipo)
    if stato:
        scope["stato"] = stato
    if venditore_id and (user["role"] == "admin" or user.get("can_view_all")):
        scope["venditore_id"] = venditore_id
    servizi = await db.servizi.find(scope, {"_id": 0}).sort("created_at", -1).to_list(5000)
    names = await clients_name_map(list({s["client_id"] for s in servizi}))
    if q:
        ql = q.lower()
        servizi = [s for s in servizi if ql in names.get(s["client_id"], "").lower()
                   or ql in s.get("dispositivo", "").lower() or ql in s.get("numero", "").lower()
                   or ql in s.get("operatore_tel", "").lower() or ql in s.get("prodotto", "").lower()]
    return [serialize_servizio(s, names.get(s["client_id"], "")) for s in servizi]

@api_router.post("/servizi")
async def create_servizio(input: ServizioInput, user: dict = Depends(get_current_user)):
    if input.tipo not in SERVIZIO_TIPI:
        raise HTTPException(status_code=400, detail="Tipo servizio non valido")
    servizio_scope(user, input.tipo)  # gate sezione
    client_doc = await db.clients.find_one({"id": input.client_id}, {"_id": 0})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    data = input.model_dump()
    if user["role"] in ("negozio",) and user.get("store_ids"):
        data["venditore_id"] = user["store_ids"][0]
    if data["tipo"] == "riparazione" and data["stato"] not in RIP_STATI:
        data["stato"] = "ingresso"
    if data["tipo"] == "riparazione":
        data["numero_riparazione"] = await next_numero("riparazione", data.get("venditore_id") or "")
    now = datetime.now(timezone.utc).isoformat()
    data.update({"id": str(uuid.uuid4()), "created_by": user["id"], "created_at": now, "updated_at": now,
                 "last_payment_date": date.today().isoformat() if data.get("pagato") else None,
                 "privacy_firmata": False, "privacy_msg_sent_at": None, "review_msg_sent_at": None})
    await db.servizi.insert_one(data)
    data.pop("_id", None)
    return serialize_servizio(data, f"{client_doc.get('cognome', '')} {client_doc.get('nome', '')}".strip())

@api_router.get("/servizi/{servizio_id}")
async def get_servizio(servizio_id: str, user: dict = Depends(get_current_user)):
    s = await get_scoped_servizio(servizio_id, user)
    names = await clients_name_map([s["client_id"]])
    client_doc = await db.clients.find_one({"id": s["client_id"]}, {"_id": 0, "telefono": 1, "email": 1})
    out = serialize_servizio(s, names.get(s["client_id"], ""))
    out["client_contacts"] = client_doc or {}
    return out

@api_router.patch("/servizi/{servizio_id}")
async def update_servizio(servizio_id: str, input: ServizioInput, user: dict = Depends(get_current_user)):
    old = await get_scoped_servizio(servizio_id, user)
    data = input.model_dump(exclude_unset=True)
    if user["role"] == "negozio":
        data.pop("venditore_id", None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if data.get("pagato") and not old.get("pagato"):
        data["last_payment_date"] = date.today().isoformat()
    await db.servizi.update_one({"id": servizio_id}, {"$set": data})
    updated = await db.servizi.find_one({"id": servizio_id}, {"_id": 0})
    names = await clients_name_map([updated["client_id"]])
    return serialize_servizio(updated, names.get(updated["client_id"], ""))

@api_router.delete("/servizi/{servizio_id}")
async def delete_servizio(servizio_id: str, admin: dict = Depends(require_admin)):
    res = await db.servizi.delete_one({"id": servizio_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Servizio non trovato")
    await db.attachments.update_many({"servizio_id": servizio_id}, {"$set": {"is_deleted": True}})
    return {"status": "ok"}

@api_router.post("/servizi/{servizio_id}/mark-paid")
async def mark_servizio_paid(servizio_id: str, user: dict = Depends(get_current_user)):
    await get_scoped_servizio(servizio_id, user)
    await db.servizi.update_one({"id": servizio_id},
                                {"$set": {"pagato": True, "last_payment_date": date.today().isoformat()}})
    return {"status": "ok"}

SVC_CATEGORIA = {"riparazione": ("TELEFONIA", "Riparazione"), "accessori": ("TELEFONIA", "Accessori"),
                 "vendita": ("TELEFONIA", "Vendita"), "sim": ("SIM", None),
                 "internet": ("INTERNET", None), "fisso": ("INTERNET", None)}

async def register_privacy_servizio(client: dict, svc: dict, store_name: str) -> dict:
    cat, det = SVC_CATEGORIA.get(svc["tipo"], ("CambiaOra", "CambiaOra"))
    if det is None:
        op = (svc.get("operatore_tel") or "").strip().upper()
        allowed = SIM_OPERATORS if svc["tipo"] == "sim" else [o.upper() for o in INTERNET_OPERATORS]
        det = op if op in allowed else allowed[0]
    return await register_privacy_site(client, store_name, categoria=cat, dettaglio=det)

def review_message_for_store(store: Optional[dict]) -> Optional[str]:
    if not store or not store.get("review_link"):
        return None
    return (f"Ciao!\nGrazie per aver scelto RS Riparazioni {store['nome']}\n"
            "Se ti sei trovato bene, ci farebbe davvero piacere una tua recensione\n"
            f"Basta un clic qui\n{store['review_link']}\nGrazie per il supporto")

@api_router.post("/servizi/{servizio_id}/whatsapp/privacy")
async def whatsapp_privacy_servizio(servizio_id: str, user: dict = Depends(get_current_user)):
    svc = await get_scoped_servizio(servizio_id, user)
    client_doc = await db.clients.find_one({"id": svc["client_id"]}, {"_id": 0})
    if not client_doc or not client_doc.get("telefono"):
        raise HTTPException(status_code=400, detail="Il cliente non ha un numero di telefono")
    store = await db.stores.find_one({"id": svc.get("venditore_id")}, {"_id": 0})
    registered, reg_error = False, None
    if client_doc.get("email"):
        try:
            await register_privacy_servizio(client_doc, svc, (store or {}).get("nome", ""))
            registered = True
        except Exception as e:
            reg_error = getattr(e, "detail", str(e))
            logger.error(f"Registrazione privacy sito fallita per servizio {servizio_id}: {reg_error}")
    wa_error = None
    try:
        await wa_send(client_doc["telefono"], PRIVACY_MSG.format(nome=client_doc.get("nome", "")), session=client_doc.get("venditore_id") or "default")
    except Exception as e:
        wa_error = getattr(e, "detail", str(e))
    if wa_error and not registered:
        raise HTTPException(status_code=502, detail=f"WhatsApp: {wa_error}")
    now = datetime.now(timezone.utc)
    updates = {}
    review_queued = False
    if not wa_error:
        updates["privacy_msg_sent_at"] = now.isoformat()
        review_msg = review_message_for_store(store)
        if review_msg:
            await db.whatsapp_queue.insert_one({
                "id": str(uuid.uuid4()), "client_id": svc["client_id"], "servizio_id": servizio_id,
                "phone": client_doc["telefono"], "type": "review", "message": review_msg,
                "send_after": (now + timedelta(minutes=5)).isoformat(), "sent": False,
                "created_at": now.isoformat()})
            review_queued = True
    if registered:
        updates["privacy_firmata"] = True
        updates["privacy_registered_at"] = now.isoformat()
    if updates:
        await db.servizi.update_one({"id": servizio_id}, {"$set": updates})
        await db.clients.update_one({"id": svc["client_id"]},
                                    {"$set": {"privacy_firmata": True}} if registered else {"$set": {}})
    return {"status": "ok", "privacy_registered": registered, "registration_error": reg_error,
            "wa_error": wa_error, "review_queued": review_queued}

@api_router.post("/servizi/{servizio_id}/attachments")
async def upload_servizio_attachment(servizio_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    await get_scoped_servizio(servizio_id, user)
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    if ext not in ("pdf", "jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Formato non supportato (PDF, JPG, PNG, WEBP)")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 15 MB)")
    path = f"{APP_NAME}/servizi/{servizio_id}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    doc = {"id": str(uuid.uuid4()), "servizio_id": servizio_id, "storage_path": result["path"],
           "original_filename": file.filename, "content_type": file.content_type,
           "size": result["size"], "is_deleted": False, "uploaded_by": user["id"],
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.attachments.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/servizi/{servizio_id}/attachments")
async def list_servizio_attachments(servizio_id: str, user: dict = Depends(get_current_user)):
    await get_scoped_servizio(servizio_id, user)
    return await db.attachments.find({"servizio_id": servizio_id, "is_deleted": False}, {"_id": 0}).to_list(200)

@api_router.get("/clients/{client_id}/servizi")
async def client_servizi(client_id: str, user: dict = Depends(get_current_user)):
    await get_scoped_client(client_id, user)
    servizi = await db.servizi.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [serialize_servizio(s) for s in servizi]

@api_router.get("/vincoli")
async def report_vincoli(user: dict = Depends(get_current_user), giorni: int = 90):
    if "telefonia" not in user_sections(user):
        raise HTTPException(status_code=403, detail="Sezione non abilitata")
    scope = servizio_scope(user)
    scope["vincolo_mesi"] = {"$nin": [None, 0]}
    scope["data_attivazione"] = {"$ne": None}
    servizi = await db.servizi.find(scope, {"_id": 0}).to_list(5000)
    names = await clients_name_map(list({s["client_id"] for s in servizi}))
    out = []
    for s in servizi:
        ser = serialize_servizio(s, names.get(s["client_id"], ""))
        if ser.get("giorni_alla_scadenza") is not None and ser["giorni_alla_scadenza"] <= giorni:
            out.append(ser)
    out.sort(key=lambda x: x["giorni_alla_scadenza"])
    return out

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

@api_router.post("/cron/whatsapp-due")
async def cron_whatsapp_due(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not token or not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(process_whatsapp_queue)
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

SEED_CLIENT_SAMPLES = [
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

async def _seed_indexes():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.clients.create_index("venditore_id")
    await db.clients.create_index("lavorazione")
    await db.lavorazioni_log.create_index("operatore_id")

async def _seed_admin():
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

async def _seed_stores():
    if await db.stores.count_documents({}) == 0:
        for s in SEED_STORES:
            await db.stores.insert_one({"id": str(uuid.uuid4()), **s, "note": "", "pagato": False,
                                        "last_payment_date": None,
                                        "created_at": datetime.now(timezone.utc).isoformat()})

async def _seed_users():
    stores = {s["nome"]: s["id"] for s in await db.stores.find({}, {"_id": 0}).to_list(100)}
    for su in SEED_USERS:
        if not await db.users.find_one({"email": su["email"]}):
            await db.users.insert_one({"id": str(uuid.uuid4()), "name": su["name"], "email": su["email"],
                                       "password_hash": hash_password(su["password"]), "role": su["role"],
                                       "store_ids": [stores[n] for n in su["stores"] if n in stores],
                                       "can_view_all": su["can_view_all"], "active": True,
                                       "created_at": datetime.now(timezone.utc).isoformat()})

def _sample_client_doc(nome, cognome, tipo_c, bolletta, forn, lav, store_id, dc, pagato, last_pay, op_id, now):
    return {"id": str(uuid.uuid4()), "nome": nome, "cognome": cognome, "tipo_cliente": tipo_c,
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
            "venditore_id": store_id, "operatore_id": op_id,
            "pagato": pagato, "last_payment_date": last_pay,
            "created_by": op_id, "created_at": now, "updated_at": now}

async def _seed_clients():
    if await db.clients.count_documents({}) > 0:
        return
    deborah = await db.users.find_one({"email": "deborah@cambiaora.local"}, {"_id": 0})
    op_id = deborah["id"] if deborah else ""
    stores = {s["nome"]: s["id"] for s in await db.stores.find({}, {"_id": 0}).to_list(100)}
    today = date.today()
    now = datetime.now(timezone.utc).isoformat()
    for nome, cognome, tipo_c, bolletta, forn, lav, store_name, mesi_fa, pagato, pag_mesi_fa in SEED_CLIENT_SAMPLES:
        dc = today - relativedelta(months=mesi_fa)
        last_pay = (today - relativedelta(months=pag_mesi_fa)).isoformat() if pag_mesi_fa is not None else None
        doc = _sample_client_doc(nome, cognome, tipo_c, bolletta, forn, lav,
                                 stores.get(store_name, ""), dc, pagato, last_pay, op_id, now)
        await db.clients.insert_one(doc)
        await db.lavorazioni_log.insert_one({
            "id": str(uuid.uuid4()), "client_id": doc["id"],
            "client_name": f"{cognome} {nome}", "operatore_id": op_id,
            "operatore_name": "Deborah", "status": lav, "note": "Cliente inserito",
            "created_at": now})

async def _seed_stores_v2():
    if not await db.stores.find_one({"nome": "Morbegno"}):
        await db.stores.insert_one({"id": str(uuid.uuid4()), "nome": "Morbegno", "referente": "",
                                    "tipo": "negozio", "note": "", "review_link": "", "pagato": False,
                                    "last_payment_date": None,
                                    "created_at": datetime.now(timezone.utc).isoformat()})
    review_links = {"Tirano": "https://g.page/r/CQedddebLpxpEAE/review",
                    "Sondrio": "https://g.page/r/CeQBdxW0AtlqEAE/review",
                    "Gravedona": "https://g.page/r/CWOpR0o29GE-EAE/review",
                    "Morbegno": "https://g.page/r/CT15UUSXSQoCEAE/review"}
    for nome, link in review_links.items():
        await db.stores.update_one({"nome": nome, "$or": [{"review_link": {"$exists": False}}, {"review_link": ""}]},
                                   {"$set": {"review_link": link}})

async def _seed_user_sections():
    await db.users.update_many({"sections": {"$exists": False}},
                               {"$set": {"sections": ["energia", "riparazioni", "telefonia"]}})

async def seed_data():
    await _seed_indexes()
    await _seed_admin()
    await _seed_stores()
    await _seed_users()
    if os.environ.get("ENVIRONMENT", "production") == "development":
        await _seed_clients()
    await _seed_stores_v2()
    await _seed_user_sections()

@app.on_event("startup")
async def startup():
    await seed_data()
    try:
        init_storage()
        logger.info("Object storage inizializzato")
    except Exception as e:
        logger.error(f"Storage init fallito: {e}")

app.include_router(api_router)

cors_origins = os.environ.get("CORS_ORIGINS", "*")
allow_origins = ["*"] if cors_origins == "*" else [o.strip() for o in cors_origins.split(",")]
extra_origins = [os.environ.get("FRONTEND_URL", ""), "http://localhost:3000"]
for o in extra_origins:
    if o and o not in allow_origins and allow_origins != ["*"]:
        allow_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=allow_origins != ["*"],
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
