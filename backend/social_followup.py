import asyncio
import random
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}

KEY = "social_followup"
GIORNI_ATTESA = 7

DEFAULTS = {
    "msg_cambiaora": ("Ciao {nome}, siamo CambiaOra 👋\n"
                      "Sono passati pochi giorni dall'attivazione del tuo contratto: speriamo sia andato tutto bene!\n"
                      "Se ti va, seguici su Instagram: troverai consigli per risparmiare in bolletta, novità e promozioni riservate ai clienti 👇\n"
                      "https://www.instagram.com/cambiaora.store\n"
                      "Grazie per averci scelto, per qualsiasi dubbio siamo qui."),
    "msg_rs": ("Ciao {nome}, siamo RS Riparazioni 👋\n"
               "È passata una settimana dal tuo passaggio da noi: speriamo che tutto funzioni alla perfezione!\n"
               "Se ti fa piacere, seguici sui social per promozioni, accessori e consigli utili 👇\n"
               "Instagram: https://www.instagram.com/rs_riparazioni\n"
               "Facebook: https://www.facebook.com/share/19WLUP2BAn/\n"
               "Grazie per la fiducia, a presto!"),
}


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


class SettingsInput(BaseModel):
    attivo: Optional[bool] = None
    per_giorno: Optional[int] = None
    msg_cambiaora: Optional[str] = None
    msg_rs: Optional[str] = None


async def _settings() -> dict:
    doc = await _d["db"].settings.find_one({"key": KEY}, {"_id": 0}) or {}
    v = doc.get("value") or {}
    return {"attivo": bool(v.get("attivo", False)), "per_giorno": int(v.get("per_giorno") or 5),
            "msg_cambiaora": v.get("msg_cambiaora") or DEFAULTS["msg_cambiaora"], "msg_rs": v.get("msg_rs") or DEFAULTS["msg_rs"]}


def _tel(c: dict) -> str:
    t = "".join(ch for ch in (c.get("telefono") or "") if ch.isdigit())
    return t[-10:] if len(t) >= 10 else t


def _data(v) -> Optional[str]:
    return (v or "")[:10] or None


async def _gia_inviati(marchio: str) -> set:
    return {r["tel"] async for r in _d["db"].social_followup_log.find({"marchio": marchio, "ok": True}, {"_id": 0, "tel": 1})}


async def _candidati_cambiaora(limite: str) -> list:
    db = _d["db"]
    out = []
    f = {"gestione": {"$ne": "enel"}, "data_contratto": {"$nin": [None, ""], "$lte": limite}, "telefono": {"$nin": [None, ""]},
         "anonimizzato_at": {"$in": [None]}, "no_recensioni": {"$ne": True}}
    async for c in db.clients.find(f, {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "data_contratto": 1,
                                       "gestione": 1, "pod": 1, "pdr": 1, "fornitore_provenienza": 1, "nuovo_fornitore": 1, "origine": 1}):
        out.append((c["data_contratto"][:10], c))
    return out


async def _candidati_rs(limite: str) -> list:
    db = _d["db"]
    date_per_cliente: dict = {}

    def segna(cid, d):
        if cid and d and d <= limite and (cid not in date_per_cliente or d < date_per_cliente[cid]):
            date_per_cliente[cid] = d

    async for s in db.servizi.find({"client_id": {"$nin": [None, ""]}, "tipo": {"$in": ["riparazione", "sim", "internet", "fisso", "accessori", "vendita"]}},
                                   {"_id": 0, "client_id": 1, "tipo": 1, "stato": 1, "data_uscita": 1, "created_at": 1}):
        if s["tipo"] == "riparazione":
            if s.get("stato") != "consegnato":
                continue
            segna(s["client_id"], _data(s.get("data_uscita")) or _data(s.get("created_at")))
        else:
            segna(s["client_id"], _data(s.get("created_at")))
    async for v in db.vendite.find({"client_id": {"$nin": [None, ""]}}, {"_id": 0, "client_id": 1, "created_at": 1, "data": 1}):
        segna(v["client_id"], _data(v.get("data")) or _data(v.get("created_at")))
    async for r in db.ritiri.find({"client_id": {"$nin": [None, ""]}}, {"_id": 0, "client_id": 1, "created_at": 1}):
        segna(r["client_id"], _data(r.get("created_at")))
    async for c in db.clients.find({"gestione": "enel"}, {"_id": 0, "id": 1, "data_contratto": 1, "created_at": 1}):
        segna(c["id"], _data(c.get("data_contratto")) or _data(c.get("created_at")))

    out = []
    if not date_per_cliente:
        return out
    f = {"id": {"$in": list(date_per_cliente)}, "telefono": {"$nin": [None, ""]}, "anonimizzato_at": {"$in": [None]}, "no_recensioni": {"$ne": True}}
    async for c in db.clients.find(f, {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "gestione": 1, "data_contratto": 1,
                                       "pod": 1, "pdr": 1, "fornitore_provenienza": 1, "nuovo_fornitore": 1, "origine": 1}):
        out.append((date_per_cliente[c["id"]], c))
    return out


async def _coda(marchio: str) -> list:
    limite = (date.today() - timedelta(days=GIORNI_ATTESA)).isoformat()
    cand = await (_candidati_cambiaora(limite) if marchio == "cambiaora" else _candidati_rs(limite))
    fatti = await _gia_inviati(marchio)
    visti, out = set(), []
    for d, c in sorted(cand, key=lambda x: x[0]):
        t = _tel(c)
        if not t or t in fatti or t in visti:
            continue
        visti.add(t)
        out.append((d, c))
    return out


async def _invia_uno(marchio: str, c: dict, tpl: str) -> dict:
    sess = await _d["wa_session_cliente"](c)
    try:
        msg = tpl.format(nome=c.get("nome", ""), cognome=c.get("cognome", ""))
    except (KeyError, IndexError, ValueError):
        msg = tpl
    log = {"id": str(uuid.uuid4()), "marchio": marchio, "client_id": c["id"], "tel": _tel(c), "session": sess,
           "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "at": _now().isoformat(), "ok": False, "error": None}
    try:
        await _d["wa_send"](c["telefono"], msg, session=sess, tipo=f"social_{marchio}", client_id=c["id"])
        log["ok"] = True
    except Exception as e:
        log["error"] = str(getattr(e, "detail", e))
    await _d["db"].social_followup_log.insert_one(log)
    return log


async def invia_giornaliero(forza: bool = False, distanzia: bool = True) -> dict:
    """Cron 10:00: N messaggi 'seguici sui social' per marchio, dai più vecchi, una sola volta per numero."""
    db = _d["db"]
    st = await _settings()
    if not st["attivo"] and not forza:
        return {"skipped": "spento"}
    esito = {}
    for marchio, tpl in (("cambiaora", st["msg_cambiaora"]), ("rs", st["msg_rs"])):
        coda = await _coda(marchio)
        inviati, errori = 0, 0
        for i, (_, c) in enumerate(coda[: st["per_giorno"]]):
            if distanzia and i:
                await asyncio.sleep(random.randint(90, 240))
            log = await _invia_uno(marchio, c, tpl)
            inviati += log["ok"]
            errori += not log["ok"]
        esito[marchio] = {"inviati": inviati, "errori": errori, "in_coda": max(len(coda) - inviati, 0)}
    await db.cron_log.update_one({"job": "social-followup"}, {"$set": {"last_run": _now().isoformat(), "esito": esito}}, upsert=True)
    return esito


def _admin(user: dict):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


@router.get("/social-followup")
async def stato(user: dict = Depends(_current_user)):
    _admin(user)
    st = await _settings()
    code = {m: await _coda(m) for m in ("cambiaora", "rs")}
    ultimi = await _d["db"].social_followup_log.find({}, {"_id": 0}).sort("at", -1).to_list(20)
    cron = await _d["db"].cron_log.find_one({"job": "social-followup"}, {"_id": 0})
    return {"settings": st, "defaults": DEFAULTS,
            "in_coda": {m: len(v) for m, v in code.items()},
            "prossimi": {m: [{"client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "data": d} for d, c in v[: st["per_giorno"]]] for m, v in code.items()},
            "ultimi": ultimi, "ultimo_giro": cron}


@router.put("/social-followup")
async def salva(body: SettingsInput, user: dict = Depends(_current_user)):
    _admin(user)
    cur = await _settings()
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "per_giorno" in upd:
        upd["per_giorno"] = max(1, min(int(upd["per_giorno"]), 10))
    await _d["db"].settings.update_one({"key": KEY}, {"$set": {"value": {**cur, **upd}}}, upsert=True)
    return {"settings": await _settings()}


@router.post("/social-followup/invia-ora")
async def invia_ora(user: dict = Depends(_current_user)):
    _admin(user)
    return await invia_giornaliero(forza=True, distanzia=False)
