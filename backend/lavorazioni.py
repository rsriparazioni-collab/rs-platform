import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}

DA_LAVORARE = ["", "da_quotare", "in_quotazione", "quotato", "richieste_bollette", "in_attesa_ok",
               "attesa_documenti", "contattare_cliente", "cambiare", "passa_in_negozio"]
LAVORATE = ["cambio_effettuato", "rinnovato"]
DA_REINSERIRE = ["problema_tecnico", "annullato"]
VERIFICA_ESITO = ["cambiare", "in_attesa_ok", "attesa_documenti"]
GIORNI_VERIFICA = 30


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


def _days(iso: Optional[str]) -> int:
    if not iso:
        return 0
    try:
        return max(0, min((_now() - datetime.fromisoformat(iso)).days, 999))
    except Exception:
        return 0


def _semaforo(giorni: int) -> str:
    return "rosso" if giorni > 7 else "giallo" if giorni > 3 else "verde"


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def _cfg() -> dict:
    doc = await _d["db"].settings.find_one({"key": "lavorazioni_cfg"}, {"_id": 0})
    return (doc or {}).get("value") or {"addetti": []}


async def _is_addetto(user: dict) -> bool:
    return user["role"] == "admin" or user["id"] in (await _cfg()).get("addetti", [])


async def require_addetto(user: dict = Depends(_current_user)):
    if not await _is_addetto(user):
        raise HTTPException(status_code=403, detail="Sezione riservata agli addetti lavorazioni")
    return user


async def require_admin(user: dict = Depends(_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


@router.get("/lavorazioni/accesso")
async def accesso(user: dict = Depends(_current_user)):
    return {"abilitato": await _is_addetto(user), "admin": user["role"] == "admin"}


@router.get("/lavorazioni/addetti")
async def addetti_list(admin: dict = Depends(require_admin)):
    cfg = await _cfg()
    users = await _d["db"].users.find({"attivo": {"$ne": False}, "role": {"$ne": "admin"}},
                                      {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "telefono": 1}).sort("name", 1).to_list(200)
    return {"addetti": cfg.get("addetti", []), "utenti": users}


class AddettiInput(BaseModel):
    addetti: list[str]


@router.put("/lavorazioni/addetti")
async def addetti_put(input: AddettiInput, admin: dict = Depends(require_admin)):
    ids = [u["id"] async for u in _d["db"].users.find({"id": {"$in": input.addetti}}, {"_id": 0, "id": 1})]
    await _d["db"].settings.update_one({"key": "lavorazioni_cfg"}, {"$set": {"value": {"addetti": ids}}}, upsert=True)
    return {"addetti": ids}


async def _ultimo_cambio(client_ids: list) -> dict:
    out = {}
    cur = _d["db"].lavorazioni_log.aggregate([{"$match": {"client_id": {"$in": client_ids}}}, {"$sort": {"created_at": 1}},
                                              {"$group": {"_id": "$client_id", "at": {"$max": "$created_at"},
                                                          "note": {"$push": {"$cond": [{"$eq": ["$status", "nota"]}, {"n": "$note", "da": "$operatore_name", "at": "$created_at"}, None]}}}}])
    async for r in cur:
        note = [n for n in r["note"] if n]
        out[r["_id"]] = {"at": r["at"], "nota": note[-1] if note else None}
    return out


def _riga(c: dict, nomi_store: dict, ultimo: dict) -> dict:
    u = ultimo.get(c["id"]) or {}
    rif = u.get("at") or c.get("updated_at") or c.get("created_at")
    giorni = _days(rif)
    lav = c.get("lavorazione") or "da_quotare"
    return {"id": c["id"], "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "telefono": c.get("telefono", ""),
            "store_id": c.get("venditore_id", ""), "negozio": nomi_store.get(c.get("venditore_id"), "-"),
            "gestione": c.get("gestione") or "cambiaora", "tipo_bolletta": c.get("tipo_bolletta", ""), "lavorazione": lav,
            "ultimo_cambio": rif, "giorni_fermo": giorni, "semaforo": _semaforo(giorni),
            "presa_in_carico_nome": c.get("presa_in_carico_nome", ""), "presa_in_carico_da": c.get("presa_in_carico_da", ""),
            "presa_in_carico_at": c.get("presa_in_carico_at"), "reinserimenti": int(c.get("reinserimenti") or 0),
            "ultima_nota": u.get("nota"), "verifica_esito": lav in VERIFICA_ESITO and giorni >= GIORNI_VERIFICA}


async def _clienti_energia(scope: dict, extra: dict) -> list:
    db = _d["db"]
    proj = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "gestione": 1, "tipo_bolletta": 1,
            "lavorazione": 1, "updated_at": 1, "created_at": 1, "presa_in_carico_nome": 1, "presa_in_carico_da": 1,
            "presa_in_carico_at": 1, "reinserimenti": 1, "data_contratto": 1, "pod": 1, "pdr": 1,
            "fornitore_provenienza": 1, "nuovo_fornitore": 1, "origine": 1}
    docs = await db.clients.find({**scope, **extra, "anonimizzato_at": {"$in": [None]}}, proj).to_list(5000)
    return [c for c in docs if _d["cliente_energia"](c)]


@router.get("/lavorazioni/riepilogo")
async def riepilogo(store_id: str = "", giorni_lavorate: int = 60, user: dict = Depends(require_addetto)):
    db = _d["db"]
    scope = _d["client_scope_filter"](user)
    if store_id:
        scope["venditore_id"] = store_id
    nomi_store = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    limite = (_now() - timedelta(days=giorni_lavorate)).isoformat()
    aperti = await _clienti_energia(scope, {"lavorazione": {"$in": DA_LAVORARE + DA_REINSERIRE}})
    lavorate_docs = await _clienti_energia(scope, {"lavorazione": {"$in": LAVORATE}, "updated_at": {"$gte": limite}})
    tutti = aperti + lavorate_docs
    ultimo = await _ultimo_cambio([c["id"] for c in tutti])
    righe = [_riga(c, nomi_store, ultimo) for c in tutti]
    da_lavorare = sorted([r for r in righe if r["lavorazione"] in DA_LAVORARE], key=lambda r: -r["giorni_fermo"])
    da_reinserire = sorted([r for r in righe if r["lavorazione"] in DA_REINSERIRE], key=lambda r: -r["giorni_fermo"])
    lavorate = sorted([r for r in righe if r["lavorazione"] in LAVORATE], key=lambda r: r["ultimo_cambio"] or "", reverse=True)
    negozi = {}
    for r in righe:
        n = negozi.setdefault(r["store_id"], {"store_id": r["store_id"], "nome": r["negozio"], "da_lavorare": 0, "lavorate": 0,
                                               "da_reinserire": 0, "ferme": 0, "senza_presa": 0})
        if r["lavorazione"] in LAVORATE:
            n["lavorate"] += 1
            continue
        chiave = "da_reinserire" if r["lavorazione"] in DA_REINSERIRE else "da_lavorare"
        n[chiave] += 1
        if r["semaforo"] == "rosso":
            n["ferme"] += 1
        if not r["presa_in_carico_da"]:
            n["senza_presa"] += 1
    oggi = date.today().isoformat()
    agenda = await db.agenda_lavorazioni.find({"user_id": user["id"], "fatto": False, "data": {"$lte": oggi}}, {"_id": 0}).sort("data", 1).to_list(500)
    return {"negozi": sorted(negozi.values(), key=lambda n: n["nome"]), "da_lavorare": da_lavorare, "lavorate": lavorate,
            "da_reinserire": da_reinserire, "verifica_esito": [r for r in da_lavorare if r["verifica_esito"]],
            "agenda_scadute": agenda, "oggi": oggi,
            "totali": {"da_lavorare": len(da_lavorare), "lavorate": len(lavorate), "da_reinserire": len(da_reinserire),
                       "ferme": sum(1 for r in da_lavorare + da_reinserire if r["semaforo"] == "rosso"),
                       "verifica_esito": sum(1 for r in da_lavorare if r["verifica_esito"]), "agenda_scadute": len(agenda)}}


class PresaInput(BaseModel):
    attiva: bool = True


@router.post("/lavorazioni/{client_id}/presa-in-carico")
async def presa_in_carico(client_id: str, input: PresaInput, user: dict = Depends(require_addetto)):
    db = _d["db"]
    c = await db.clients.find_one({**_d["client_scope_filter"](user), "id": client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    if input.attiva:
        if c.get("presa_in_carico_da") and c["presa_in_carico_da"] != user["id"] and user["role"] != "admin":
            raise HTTPException(status_code=409, detail=f"Già in carico a {c.get('presa_in_carico_nome')}")
        upd = {"$set": {"presa_in_carico_da": user["id"], "presa_in_carico_nome": user["name"], "presa_in_carico_at": _now().isoformat()}}
    else:
        upd = {"$unset": {"presa_in_carico_da": "", "presa_in_carico_nome": "", "presa_in_carico_at": ""}}
    await db.clients.update_one({"id": client_id}, upd)
    await _d["log_lavorazione"](c, user, c.get("lavorazione", ""), "Presa in carico" if input.attiva else "Rilasciata presa in carico")
    return {"status": "ok"}


class NotaInput(BaseModel):
    nota: str


@router.post("/lavorazioni/{client_id}/nota")
async def nota_rapida(client_id: str, input: NotaInput, user: dict = Depends(require_addetto)):
    if not input.nota.strip():
        raise HTTPException(status_code=400, detail="Nota vuota")
    c = await _d["db"].clients.find_one({**_d["client_scope_filter"](user), "id": client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    await _d["log_lavorazione"](c, user, "nota", input.nota.strip())
    return {"status": "ok"}


@router.get("/lavorazioni/storico-settimanale")
async def storico_settimanale(settimane: int = 8, user: dict = Depends(require_addetto)):
    """Pratiche chiuse (cambio effettuato / rinnovato) per settimana ISO, negozio e operatore."""
    db = _d["db"]
    settimane = max(1, min(settimane, 52))
    oggi = date.today()
    lunedi = oggi - timedelta(days=oggi.weekday())
    inizio = lunedi - timedelta(weeks=settimane - 1)
    logs = await db.lavorazioni_log.find({"status": {"$in": LAVORATE}, "created_at": {"$gte": inizio.isoformat()}},
                                         {"_id": 0, "client_id": 1, "operatore_name": 1, "created_at": 1}).to_list(20000)
    scope = _d["client_scope_filter"](user)
    cids = list({l["client_id"] for l in logs})
    store_of = {c["id"]: c.get("venditore_id", "") async for c in db.clients.find({**scope, "id": {"$in": cids}}, {"_id": 0, "id": 1, "venditore_id": 1})}
    nomi_store = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    sett = [(inizio + timedelta(weeks=i)) for i in range(settimane)]
    righe = {w.isoformat(): {"settimana": w.isoformat(), "fine": (w + timedelta(days=6)).isoformat(), "negozi": {}, "operatori": {}, "totale": 0} for w in sett}
    visti = set()
    for l in logs:
        if l["client_id"] not in store_of:
            continue
        d = datetime.fromisoformat(l["created_at"]).date()
        key = (l["client_id"], d.isocalendar()[:2])
        if key in visti:
            continue
        visti.add(key)
        w = (d - timedelta(days=d.weekday())).isoformat()
        r = righe.get(w)
        if not r:
            continue
        st = nomi_store.get(store_of[l["client_id"]], "-")
        r["negozi"][st] = r["negozi"].get(st, 0) + 1
        r["operatori"][l["operatore_name"]] = r["operatori"].get(l["operatore_name"], 0) + 1
        r["totale"] += 1
    negozi = sorted({n for r in righe.values() for n in r["negozi"]})
    operatori = sorted({o for r in righe.values() for o in r["operatori"]})
    return {"settimane": list(reversed(list(righe.values()))), "negozi": negozi, "operatori": operatori}


class ReinserisciInput(BaseModel):
    motivo: str = ""


@router.post("/lavorazioni/{client_id}/reinserisci")
async def reinserisci(client_id: str, input: ReinserisciInput, user: dict = Depends(require_addetto)):
    db = _d["db"]
    c = await db.clients.find_one({**_d["client_scope_filter"](user), "id": client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    if c.get("lavorazione") not in DA_REINSERIRE:
        raise HTTPException(status_code=400, detail="La pratica non è annullata né in problema tecnico")
    prec = c.get("lavorazione")
    await db.clients.update_one({"id": client_id}, {
        "$set": {"lavorazione": "da_quotare", "updated_at": _now().isoformat(), "reinserita_at": _now().isoformat(),
                 "presa_in_carico_da": user["id"], "presa_in_carico_nome": user["name"], "presa_in_carico_at": _now().isoformat()},
        "$inc": {"reinserimenti": 1}})
    await _d["log_lavorazione"](c, user, "da_quotare", f"Pratica reinserita (precedente: {prec}). {input.motivo.strip()}".strip())
    return {"status": "ok", "lavorazione": "da_quotare"}


class AgendaInput(BaseModel):
    client_id: str = ""
    data: str
    nota: str


@router.get("/lavorazioni/agenda")
async def agenda_list(da: str = "", a: str = "", solo_aperte: bool = False, user: dict = Depends(require_addetto)):
    q = {"user_id": user["id"]}
    if da or a:
        q["data"] = {k: v for k, v in (("$gte", da), ("$lte", a)) if v}
    if solo_aperte:
        q["fatto"] = False
    return await _d["db"].agenda_lavorazioni.find(q, {"_id": 0}).sort([("data", 1), ("created_at", 1)]).to_list(1000)


@router.post("/lavorazioni/agenda")
async def agenda_add(input: AgendaInput, user: dict = Depends(require_addetto)):
    db = _d["db"]
    try:
        date.fromisoformat(input.data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    if not input.nota.strip():
        raise HTTPException(status_code=400, detail="Nota obbligatoria")
    nome = ""
    if input.client_id:
        c = await db.clients.find_one({"id": input.client_id}, {"_id": 0, "nome": 1, "cognome": 1})
        nome = f"{(c or {}).get('cognome', '')} {(c or {}).get('nome', '')}".strip()
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "client_id": input.client_id, "client_name": nome,
           "data": input.data, "nota": input.nota.strip(), "fatto": False, "created_at": _now().isoformat()}
    await db.agenda_lavorazioni.insert_one(doc)
    doc.pop("_id", None)
    return doc


class AgendaFattoInput(BaseModel):
    fatto: bool = True


@router.patch("/lavorazioni/agenda/{item_id}")
async def agenda_fatto(item_id: str, input: AgendaFattoInput, user: dict = Depends(require_addetto)):
    res = await _d["db"].agenda_lavorazioni.update_one({"id": item_id, "user_id": user["id"]},
                                                       {"$set": {"fatto": input.fatto, "fatto_at": _now().isoformat() if input.fatto else None}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Voce agenda non trovata")
    return {"status": "ok"}


@router.delete("/lavorazioni/agenda/{item_id}")
async def agenda_delete(item_id: str, user: dict = Depends(require_addetto)):
    res = await _d["db"].agenda_lavorazioni.delete_one({"id": item_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Voce agenda non trovata")
    return {"status": "ok"}


async def riepilogo_mattutino() -> dict:
    """WhatsApp alle operatrici energia (ruolo operatore con telefono) con i conteggi del giorno."""
    db = _d["db"]
    inviati = []
    cfg = await _cfg()
    async for u in db.users.find({"id": {"$in": cfg.get("addetti", [])}, "attivo": {"$ne": False}, "telefono": {"$nin": [None, ""]}}, {"_id": 0}):
        r = await riepilogo(user=u)
        t = r["totali"]
        if not any(t.values()):
            continue
        righe = [f"Buongiorno {u['name']}! Riepilogo lavorazioni energia di oggi:",
                 f"• {t['da_lavorare']} da lavorare", f"• {t['da_reinserire']} da reinserire"]
        if t["ferme"]:
            righe.append(f"• {t['ferme']} ferme da più di 7 giorni ⚠️")
        if t["verifica_esito"]:
            righe.append(f"• {t['verifica_esito']} da verificare esito (oltre {GIORNI_VERIFICA} gg)")
        if t["agenda_scadute"]:
            righe.append(f"• {t['agenda_scadute']} promemoria in agenda per oggi")
        righe.append(f"Lavorate negli ultimi 60 gg: {t['lavorate']}. Buon lavoro!")
        sess = (u.get("store_ids") or ["default"])[0]
        try:
            await _d["wa_send"](u["telefono"], "\n".join(righe), session=sess, tipo="riepilogo_lavorazioni")
            inviati.append(u["name"])
        except Exception as e:
            await db.cron_log.insert_one({"job": "riepilogo-lavorazioni", "user": u["name"], "error": str(e), "at": _now().isoformat()})
    await db.cron_log.update_one({"job": "riepilogo-lavorazioni"}, {"$set": {"last_run": _now().isoformat(), "inviati": inviati}}, upsert=True)
    return {"inviati": inviati}
