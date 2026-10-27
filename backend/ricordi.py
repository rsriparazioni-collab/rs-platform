import re
import uuid
from datetime import datetime, timezone, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}
CF_MESI = "ABCDEHLMPRST"
CF_RE = re.compile(r"^[A-Z]{6}(\d{2})([A-Z])(\d{2})[A-Z]\d{3}[A-Z]$")


def setup(**deps):
    _d.update(deps)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _now():
    return datetime.now(timezone.utc)


def nascita_da_cf(cf: str):
    m = CF_RE.match((cf or "").strip().upper())
    if not m:
        return None
    yy, mese, gg = int(m.group(1)), CF_MESI.find(m.group(2)), int(m.group(3))
    if mese < 0:
        return None
    gg = gg - 40 if gg > 40 else gg
    anno = 2000 + yy if yy <= date.today().year % 100 else 1900 + yy
    try:
        return date(anno, mese + 1, gg).isoformat()
    except ValueError:
        return None


def _data_nascita(c: dict):
    return c.get("data_nascita") or nascita_da_cf(c.get("codice_fiscale", ""))


async def _cliente(client_id: str, user: dict) -> dict:
    c = await _d["db"].clients.find_one({**_d["client_scope_filter"](user), "id": client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return c


@router.get("/clients/{client_id}/ricordi")
async def ricordi_list(client_id: str, user: dict = Depends(_current_user)):
    c = await _cliente(client_id, user)
    items = await _d["db"].client_ricordi.find({"client_id": client_id}, {"_id": 0}).sort("at", -1).to_list(100)
    return {"ricordi": items, "data_nascita": _data_nascita(c), "nascita_da_cf": not c.get("data_nascita") and bool(nascita_da_cf(c.get("codice_fiscale", "")))}


class RicordoInput(BaseModel):
    testo: str


@router.post("/clients/{client_id}/ricordi")
async def ricordi_add(client_id: str, input: RicordoInput, user: dict = Depends(_current_user)):
    await _cliente(client_id, user)
    testo = input.testo.strip()
    if not testo:
        raise HTTPException(status_code=400, detail="Testo vuoto")
    doc = {"id": str(uuid.uuid4()), "client_id": client_id, "testo": testo[:200], "da": user["name"], "da_id": user["id"], "at": _now().isoformat()}
    await _d["db"].client_ricordi.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/clients/{client_id}/ricordi/{ricordo_id}")
async def ricordi_delete(client_id: str, ricordo_id: str, user: dict = Depends(_current_user)):
    await _cliente(client_id, user)
    res = await _d["db"].client_ricordi.delete_one({"id": ricordo_id, "client_id": client_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Ricordo non trovato")
    return {"status": "ok"}


@router.get("/ricordi/preview")
async def ricordi_preview(ids: str = "", user: dict = Depends(_current_user)):
    """Per le liste: {client_id: [testi...]} per gli id richiesti (max 300)."""
    lista = [i for i in ids.split(",") if i][:300]
    if not lista:
        return {}
    out: dict = {}
    async for r in _d["db"].client_ricordi.find({"client_id": {"$in": lista}}, {"_id": 0, "client_id": 1, "testo": 1}).sort("at", -1):
        out.setdefault(r["client_id"], []).append(r["testo"])
    return out


def _persona_key(c: dict) -> str:
    return (c.get("codice_fiscale") or "").strip().upper() or (c.get("telefono") or "").strip() or c["id"]


def _prossimo_compleanno(nascita: str, oggi: date):
    try:
        d = date.fromisoformat(nascita)
    except ValueError:
        return None, None
    for anno in (oggi.year, oggi.year + 1):
        try:
            prox = d.replace(year=anno)
        except ValueError:
            prox = date(anno, 3, 1)
        if prox >= oggi:
            return prox, anno - d.year
    return None, None


@router.get("/ricordi/compleanni")
async def compleanni(giorni: int = 7, user: dict = Depends(_current_user)):
    db = _d["db"]
    oggi = date.today()
    out, visti = [], set()
    nomi_store = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    proj = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "data_nascita": 1, "codice_fiscale": 1, "auguri_anno": 1}
    async for c in db.clients.find({**_d["client_scope_filter"](user), "anonimizzato_at": {"$in": [None]}}, proj):
        n = _data_nascita(c)
        if not n:
            continue
        prox, eta = _prossimo_compleanno(n, oggi)
        if prox and (prox - oggi).days <= giorni and _persona_key(c) not in visti:
            visti.add(_persona_key(c))
            out.append({"id": c["id"], "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "telefono": c.get("telefono", ""),
                        "negozio": nomi_store.get(c.get("venditore_id"), "-"), "data": prox.isoformat(), "oggi": prox == oggi, "eta": eta,
                        "auguri_inviati": c.get("auguri_anno") == oggi.year})
    return sorted(out, key=lambda x: (x["data"], x["client_name"]))


async def invia_auguri() -> dict:
    """Cron 09:00: auguri WhatsApp dal numero del negozio ai clienti che compiono gli anni oggi (una volta l'anno)."""
    db = _d["db"]
    oggi = date.today()
    stores = {s["id"]: s async for s in db.stores.find({}, {"_id": 0})}
    inviati, errori = [], []
    visti = {_persona_key(c) async for c in db.clients.find({"auguri_anno": oggi.year}, {"_id": 0, "id": 1, "codice_fiscale": 1, "telefono": 1})}
    proj = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "data_nascita": 1, "codice_fiscale": 1, "auguri_anno": 1, "no_recensioni": 1}
    async for c in db.clients.find({"anonimizzato_at": {"$in": [None]}, "telefono": {"$nin": [None, ""]}, "no_recensioni": {"$ne": True},
                                    "auguri_anno": {"$ne": oggi.year}}, proj):
        n = _data_nascita(c)
        if not n:
            continue
        prox, _ = _prossimo_compleanno(n, oggi)
        if prox != oggi or _persona_key(c) in visti:
            continue
        visti.add(_persona_key(c))
        store = stores.get(c.get("venditore_id"))
        msg = _d["store_msg"](store, "msg_compleanno", nome=c.get("nome", ""), cognome=c.get("cognome", ""))
        try:
            await _d["wa_send"](c["telefono"], msg, session=c.get("venditore_id") or "default", tipo="compleanno", client_id=c["id"])
            stessa_persona = {"$or": [{"id": c["id"]}] + ([{"codice_fiscale": c["codice_fiscale"]}] if c.get("codice_fiscale") else []) + [{"telefono": c["telefono"]}]}
            await db.clients.update_many(stessa_persona, {"$set": {"auguri_anno": oggi.year, "auguri_sent_at": _now().isoformat()}})
            inviati.append(c["id"])
        except Exception as e:
            errori.append({"client_id": c["id"], "error": str(getattr(e, "detail", e))})
    await db.cron_log.update_one({"job": "auguri-compleanno"}, {"$set": {"last_run": _now().isoformat(), "inviati": len(inviati), "errori": errori[:50]}}, upsert=True)
    return {"inviati": len(inviati), "errori": len(errori)}


@router.post("/ricordi/compleanni/invia-ora")
async def invia_auguri_ora(user: dict = Depends(_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return await invia_auguri()


@router.get("/ricordi/compleanni/stato")
async def compleanni_stato(user: dict = Depends(_current_user)):
    db = _d["db"]
    tot = await db.clients.count_documents({"anonimizzato_at": {"$in": [None]}})
    con_data = await db.clients.count_documents({"anonimizzato_at": {"$in": [None]}, "data_nascita": {"$nin": [None, ""]}})
    con_cf = 0
    async for c in db.clients.find({"anonimizzato_at": {"$in": [None]}, "data_nascita": {"$in": [None, ""]}, "codice_fiscale": {"$nin": [None, ""]}}, {"_id": 0, "codice_fiscale": 1}):
        con_cf += 1 if nascita_da_cf(c["codice_fiscale"]) else 0
    log = await db.cron_log.find_one({"job": "auguri-compleanno"}, {"_id": 0})
    return {"clienti": tot, "con_data_nascita": con_data, "da_codice_fiscale": con_cf, "senza": tot - con_data - con_cf, "ultimo_invio": log,
            "domani_in_scadenza": (date.today() + timedelta(days=1)).isoformat()}
