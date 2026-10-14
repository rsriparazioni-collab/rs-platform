import asyncio
import logging
import os
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("contabilita")
router = APIRouter(prefix="/contabilita")
_d: dict = {}

MESI_IT = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
ROMA = ZoneInfo("Europe/Rome")


ACCESSI_DEFAULT = {"deborah@cambiaora.local": ["morbegno"]}


async def seed_accessi() -> None:
    """Imposta l'accesso contabilità di default (es. Deborah → Morbegno) se l'utente non ha ancora un override."""
    db = _d["db"]
    stores = {_slug(s["nome"]): s["id"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    for email, slugs in ACCESSI_DEFAULT.items():
        ids = [stores[s] for s in slugs if s in stores]
        if ids:
            r = await db.users.update_one({"email": email, "contabilita_store_ids": {"$exists": False}}, {"$set": {"contabilita_store_ids": ids}})
            if r.modified_count:
                logger.info("Accesso contabilità di default impostato per %s: %s", email, slugs)


async def invii_programmati_loop() -> None:
    """Fallback interno al cron piattaforma: ogni 5 min, dopo le 19:00 (Roma) invia il WA giornaliero se non ancora inviato oggi; alle 18:00 l'avviso fine mese."""
    while True:
        await asyncio.sleep(300)
        try:
            ora = datetime.now(ROMA)
            oggi = ora.date().isoformat()
            db = _d["db"]
            if (ora.hour, ora.minute) >= (19, 0) and not await db.contabilita_log.find_one({"tipo": "wa_giornaliero", "giorno": oggi, "solo_store": {"$exists": False}}):
                logger.info("Fallback interno: invio WA corrispettivi giornalieri %s", oggi)
                await invia_wa_giornaliero(oggi)
            if ora.hour >= 18 and (ora.date() + timedelta(days=1)).day == 1 and not await db.contabilita_log.find_one({"tipo": "wa_fine_mese", "giorno": oggi}):
                logger.info("Fallback interno: avviso fine mese %s", oggi)
                await avviso_fine_mese(oggi)
            await db.cron_log.update_one({"job": "corrispettivi-loop"}, {"$set": {"last_run": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        except Exception as e:
            logger.error("invii_programmati_loop errore: %s", e)

NUMERO_AMMINISTRAZIONE = "3792773557"
CONFIG_DEFAULT = {
    "morbegno": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "info@paghesas.it", "email_from": "rscontabilita@gmail.com"},
    "gravedona": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "info@paghesas.it", "email_from": "rscontabilita@gmail.com"},
    "sondrio": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "marisa@ncservizi.it", "email_from": "amministrazioners.gruppo@gmail.com"},
}
VOCI_DEFAULT = {
    "entrate": ["Eolo", "Energia / Enel", "Telefonia", "Pacchi"],
    "spese_fisse": ["Stipendi", "Contributi", "TFR", "INAIL", "Condominio", "Affitti", "Utenze", "Commercialista", "Finanziamento"],
    "spese_semifisse": ["Ritiri", "Pubblicità"],
    "fornitori": ["Sifar", "Enel", "Eolo", "Fastweb", "Wind", "KMD", "Iliad", "DHL", "UPS", "Kolme", "GLS", "Prontopacco", "Fermopoint", "Mooney", "Nexi", "Pixartprinting", "Miwo", "Raffaella", "CDR", "Parking"],
}
VOCI_DEFAULT_SONDRIO = {
    "entrate": ["Eolo", "Enel mese precedente", "Telefonia", "Pacchi"],
    "spese_fisse": ["Stipendi", "Affitti", "Utenze", "Condominio", "Finanziamento", "Commercialista", "Elena", "Enrico", "INPS Enrico"],
    "spese_semifisse": ["Ritiri", "Pubblicità"],
    "fornitori": ["Nexi", "Fastweb", "Master Group", "KMD", "Iliad", "DHL", "Mooney", "Compass", "Benzina", "Antonino", "W3", "Sifar", "Enel", "Eolo", "Teknozone", "Kolme", "Miwo", "Raffaella", "CDR", "Parking"],
}
CATEGORIE = ["entrate", "spese_fisse", "spese_semifisse", "fornitori"]


def setup(**deps):
    _d.update(deps)


def _slug(nome: str) -> str:
    return (nome or "").strip().lower()


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _is_admin(user: dict) -> bool:
    return user["role"] == "admin"


def _miei_store(user: dict) -> list:
    """Per la contabilità vale l'override `contabilita_store_ids` (es. Deborah → solo Morbegno), altrimenti gli store_ids dell'utente."""
    if user.get("contabilita_store_ids") is not None:
        return user["contabilita_store_ids"]
    return user.get("store_ids") or []


async def _config(store: dict) -> dict:
    cfg = await _d["db"].contabilita_config.find_one({"store_id": store["id"]}, {"_id": 0}) or {}
    base = {"store_id": store["id"], "condividi_admin": False, "wa_numero": "", "email_to": "", "email_from": "", "wa_attivo": True, "email_attivo": True}
    base.update(CONFIG_DEFAULT.get(_slug(store["nome"]), {}))
    base.update({k: v for k, v in cfg.items() if v is not None})
    return base


async def _stores_visibili(user: dict) -> list:
    """Ritorna [(store, config, completo)]: completo=False → admin vede solo attivo/ultimo inserimento."""
    db = _d["db"]
    q = {} if _is_admin(user) else {"id": {"$in": _miei_store(user)}}
    out = []
    async for s in db.stores.find(q, {"_id": 0, "id": 1, "nome": 1, "telefono_avvisi": 1}).sort("nome", 1):
        cfg = await _config(s)
        completo = (s["id"] in _miei_store(user)) or (_is_admin(user) and cfg["condividi_admin"])
        out.append((s, cfg, completo))
    return out


async def _store_completo(user: dict, store_id: str) -> tuple:
    for s, cfg, completo in await _stores_visibili(user):
        if s["id"] == store_id:
            if not completo:
                raise HTTPException(status_code=403, detail="Il negozio non condivide i corrispettivi con l'amministrazione")
            return s, cfg
    raise HTTPException(status_code=403, detail="Negozio non accessibile")


def _f(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _eur(v) -> str:
    s = f"{_f(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


def _norm(c: dict) -> dict:
    fatt = [{"numero": (x.get("numero") or "")[:30], "importo": _f(x.get("importo")), "pagamento": (x.get("pagamento") or "")[:20]} for x in (c.get("fatture_dettaglio") or []) if x.get("numero") or x.get("importo")]
    c["fatture_dettaglio"] = fatt
    c["fatture"] = _f(c.get("fatture")) or round(sum(x["importo"] for x in fatt), 2)
    for k in ("riparazioni", "merce", "art74", "contanti", "pos", "versati", "non_riscosso"):
        c[k] = _f(c.get(k))
    c["non_riscosso_note"] = (c.get("non_riscosso_note") or "")[:200]
    c["scontrini"] = round(c["riparazioni"] + c["merce"] + c["art74"], 2)
    c["fatture_pos"] = round(sum(x["importo"] for x in fatt if x["pagamento"].lower() == "pos"), 2)
    c["fatture_contanti"] = round(sum(x["importo"] for x in fatt if x["pagamento"].lower() == "contanti"), 2)
    if "contanti_inseriti" not in c:
        c["contanti_inseriti"], c["pos_inseriti"] = c["contanti"], c["pos"]
    c["contanti_inseriti"] = _f(c.get("contanti_inseriti"))
    c["pos_inseriti"] = _f(c.get("pos_inseriti"))
    c["contanti"] = round(c["contanti_inseriti"] + c["fatture_contanti"], 2)
    c["pos"] = round(c["pos_inseriti"] + c["fatture_pos"], 2)
    c["pos_scontrini"] = c["pos_inseriti"]
    c["contanti_scontrini"] = c["contanti_inseriti"]
    c["incassato"] = round(c["contanti"] + c["pos"], 2)
    c["quadratura_diff"] = round(c["scontrini"] - c["contanti_scontrini"] - c["pos_scontrini"] - c["non_riscosso"], 2)
    c["totale"] = round(c["scontrini"] + c["fatture"], 2)
    c["iva"] = round((c["riparazioni"] + c["merce"] + c["fatture"]) * 22 / 122, 2)
    return c


# ---------------- Meta / config ----------------
@router.get("/meta")
async def meta(request: Request):
    user = await _user(request)
    db = _d["db"]
    out = []
    for s, cfg, completo in await _stores_visibili(user):
        ultimo = await db.corrispettivi.find_one({"store_id": s["id"]}, {"_id": 0, "data": 1, "updated_at": 1}, sort=[("data", -1)])
        item = {"id": s["id"], "nome": s["nome"], "completo": completo, "attivo": bool(ultimo), "ultimo_inserimento": (ultimo or {}).get("data")}
        if completo:
            item["config"] = cfg
        out.append(item)
    return {"stores": out, "is_admin": _is_admin(user), "categorie": CATEGORIE, "numero_amministrazione": NUMERO_AMMINISTRAZIONE}


@router.get("/utenti")
async def utenti_accessi(request: Request):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    out = []
    async for u in db.users.find({"role": {"$ne": "admin"}, "attivo": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "store_ids": 1, "contabilita_store_ids": 1}).sort("name", 1):
        eff = u["contabilita_store_ids"] if u.get("contabilita_store_ids") is not None else (u.get("store_ids") or [])
        out.append({**u, "override": u.get("contabilita_store_ids") is not None, "store_ids_effettivi": eff, "negozi": [stores.get(s, s) for s in eff]})
    return {"utenti": out, "stores": [{"id": k, "nome": v} for k, v in sorted(stores.items(), key=lambda x: x[1])]}


class AccessoInput(BaseModel):
    contabilita_store_ids: Optional[list] = None


@router.patch("/utenti/{user_id}")
async def patch_utente_accesso(user_id: str, body: AccessoInput, request: Request):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    upd = {"$set": {"contabilita_store_ids": body.contabilita_store_ids}} if body.contabilita_store_ids is not None else {"$unset": {"contabilita_store_ids": ""}}
    r = await _d["db"].users.update_one({"id": user_id}, upd)
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"ok": True}


class ConfigInput(BaseModel):
    condividi_admin: Optional[bool] = None
    wa_numero: Optional[str] = None
    wa_attivo: Optional[bool] = None
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    email_attivo: Optional[bool] = None


@router.patch("/config/{store_id}")
async def patch_config(store_id: str, body: ConfigInput, request: Request):
    user = await _user(request)
    mio = store_id in _miei_store(user)
    if not mio and not _is_admin(user):
        raise HTTPException(status_code=403, detail="Negozio non accessibile")
    if not mio and body.condividi_admin is not None and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo il negozio decide cosa condividere")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "wa_numero" in upd:
        upd["wa_numero"] = re.sub(r"\D", "", upd["wa_numero"])
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _d["db"].contabilita_config.update_one({"store_id": store_id}, {"$set": upd, "$setOnInsert": {"store_id": store_id}}, upsert=True)
    store = await _d["db"].stores.find_one({"id": store_id}, {"_id": 0, "id": 1, "nome": 1})
    return await _config(store)


# ---------------- Corrispettivi ----------------
async def _mese_dati(store_id: str, anno: int, mese: int) -> dict:
    db = _d["db"]
    pref = f"{anno:04d}-{mese:02d}"
    giorni = {c["data"]: _norm(c) async for c in db.corrispettivi.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0})}
    spese = await db.spese_cassa.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0}).sort("data", 1).to_list(500)
    n = monthrange(anno, mese)[1]
    righe = []
    for g in range(1, n + 1):
        d = f"{pref}-{g:02d}"
        righe.append(giorni.get(d) or {"data": d, "vuoto": True})
    keys = ("riparazioni", "merce", "art74", "fatture", "totale", "contanti", "pos", "incassato", "versati", "iva", "non_riscosso", "fatture_pos", "fatture_contanti")
    tot = {k: round(sum(_f(c.get(k)) for c in giorni.values()), 2) for k in keys}
    tot["spese_contanti"] = round(sum(_f(s.get("importo")) for s in spese), 2)
    tot["cassa_netta"] = round(tot["contanti"] - tot["spese_contanti"], 2)
    extra = await db.corrispettivi_mese.find_one({"store_id": store_id, "anno": anno, "mese": mese}, {"_id": 0}) or {}
    versati_dopo = extra.get("versati_dopo") or []
    tot["versati_dopo"] = round(sum(_f(v.get("importo")) for v in versati_dopo), 2)
    tot["versati_totale"] = round(tot["versati"] + tot["versati_dopo"], 2)
    tot["riporto"] = _f(extra.get("riporto"))
    tot["giorni_inseriti"] = len(giorni)
    import corrispettivi_ade
    confronto_ade = await corrispettivi_ade.confronto_mese(store_id, anno, mese, righe)
    prev_a, prev_m = (anno - 1, 12) if mese == 1 else (anno, mese - 1)
    prev_ex = await db.corrispettivi_mese.find_one({"store_id": store_id, "anno": prev_a, "mese": prev_m}, {"_id": 0, "riporto": 1, "versati_dopo": 1})
    prev_pref = f"{prev_a:04d}-{prev_m:02d}"
    prev_cont = 0.0
    prev_vers = 0.0
    async for c in db.corrispettivi.find({"store_id": store_id, "data": {"$regex": f"^{prev_pref}"}}, {"_id": 0, "contanti": 1, "versati": 1}):
        prev_cont += _f(c.get("contanti"))
        prev_vers += _f(c.get("versati"))
    prev_spese = sum([_f(s.get("importo")) async for s in db.spese_cassa.find({"store_id": store_id, "data": {"$regex": f"^{prev_pref}"}}, {"_id": 0, "importo": 1})])
    prev_vers += sum(_f(v.get("importo")) for v in ((prev_ex or {}).get("versati_dopo") or []))
    riporto_proposto = round(_f((prev_ex or {}).get("riporto")) + prev_cont - prev_spese - prev_vers, 2) if (prev_cont or prev_ex) else 0.0
    riporto_auto = "riporto" not in extra or extra.get("riporto_fonte") == "auto"
    if riporto_auto and riporto_proposto > 0:
        tot["riporto"] = riporto_proposto
    tot["da_versare"] = round(tot["riporto"] + tot["cassa_netta"] - tot["versati_totale"], 2)
    return {"anno": anno, "mese": mese, "righe": righe, "spese": spese, "versati_dopo": versati_dopo, "riporto": tot["riporto"], "confronto_ade": confronto_ade,
            "riporto_note": extra.get("riporto_note") or (f"riporto automatico non versato {MESI_IT[prev_m]} {prev_a}" if riporto_auto and tot["riporto"] else ""),
            "riporto_auto": riporto_auto, "riporto_proposto": riporto_proposto, "riporto_proposto_mese": f"{MESI_IT[prev_m]} {prev_a}", "totali": tot}


@router.get("/corrispettivi")
async def get_corrispettivi(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    store, cfg = await _store_completo(user, store_id)
    out = await _mese_dati(store_id, anno, mese)
    out["store"] = {"id": store["id"], "nome": store["nome"]}
    return out


class CorrispettivoInput(BaseModel):
    riparazioni: float = 0
    merce: float = 0
    art74: float = 0
    fatture: float = 0
    fatture_dettaglio: list = []
    contanti: float = 0
    pos: float = 0
    versati: float = 0
    non_riscosso: float = 0
    non_riscosso_note: str = ""
    note: str = ""


QUADRATURA_TOLLERANZA = 1.0


async def avviso_quadratura(store_id: str, c: dict) -> None:
    """WhatsApp immediato al negozio se scontrini ≠ contanti+POS+non riscosso."""
    db = _d["db"]
    diff = c.get("quadratura_diff") or 0
    if abs(diff) < QUADRATURA_TOLLERANZA or not c.get("incassato"):
        return
    s = await db.stores.find_one({"id": store_id}, {"_id": 0, "id": 1, "nome": 1, "telefono_avvisi": 1})
    numero = re.sub(r"\D", "", (s or {}).get("telefono_avvisi") or "")
    if not numero:
        return
    d = c["data"]
    testo = (f"⚠️ *{s['nome']}* - corrispettivo del {d[8:]}/{d[5:7]}/{d[:4]} NON quadra\n"
             f"Scontrini (riparazioni+merce+art.74): {_eur(c['scontrini'])}\n"
             f"Contanti da scontrini {_eur(c['contanti_scontrini'])} + POS da scontrini {_eur(c['pos_scontrini'])}"
             + (f" (fatture a parte: POS {_eur(c.get('fatture_pos', 0))}, contanti {_eur(c.get('fatture_contanti', 0))})" if (c.get("fatture_pos") or c.get("fatture_contanti")) else "")
             + (f" + non riscosso {_eur(c['non_riscosso'])}" if c.get("non_riscosso") else "")
             + f" = {_eur(c['contanti_scontrini'] + c['pos_scontrini'] + c.get('non_riscosso', 0))}\n"
             f"Differenza: *{_eur(diff)}* ({'mancano' if diff > 0 else 'in più'} rispetto agli scontrini). Controlla e correggi il corrispettivo.")
    try:
        await _d["wa_send"](numero, testo, session=store_id, tipo="corrispettivi_quadratura")
    except Exception as e:
        logger.warning("Avviso quadratura %s non inviato: %s", s["nome"], e)


@router.put("/corrispettivi/{store_id}/{data}")
async def put_corrispettivo(store_id: str, data: str, body: CorrispettivoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    try:
        date.fromisoformat(data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    raw = body.model_dump()
    raw["contanti_inseriti"], raw["pos_inseriti"] = raw.get("contanti") or 0, raw.get("pos") or 0
    doc = _norm(raw)
    doc.update({"store_id": store_id, "data": data, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name", "")})
    await _d["db"].corrispettivi.update_one({"store_id": store_id, "data": data}, {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    asyncio.create_task(avviso_quadratura(store_id, doc))
    return await _d["db"].corrispettivi.find_one({"store_id": store_id, "data": data}, {"_id": 0})


@router.delete("/corrispettivi/{store_id}/{data}")
async def del_corrispettivo(store_id: str, data: str, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].corrispettivi.delete_one({"store_id": store_id, "data": data})
    return {"ok": True}


class RiportoInput(BaseModel):
    riporto: float = 0
    riporto_note: str = ""


@router.put("/corrispettivi/{store_id}/{anno}/{mese}/riporto")
async def put_riporto(store_id: str, anno: int, mese: int, body: RiportoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].corrispettivi_mese.update_one({"store_id": store_id, "anno": anno, "mese": mese},
                                                 {"$set": {"riporto": _f(body.riporto), "riporto_note": body.riporto_note[:120], "riporto_fonte": "manuale", "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True, "riporto": _f(body.riporto)}


@router.delete("/corrispettivi/{store_id}/{anno}/{mese}/riporto")
async def reset_riporto(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].corrispettivi_mese.update_one({"store_id": store_id, "anno": anno, "mese": mese}, {"$unset": {"riporto": "", "riporto_note": "", "riporto_fonte": ""}})
    return {"ok": True}


async def avviso_fine_mese(giorno: Optional[str] = None) -> list:
    """Alle 18 dell'ultimo giorno del mese: avvisa il negozio del non versato che passa al mese successivo."""
    db = _d["db"]
    oggi = date.fromisoformat(giorno) if giorno else date.today()
    if (oggi + timedelta(days=1)).day != 1:
        return [{"skip": "non è l'ultimo giorno del mese"}]
    esiti = []
    async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1, "telefono_avvisi": 1}):
        dati = await _mese_dati(s["id"], oggi.year, oggi.month)
        t = dati["totali"]
        if not t["giorni_inseriti"] or t["da_versare"] <= 0:
            continue
        succ = oggi + timedelta(days=1)
        numero = re.sub(r"\D", "", s.get("telefono_avvisi") or "")
        testo = (f"⚠️ *{s['nome']}* - chiusura {MESI_IT[oggi.month]} {oggi.year}\n"
                 f"Non hai ancora versato *{_eur(t['da_versare'])}* (riporto {_eur(t['riporto'])} + contanti {_eur(t['contanti'])} - spese {_eur(t['spese_contanti'])} - versati {_eur(t['versati_totale'])}).\n"
                 f"La cifra verrà riportata automaticamente su {MESI_IT[succ.month]} {succ.year} e dovrà risultare versata.")
        if not numero:
            esiti.append({"negozio": s["nome"], "ok": False, "error": "telefono avvisi negozio mancante", "da_versare": t["da_versare"]})
            continue
        try:
            await _d["wa_send"](numero, testo, session=s["id"], tipo="corrispettivi_fine_mese")
            esiti.append({"negozio": s["nome"], "numero": numero, "ok": True, "da_versare": t["da_versare"]})
        except Exception as e:
            esiti.append({"negozio": s["nome"], "numero": numero, "ok": False, "error": str(getattr(e, "detail", e)), "da_versare": t["da_versare"]})
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "wa_fine_mese", "giorno": oggi.isoformat(), "esiti": esiti, "at": datetime.now(timezone.utc).isoformat()})
    return esiti


@router.post("/corrispettivi/avviso-fine-mese")
async def avviso_fine_mese_manuale(giorno: str, request: Request):
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return await avviso_fine_mese(giorno)


class VersatoDopoInput(BaseModel):
    data: str
    importo: float
    note: str = ""


@router.post("/corrispettivi/{store_id}/{anno}/{mese}/versati-dopo")
async def add_versato_dopo(store_id: str, anno: int, mese: int, body: VersatoDopoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    try:
        date.fromisoformat(body.data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    v = {"id": str(uuid.uuid4()), "data": body.data, "importo": _f(body.importo), "note": body.note[:120], "created_by": user.get("name", "")}
    await _d["db"].corrispettivi_mese.update_one({"store_id": store_id, "anno": anno, "mese": mese}, {"$push": {"versati_dopo": v}}, upsert=True)
    return v


@router.delete("/corrispettivi/{store_id}/{anno}/{mese}/versati-dopo/{vid}")
async def del_versato_dopo(store_id: str, anno: int, mese: int, vid: str, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].corrispettivi_mese.update_one({"store_id": store_id, "anno": anno, "mese": mese}, {"$pull": {"versati_dopo": {"id": vid}}})
    return {"ok": True}


class SpesaInput(BaseModel):
    store_id: str
    data: str
    motivo: str
    importo: float
    riferimento: str = ""


@router.post("/spese")
async def add_spesa(body: SpesaInput, request: Request):
    user = await _user(request)
    await _store_completo(user, body.store_id)
    doc = body.model_dump()
    doc.update({"id": str(uuid.uuid4()), "importo": _f(body.importo), "created_at": datetime.now(timezone.utc).isoformat(), "created_by": user.get("name", "")})
    await _d["db"].spese_cassa.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/spese/{spesa_id}")
async def del_spesa(spesa_id: str, request: Request):
    user = await _user(request)
    sp = await _d["db"].spese_cassa.find_one({"id": spesa_id}, {"_id": 0})
    if not sp:
        raise HTTPException(status_code=404, detail="Spesa non trovata")
    await _store_completo(user, sp["store_id"])
    await _d["db"].spese_cassa.delete_one({"id": spesa_id})
    return {"ok": True}


# ---------------- PDF mensile ----------------
def _pdf_txt(s) -> str:
    return str(s).replace("–", "-").replace("—", "-").replace("€", "EUR").encode("latin-1", "replace").decode("latin-1")


def _pdf_mese(store: dict, dati: dict) -> bytes:
    from fpdf import FPDF
    anno, mese, tot = dati["anno"], dati["mese"], dati["totali"]
    pdf = FPDF(orientation="L", format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _pdf_txt(f"Corrispettivi giornalieri - {store['nome']} - {MESI_IT[mese]} {anno}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, _pdf_txt(f"Generato il {date.today().strftime('%d/%m/%Y')} - RS Riparazioni / CambiaOra"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    cols = [("Giorno", 16), ("Riparazioni", 26), ("Merce", 24), ("Art. 74", 24), ("Fatture", 24), ("N. fattura / pag.", 48), ("Contanti", 24), ("POS", 24), ("TOTALE", 26), ("Versati", 24), ("IVA 22%", 22)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(226, 232, 240)
    for t, w in cols:
        pdf.cell(w, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in dati["righe"]:
        g = r["data"][8:]
        if r.get("vuoto"):
            vals = [g, "", "", "", "", "", "-", "", "", "", ""]
        else:
            fd = ", ".join(f"{x['numero']} {x['pagamento']}".strip() for x in r["fatture_dettaglio"])[:34]
            vals = [g, _eur(r["riparazioni"]), _eur(r["merce"]), _eur(r["art74"]), _eur(r["fatture"]), fd, _eur(r["contanti"]), _eur(r["pos"]), _eur(r["totale"]), _eur(r["versati"]) if r["versati"] else "", _eur(r["iva"])]
        for (t, w), v in zip(cols, vals):
            pdf.cell(w, 6, _pdf_txt(v), border=1, align="R" if t not in ("Giorno", "N. fattura / pag.") else "L")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 8)
    vals = ["TOT", _eur(tot["riparazioni"]), _eur(tot["merce"]), _eur(tot["art74"]), _eur(tot["fatture"]), "", _eur(tot["contanti"]), _eur(tot["pos"]), _eur(tot["totale"]), _eur(tot["versati"]), _eur(tot["iva"])]
    for (t, w), v in zip(cols, vals):
        pdf.cell(w, 7, _pdf_txt(v), border=1, fill=True, align="R" if t != "Giorno" else "L")
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Spese per contanti / cassa [PRIMA NOTA]", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 8)
    for t, w in [("Data", 24), ("Motivo", 110), ("Importo", 30), ("N. fattura / ritiro", 50)]:
        pdf.cell(w, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for s in dati["spese"]:
        for v, w in [(s["data"][8:] + "/" + s["data"][5:7], 24), (s.get("motivo", "")[:70], 110), (_eur(s["importo"]), 30), (s.get("riferimento", "")[:30], 50)]:
            pdf.cell(w, 6, _pdf_txt(v), border=1)
        pdf.ln()
    if not dati["spese"]:
        pdf.cell(214, 6, "Nessuna spesa registrata", border=1, new_x="LMARGIN", new_y="NEXT")
    if dati["versati_dopo"]:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "Versamenti effettuati dopo la fine del mese (competenza del mese)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for v in dati["versati_dopo"]:
            pdf.cell(0, 5, _pdf_txt(f"{v['data'][8:]}/{v['data'][5:7]}/{v['data'][:4]}  {_eur(v['importo'])}  {v.get('note', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, _pdf_txt(f"Riporto mese precedente: {_eur(tot['riporto'])}  -  Contanti incassati: {_eur(tot['contanti'])}  -  Spese contanti: {_eur(tot['spese_contanti'])}  -  Cassa netta: {_eur(tot['cassa_netta'])}  -  Versati: {_eur(tot['versati_totale'])}  -  Giorni inseriti: {tot['giorni_inseriti']}"), new_x="LMARGIN", new_y="NEXT")
    if tot["da_versare"] < 0:
        pdf.set_text_color(190, 30, 30)
    pdf.cell(0, 6, _pdf_txt(("AMMANCO: " if tot["da_versare"] < 0 else "Da versare: ") + _eur(tot["da_versare"])), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


@router.get("/corrispettivi/pdf")
async def pdf_corrispettivi(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    data = _pdf_mese(store, await _mese_dati(store_id, anno, mese))
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Corrispettivi_{store["nome"]}_{anno}-{mese:02d}.pdf"'})


# ---------------- Invii ----------------
def _testo_wa_store(nome: str, c: Optional[dict], spese: list, data: str) -> str:
    d = f"{data[8:]}/{data[5:7]}/{data[:4]}"
    if not c:
        return f"*{nome}* - {d}\nNessun corrispettivo inserito oggi."
    righe = [f"*{nome}* - {d}",
             f"Riparazioni: {_eur(c['riparazioni'])}", f"Merce: {_eur(c['merce'])}", f"Art. 74: {_eur(c['art74'])}"]
    if c["fatture"]:
        det = ", ".join(f"{x['numero']} {x['pagamento']}".strip() for x in c["fatture_dettaglio"])
        righe.append(f"Fatture: {_eur(c['fatture'])}" + (f" ({det})" if det else ""))
    righe += [f"Contanti: {_eur(c['contanti'])} | POS: {_eur(c['pos'])}" + (f" (di cui fatture: POS {_eur(c.get('fatture_pos', 0))}, contanti {_eur(c.get('fatture_contanti', 0))})" if (c.get("fatture_pos") or c.get("fatture_contanti")) else ""),
              f"*TOTALE SCONTRINATO (scontrini+fatture): {_eur(c['totale'])}*"]
    if c.get("non_riscosso"):
        righe.append(f"Non riscosso: {_eur(c['non_riscosso'])}" + (f" ({c['non_riscosso_note']})" if c.get("non_riscosso_note") else ""))
    if c.get("incassato") and abs(c.get("quadratura_diff") or 0) >= QUADRATURA_TOLLERANZA:
        righe.append(f"⚠️ Non quadra: differenza {_eur(c['quadratura_diff'])} tra scontrini e incasso")
    if c["versati"]:
        righe.append(f"Versati: {_eur(c['versati'])}")
    if spese:
        righe.append("Spese contanti: " + "; ".join(f"{s['motivo']} {_eur(s['importo'])}" for s in spese))
        righe.append(f"Totale spese: {_eur(sum(s['importo'] for s in spese))}")
    if c.get("note"):
        righe.append(f"Note: {c['note']}")
    return "\n".join(righe)


async def invia_wa_giornaliero(giorno: Optional[str] = None, solo_store: Optional[str] = None) -> list:
    """Alle 19:00: un messaggio per numero destinatario con tutti i negozi che lo hanno impostato, dal numero del primo negozio."""
    db = _d["db"]
    giorno = giorno or date.today().isoformat()
    gruppi: dict = {}
    async for s in db.stores.find({} if not solo_store else {"id": solo_store}, {"_id": 0, "id": 1, "nome": 1}):
        cfg = await _config(s)
        if not cfg["wa_numero"] or not cfg.get("wa_attivo", True):
            continue
        c = await db.corrispettivi.find_one({"store_id": s["id"], "data": giorno}, {"_id": 0})
        spese = await db.spese_cassa.find({"store_id": s["id"], "data": giorno}, {"_id": 0}).to_list(100)
        gruppi.setdefault(cfg["wa_numero"], []).append((s, _norm(c) if c else None, spese))
    esiti = []
    for numero, items in gruppi.items():
        testo = "📊 *Corrispettivi del giorno*\n\n" + "\n\n".join(_testo_wa_store(s["nome"], c, sp, giorno) for s, c, sp in items)
        session = items[0][0]["id"]
        for s, c, sp in items:
            if await _d["wa_sessione_connessa"](s["id"]):
                session = s["id"]
                break
        try:
            await _d["wa_send"](numero, testo, session=session, tipo="corrispettivi_giornalieri")
            esiti.append({"numero": numero, "negozi": [s["nome"] for s, _, _ in items], "ok": True})
        except Exception as e:
            esiti.append({"numero": numero, "negozi": [s["nome"] for s, _, _ in items], "ok": False, "error": str(getattr(e, "detail", e))})
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "wa_giornaliero", "giorno": giorno, "esiti": esiti, "at": datetime.now(timezone.utc).isoformat(), **({"solo_store": solo_store} if solo_store else {})})
    return esiti


@router.post("/corrispettivi/invia-whatsapp")
async def invia_whatsapp_manuale(store_id: str, data: str, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    return await invia_wa_giornaliero(data, solo_store=store_id)


async def invia_email_mensile(store_id: str, anno: int, mese: int, extra_to: Optional[str] = None) -> dict:
    db = _d["db"]
    store = await db.stores.find_one({"id": store_id}, {"_id": 0, "id": 1, "nome": 1})
    cfg = await _config(store)
    to = extra_to or cfg["email_to"]
    if not to or "@" not in to:
        return {"inviato": False, "motivo": "Email destinatario non impostata"}
    dati = await _mese_dati(store_id, anno, mese)
    if not dati["totali"]["giorni_inseriti"]:
        return {"inviato": False, "motivo": "Nessun corrispettivo nel mese"}
    pdf = _pdf_mese(store, dati)
    path = f"{_d['app_name']}/contabilita/{store['nome']}_{anno}-{mese:02d}_{uuid.uuid4().hex[:8]}.pdf"
    res = _d["put_object"](path, pdf, "application/pdf")
    token = uuid.uuid4().hex
    fname = f"Corrispettivi_{store['nome']}_{anno}-{mese:02d}.pdf"
    await db.report_download.insert_one({"token": token, "path": res["path"], "content_type": "application/pdf", "filename": fname,
                                         "expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
                                         "created_at": datetime.now(timezone.utc).isoformat()})
    link = f"{os.environ.get('FRONTEND_URL', '').rstrip('/')}/api/public/report/{token}"
    t = dati["totali"]
    html = (f"<div style='font-family:Arial,sans-serif;color:#0f172a'><h2>Corrispettivi {escape(store['nome'])} - {MESI_IT[mese]} {anno}</h2>"
            f"<p>Buongiorno, in allegato (link sicuro, valido 60 giorni) il riepilogo dei corrispettivi giornalieri e delle spese di cassa del mese.</p>"
            f"<p><a href='{link}' style='display:inline-block;padding:10px 16px;background:#0f172a;color:#fff;border-radius:8px;text-decoration:none'>Scarica il PDF completo</a></p>"
            f"<table style='border-collapse:collapse;font-size:13px'>"
            + "".join(f"<tr><td style='padding:4px 10px;border-bottom:1px solid #e2e8f0'>{k}</td><td style='padding:4px 10px;border-bottom:1px solid #e2e8f0;text-align:right'><b>{escape(_eur(v))}</b></td></tr>"
                      for k, v in [("Riparazioni", t["riparazioni"]), ("Merce", t["merce"]), ("Art. 74", t["art74"]), ("Fatture", t["fatture"]), ("TOTALE SCONTRINATO (scontrini + fatture)", t["totale"]),
                                   ("Contanti", t["contanti"]), ("POS", t["pos"]), ("Non riscosso", t["non_riscosso"]), ("Riporto mese precedente", t["riporto"]), ("Versati (nel mese + dopo)", t["versati_totale"]), ("Spese contanti (prima nota)", t["spese_contanti"]), ("Da versare / ammanco", t["da_versare"]), ("IVA 22% scorporata", t["iva"])])
            + f"</table><p style='font-size:12px;color:#64748b'>Giorni inseriti: {t['giorni_inseriti']}. Inviato da {escape(cfg['email_from'] or 'gestionale')} - RS Riparazioni / CambiaOra.</p></div>")
    email_id = await _d["send_email"](to=to, subject=f"Corrispettivi {store['nome']} - {MESI_IT[mese]} {anno}", html=html,
                                      reply_to=cfg["email_from"] or None, from_name=cfg["email_from"] or None)
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "email_mensile", "store_id": store_id, "anno": anno, "mese": mese, "to": to,
                                         "from": cfg["email_from"], "link": link, "email_id": email_id, "at": datetime.now(timezone.utc).isoformat()})
    return {"inviato": True, "to": to, "from": cfg["email_from"], "link": link}


async def invia_email_mensile_tutti() -> list:
    oggi = date.today()
    prev = (oggi.replace(day=1) - timedelta(days=1))
    out = []
    async for s in _d["db"].stores.find({}, {"_id": 0, "id": 1, "nome": 1}):
        cfg = await _config(s)
        if not cfg["email_to"] or not cfg.get("email_attivo", True):
            continue
        try:
            out.append({"negozio": s["nome"], **(await invia_email_mensile(s["id"], prev.year, prev.month))})
        except Exception as e:
            out.append({"negozio": s["nome"], "inviato": False, "motivo": str(getattr(e, "detail", e))})
    logger.info(f"Email corrispettivi mensili: {out}")
    return out


@router.post("/corrispettivi/invia-email")
async def invia_email_manuale(store_id: str, anno: int, mese: int, request: Request, to: Optional[str] = None):
    user = await _user(request)
    await _store_completo(user, store_id)
    return await invia_email_mensile(store_id, anno, mese, extra_to=to)


@router.get("/log")
async def log_invii(request: Request):
    user = await _user(request)
    ids = [s["id"] for s, _, completo in await _stores_visibili(user) if completo]
    q = {"$or": [{"store_id": {"$in": ids}}, {"tipo": "wa_giornaliero"}]} if not _is_admin(user) else {}
    return await _d["db"].contabilita_log.find(q, {"_id": 0}).sort("at", -1).to_list(60)


# ---------------- Punto di pareggio (per centro di costo) ----------------
SEED_PDP = {"morbegno+gravedona": {(2026, 8): {
    "entrate|Eolo": 6640.0, "entrate|Energia / Enel": 8200.35, "entrate|Telefonia": 523.0, "entrate|Pacchi": 181.08,
    "spese_fisse|Stipendi": 7100.0, "spese_fisse|Contributi": 4000.0, "spese_fisse|Condominio": 540.0, "spese_fisse|Affitti": 1300.0,
    "spese_fisse|Utenze": 450.0, "spese_fisse|Commercialista": 950.0,
    "fornitori|Sifar": 5380.0, "fornitori|Enel": 8684.08, "fornitori|Eolo": 8808.40, "fornitori|Fastweb": 377.90, "fornitori|Wind": 681.98,
    "fornitori|Iliad": 711.24, "fornitori|DHL": 241.07, "fornitori|UPS": 114.96, "fornitori|Mooney": 58.56, "fornitori|Nexi": 36.60,
    "fornitori|W3": 59.66, "fornitori|Phoneclik": 689.0, "fornitori|Miwo": 721.15, "fornitori|Raffaella": 1662.13}}}


async def _centri(user: dict) -> list:
    """Centri di costo visibili all'utente. Default: Morbegno+Gravedona insieme, Sondrio da solo, gli altri singoli."""
    db = _d["db"]
    stores_all = {s["id"]: s async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    centri = await db.pdp_centri.find({}, {"_id": 0}).to_list(100)
    assegnati = {sid for c in centri for sid in c["store_ids"]}
    if not centri:
        mg = [s["id"] for s in stores_all.values() if _slug(s["nome"]) in ("morbegno", "gravedona")]
        if mg:
            centri.append({"id": "morbegno+gravedona", "nome": "Morbegno + Gravedona", "store_ids": mg})
            assegnati |= set(mg)
    for sid, s in stores_all.items():
        if sid not in assegnati:
            centri.append({"id": f"store:{sid}", "nome": s["nome"], "store_ids": [sid]})
    if not await db.pdp_centri.count_documents({}):
        for c in centri:
            await db.pdp_centri.update_one({"id": c["id"]}, {"$set": c}, upsert=True)
    visibili = {s["id"] for s, _, completo in await _stores_visibili(user) if completo}
    out = []
    for c in centri:
        c["store_ids"] = [sid for sid in c["store_ids"] if sid in stores_all]
        c["negozi"] = [stores_all[sid]["nome"] for sid in c["store_ids"]]
        if c["store_ids"] and (set(c["store_ids"]) & visibili):
            out.append(c)
    return out


async def _centro(user: dict, centro_id: str) -> dict:
    for c in await _centri(user):
        if c["id"] == centro_id:
            return c
    raise HTTPException(status_code=403, detail="Centro di costo non accessibile")


class CentroInput(BaseModel):
    id: str = ""
    nome: str
    store_ids: list


@router.get("/pdp/centri")
async def get_centri(request: Request):
    return await _centri(await _user(request))


@router.put("/pdp/centri")
async def put_centri(body: list[CentroInput], request: Request):
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    usati = set()
    docs = []
    for c in body:
        ids = [s for s in c.store_ids if s not in usati]
        usati |= set(ids)
        if not ids or not c.nome.strip():
            continue
        docs.append({"id": c.id or str(uuid.uuid4()), "nome": c.nome.strip()[:60], "store_ids": ids})
    await db.pdp_centri.delete_many({})
    if docs:
        await db.pdp_centri.insert_many([dict(d) for d in docs])
    return await _centri(user)


async def _voci(centro: dict) -> dict:
    doc = await _d["db"].pdp_voci.find_one({"centro_id": centro["id"]}, {"_id": 0})
    if doc:
        return {k: doc.get(k, []) for k in CATEGORIE}
    base = VOCI_DEFAULT_SONDRIO if "sondrio" in _slug(centro["nome"]) else VOCI_DEFAULT
    return {k: list(v) for k, v in base.items()}


class VociInput(BaseModel):
    entrate: list = []
    spese_fisse: list = []
    spese_semifisse: list = []
    fornitori: list = []


@router.put("/pdp/voci/{centro_id}")
async def put_voci(centro_id: str, body: VociInput, request: Request):
    user = await _user(request)
    await _centro(user, centro_id)
    doc = {k: [str(x).strip()[:60] for x in getattr(body, k) if str(x).strip()] for k in CATEGORIE}
    await _d["db"].pdp_voci.update_one({"centro_id": centro_id}, {"$set": doc}, upsert=True)
    return doc


STOP_WORDS = {"spa", "srl", "snc", "sas", "s.p.a.", "s.r.l.", "italia", "italy", "group", "energia", "express", "payments", "di", "e", "&", "c", "the"}


def _tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 3 and t not in STOP_WORDS}


async def _ricevute_per_fornitore(centro_id: str, anno: int, mese: int, voci_fornitori: list) -> tuple:
    """Raggruppa le fatture ricevute AdE per controparte e le abbina alle voci fornitori del PDP."""
    gruppi: dict = {}
    async for f in _d["db"].fatture_ade.find({"centro_id": centro_id, "anno": anno, "mese": mese, "direzione": "ricevute"}, {"_id": 0, "controparte": 1, "totale": 1}):
        k = (f.get("controparte") or "Sconosciuto").strip()
        gruppi[k] = round(gruppi.get(k, 0.0) + _f(f.get("totale")), 2)
    abbinati: dict = {}
    non_abbinate = []
    voci_tok = [(v, _tokens(v)) for v in voci_fornitori]
    for contro, tot in sorted(gruppi.items(), key=lambda x: -abs(x[1])):
        ct = _tokens(contro)
        match = None
        for v, vt in voci_tok:
            if vt and (vt <= ct or any(any(a.startswith(b) or b.startswith(a) for a in ct) for b in vt if len(b) >= 4)):
                match = v
                break
        if match:
            abbinati[match] = round(abbinati.get(match, 0.0) + tot, 2)
        else:
            non_abbinate.append({"controparte": contro, "totale": tot})
    return abbinati, non_abbinate


async def _pdp_calcolo(centro: dict, anno: int, mese: int) -> dict:
    db = _d["db"]
    voci = await _voci(centro)
    doc = await db.pdp.find_one({"centro_id": centro["id"], "anno": anno, "mese": mese}, {"_id": 0}) or {}
    valori = dict(doc.get("valori") or {})
    ereditato_da = None
    if not doc and (anno, mese) in SEED_PDP.get(centro["id"], {}):
        valori = dict(SEED_PDP[centro["id"]][(anno, mese)])
        ereditato_da = "foglio Google (agosto 2026)"
    elif not doc:
        prev = await db.pdp.find({"centro_id": centro["id"], "$or": [{"anno": {"$lt": anno}}, {"anno": anno, "mese": {"$lt": mese}}]},
                                 {"_id": 0, "anno": 1, "mese": 1, "valori": 1}).sort([("anno", -1), ("mese", -1)]).limit(1).to_list(1)
        fonte = prev[0] if prev else None
        if not fonte:
            seed = [(k, v) for k, v in SEED_PDP.get(centro["id"], {}).items() if k < (anno, mese)]
            if seed:
                (a, m), v = max(seed)
                fonte = {"anno": a, "mese": m, "valori": v}
        if fonte:
            fisse = {k: v for k, v in (fonte.get("valori") or {}).items() if k.startswith("spese_fisse|") and _f(v)}
            if fisse:
                valori.update(fisse)
                ereditato_da = f"{MESI_IT[fonte['mese']]} {fonte['anno']}"
    for k in valori:
        cat, nome = k.split("|", 1)
        if cat in voci and nome not in voci[cat]:
            voci[cat].append(nome)
    corr = 0.0
    per_negozio = {}
    for sid in centro["store_ids"]:
        t = (await _mese_dati(sid, anno, mese))["totali"]["totale"]
        per_negozio[sid] = t
        corr += t
    entrate = {"Corrispettivi negozi": round(corr, 2)}
    import fatture_ade
    ade = await fatture_ade.totali_mese(centro["id"], anno, mese)
    entrate["Fatture emesse (AdE)"] = ade["emesse"]
    entrate_info = {}
    for v in voci["entrate"]:
        val = _f(valori.get(f"entrate|{v}"))
        if ade["emesse"] > 0:
            entrate_info[v] = val  # già comprese nelle fatture emesse: non sommare due volte
        else:
            entrate[v] = val
    sezioni = {}
    for cat in ("spese_fisse", "spese_semifisse", "fornitori"):
        sezioni[cat] = {v: _f(valori.get(f"{cat}|{v}")) for v in voci[cat]}
    ade_fornitori, non_abbinate = await _ricevute_per_fornitore(centro["id"], anno, mese, voci["fornitori"])
    for v, imp in ade_fornitori.items():
        sezioni["fornitori"][v] = imp if imp else sezioni["fornitori"].get(v, 0.0)
    tot_non_abb = round(sum(x["totale"] for x in non_abbinate), 2)
    sezioni["fornitori"] = {"Fatture ricevute non abbinate (AdE)": tot_non_abb, **sezioni["fornitori"]}
    tot_entrate = round(sum(entrate.values()), 2)
    tot_spese = {cat: round(sum(d.values()), 2) for cat, d in sezioni.items()}
    # Spese contanti da prima nota (incluse quelle importate dai fogli Google), raggruppate per motivo
    pref = f"{anno:04d}-{mese:02d}"
    spese_cassa: dict = {}
    async for s in db.spese_cassa.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "motivo": 1, "importo": 1}):
        k = re.sub(r"\s+", " ", (s.get("motivo") or "Varie").strip()).title()[:40] or "Varie"
        spese_cassa[k] = round(spese_cassa.get(k, 0.0) + _f(s.get("importo")), 2)
    tot_spese_cassa = round(sum(spese_cassa.values()), 2)
    tot_spese["spese_cassa"] = tot_spese_cassa
    tot_uscite = round(sum(tot_spese.values()), 2)
    # Incassato reale e giorni lavorati
    incassato = contanti = pos = non_riscosso = iva = 0.0
    giorni_inseriti = 0
    for sid in centro["store_ids"]:
        t = (await _mese_dati(sid, anno, mese))["totali"]
        contanti += t["contanti"]; pos += t["pos"]; non_riscosso += t["non_riscosso"]; iva += t["iva"]
        giorni_inseriti = max(giorni_inseriti, t.get("giorni_inseriti") or 0)
    incassato = round(contanti + pos, 2)
    # Break-even: costi fissi / margine di contribuzione %
    costi_fissi = round(tot_spese["spese_fisse"] + tot_spese["spese_semifisse"] + tot_spese_cassa, 2)
    costi_variabili = tot_spese["fornitori"]
    mdc = round(tot_entrate - costi_variabili, 2)
    mdc_pct = round(mdc / tot_entrate * 100, 1) if tot_entrate else None
    bep = round(costi_fissi / (mdc / tot_entrate), 2) if tot_entrate and mdc > 0 else (costi_fissi if not costi_variabili else None)
    bep_motivo = "" if bep is not None else "I costi variabili (fornitori) superano il fatturato: il pareggio non è raggiungibile a questo margine. Controlla che tra i fornitori non ci siano costi passanti (es. bollette Enel/Eolo rivendute) o sposta le voci fisse."
    import calendar
    giorni_mese = calendar.monthrange(anno, mese)[1]
    oggi = date.today()
    in_corso = (anno, mese) == (oggi.year, oggi.month)
    giorni_trascorsi = oggi.day if in_corso else giorni_mese
    media_giorno = round(tot_entrate / giorni_inseriti, 2) if giorni_inseriti else 0.0
    giorni_apertura_stimati = max(giorni_inseriti, round(giorni_mese * 26 / 30))
    proiezione = round(media_giorno * giorni_apertura_stimati, 2) if in_corso and giorni_inseriti else tot_entrate
    bep_giorno = round(bep / giorni_apertura_stimati, 2) if bep else None
    break_even = {"costi_fissi": costi_fissi, "costi_variabili": costi_variabili, "mdc": mdc, "mdc_pct": mdc_pct, "bep_fatturato": bep, "bep_motivo": bep_motivo,
                  "margine_sicurezza": round(tot_entrate - bep, 2) if bep is not None else None,
                  "margine_sicurezza_pct": round((tot_entrate - bep) / tot_entrate * 100, 1) if bep is not None and tot_entrate else None,
                  "bep_giorno": bep_giorno, "media_giorno": media_giorno, "giorni_inseriti": giorni_inseriti, "giorni_mese": giorni_mese,
                  "giorni_trascorsi": giorni_trascorsi, "giorni_apertura_stimati": giorni_apertura_stimati, "in_corso": in_corso, "proiezione_fatturato": proiezione,
                  "proiezione_risultato": round(proiezione - costi_variabili * (proiezione / tot_entrate if tot_entrate else 1) - costi_fissi, 2) if in_corso else round(tot_entrate - tot_uscite, 2)}
    return {"centro": {"id": centro["id"], "nome": centro["nome"], "negozi": centro["negozi"]}, "anno": anno, "mese": mese, "voci": voci, "valori": valori,
            "entrate": entrate, "entrate_info": entrate_info, "corrispettivi_per_negozio": per_negozio, "ade": ade, "ade_fornitori": ade_fornitori, "ade_non_abbinate": non_abbinate, "sezioni": sezioni, "tot_entrate": tot_entrate, "tot_spese": tot_spese, "tot_uscite": tot_uscite,
            "spese_cassa": spese_cassa, "tot_spese_cassa": tot_spese_cassa,
            "incasso": {"incassato": incassato, "contanti": round(contanti, 2), "pos": round(pos, 2), "non_riscosso": round(non_riscosso, 2), "iva": round(iva, 2), "fatturato": tot_entrate,
                        "da_incassare": round(tot_entrate - incassato, 2)},
            "break_even": break_even,
            "punto_pareggio": bep if bep is not None else tot_uscite, "risultato": round(tot_entrate - tot_uscite, 2),
            "copertura_pct": round(tot_entrate / tot_uscite * 100, 1) if tot_uscite else None, "note": doc.get("note", ""), "ereditato_da": ereditato_da,
            "compilato": bool(doc) or (anno, mese) in SEED_PDP.get(centro["id"], {})}


@router.get("/pdp")
async def get_pdp(centro_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    return await _pdp_calcolo(await _centro(user, centro_id), anno, mese)


@router.get("/pdp/trend")
async def get_pdp_trend(centro_id: str, anno: int, mese: int, request: Request, mesi: int = 6):
    """Serie degli ultimi N mesi (fatturato, incassato, costi fissi/variabili, risultato, BEP) per il centro di costo."""
    user = await _user(request)
    centro = await _centro(user, centro_id)
    out = []
    a, m = anno, mese
    for _ in range(max(1, min(mesi, 12))):
        d = await _pdp_calcolo(centro, a, m)
        be = d["break_even"]
        out.append({"anno": a, "mese": m, "label": f"{MESI_IT[m][:3]} {str(a)[2:]}", "fatturato": d["tot_entrate"], "incassato": d["incasso"]["incassato"],
                    "costi_fissi": be["costi_fissi"], "costi_variabili": be["costi_variabili"], "uscite": d["tot_uscite"], "risultato": d["risultato"],
                    "bep": be["bep_fatturato"], "mdc_pct": be["mdc_pct"], "compilato": d["compilato"]})
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return list(reversed(out))


class PdpInput(BaseModel):
    valori: dict = {}
    note: str = ""


@router.put("/pdp/{centro_id}/{anno}/{mese}")
async def put_pdp(centro_id: str, anno: int, mese: int, body: PdpInput, request: Request):
    user = await _user(request)
    centro = await _centro(user, centro_id)
    valori = {k: _f(v) for k, v in body.valori.items() if "|" in k}
    await _d["db"].pdp.update_one({"centro_id": centro_id, "anno": anno, "mese": mese},
                                  {"$set": {"valori": valori, "note": body.note[:500], "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name", "")},
                                   "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return await _pdp_calcolo(centro, anno, mese)


# ---------------- Report annuale ----------------
async def _fatturato_mese(store: dict, anno: int, mese: int) -> dict:
    db = _d["db"]
    storico = await db.fatturato_storico.find_one({"store_id": store["id"], "anno": anno, "mese": mese}, {"_id": 0})
    corr = (await _mese_dati(store["id"], anno, mese))["totali"]["totale"]
    live = {"enel": 0.0, "altro": round(corr, 2)}
    if storico:
        st = {"enel": _f(storico.get("enel")), "altro": _f(storico.get("altro")), "storico": True}
        if live["enel"] + live["altro"] <= st["enel"] + st["altro"]:
            return st
    return live


@router.get("/report/annuale")
async def report_annuale(store_id: str, anno: int, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    mesi = []
    tot = {"enel": 0.0, "altro": 0.0, "tot": 0.0, "enel_ap": 0.0, "altro_ap": 0.0, "tot_ap": 0.0}
    for m in range(1, 13):
        cur = await _fatturato_mese(store, anno, m)
        ap = await _fatturato_mese(store, anno - 1, m)
        cur_t, ap_t = round(cur["enel"] + cur["altro"], 2), round(ap["enel"] + ap["altro"], 2)
        pct = round((cur_t - ap_t) / ap_t * 100, 2) if ap_t and cur_t else None
        pct_enel = round((cur["enel"] - ap["enel"]) / ap["enel"] * 100, 2) if ap["enel"] and cur["enel"] else None
        pct_altro = round((cur["altro"] - ap["altro"]) / ap["altro"] * 100, 2) if ap["altro"] and cur["altro"] else None
        mesi.append({"mese": m, "nome": MESI_IT[m], "enel": cur["enel"], "altro": cur["altro"], "tot": cur_t, "storico": cur.get("storico", False),
                     "enel_ap": ap["enel"], "altro_ap": ap["altro"], "tot_ap": ap_t, "pct": pct, "pct_enel": pct_enel, "pct_altro": pct_altro})
        for k in ("enel", "altro"):
            tot[k] += cur[k]
            tot[k + "_ap"] += ap[k]
        tot["tot"] += cur_t
        tot["tot_ap"] += ap_t
    tot = {k: round(v, 2) for k, v in tot.items()}
    tot["pct"] = round((tot["tot"] - tot["tot_ap"]) / tot["tot_ap"] * 100, 2) if tot["tot_ap"] and tot["tot"] else None
    return {"store": {"id": store["id"], "nome": store["nome"]}, "anno": anno, "mesi": mesi, "totali": tot}


FOGLI_STORICO = {"sondrio": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "0", "tot"),
                 "morbegno": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "1406738088", "split"),
                 "gravedona": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "1680449865", "tot")}
MESI_UP = [m.upper() for m in MESI_IT]


def _num_it(v: str) -> float:
    s = (v or "").strip().replace("€", "").replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _parse_storico(csv_text: str, modo: str) -> list:
    import csv
    import io
    rows = list(csv.reader(io.StringIO(csv_text)))
    header = next((r for r in rows if r and r[0].strip().lower() == "fatturato"), None)
    if not header:
        return []
    anni = []
    for i, h in enumerate(header):
        m = re.match(r"^\s*(20\d\d)\s*(ENEL|ALTRO|tot)?\s*$", h.strip(), re.I)
        if m and (modo == "tot" and not m.group(2) or modo == "split" and m.group(2) and m.group(2).lower() != "tot"):
            anni.append((int(m.group(1)), (m.group(2) or "").lower(), i))
    out = []
    for r in rows:
        nome = (r[0] if r else "").strip().upper()
        if nome not in MESI_UP or nome == "":
            continue
        mese = MESI_UP.index(nome)
        per_anno: dict = {}
        for anno, tipo, i in anni:
            v = _num_it(r[i]) if i < len(r) else 0.0
            d = per_anno.setdefault(anno, {"enel": 0.0, "altro": 0.0})
            d["enel" if tipo == "enel" else "altro"] += v
        for anno, d in per_anno.items():
            if d["enel"] or d["altro"]:
                out.append({"anno": anno, "mese": mese, **d})
    return out


@router.post("/report/importa-fogli")
async def importa_storico_fogli(request: Request):
    import httpx
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    stores = {_slug(s["nome"]): s async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    esito = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for slug, (sheet_id, gid, modo) in FOGLI_STORICO.items():
            store = stores.get(slug)
            if not store:
                esito.append({"negozio": slug, "errore": "negozio non trovato"})
                continue
            resp = await client.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}")
            if resp.status_code != 200:
                esito.append({"negozio": store["nome"], "errore": f"foglio non leggibile ({resp.status_code})"})
                continue
            righe = _parse_storico(resp.text, modo)
            for r in righe:
                await db.fatturato_storico.update_one({"store_id": store["id"], "anno": r["anno"], "mese": r["mese"]},
                                                      {"$set": {"enel": round(r["enel"], 2), "altro": round(r["altro"], 2), "fonte": "foglio_google",
                                                                "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            esito.append({"negozio": store["nome"], "mesi_importati": len(righe), "anni": sorted({r["anno"] for r in righe})})
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "import_storico", "esito": esito, "by": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()})
    return {"esito": esito}


@router.post("/pdp/importa-fogli")
async def importa_pdp_fogli_endpoint(request: Request):
    import httpx
    import pdp_import
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    centri = await _centri(user)
    stores = await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1}).to_list(100)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async def fetch(url):
            r = await client.get(url)
            r.raise_for_status()
            return r.text
        esito = await pdp_import.importa_pdp_fogli(db, fetch, centri, stores, user.get("name", ""))
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "import_pdp", "esito": esito, "by": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()})
    return {"esito": esito}


@router.post("/corrispettivi/importa-fogli")
async def importa_corrispettivi_fogli(request: Request):
    import httpx
    import contabilita_import
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async def fetch(url):
            r = await client.get(url)
            r.raise_for_status()
            return r.text
        esito = await contabilita_import.importa_tutti(_d["db"], fetch)
    await _d["db"].contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "import_corrispettivi", "esito": esito, "by": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()})
    return {"esito": esito, "giorni": sum(e.get("giorni", 0) for e in esito), "spese": sum(e.get("spese", 0) for e in esito), "errori": [e for e in esito if e.get("errore")]}


class NuovoNegozioInput(BaseModel):
    nome: str
    referente: str = ""
    telefono_avvisi: str = ""
    wa_numero: str = ""
    email_to: str = ""
    email_from: str = ""
    condividi_admin: bool = True


@router.post("/negozi")
async def nuovo_negozio(body: NuovoNegozioInput, request: Request):
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    nome = body.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome negozio obbligatorio")
    if await db.stores.find_one({"nome": {"$regex": f"^{re.escape(nome)}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="Esiste già un negozio con questo nome")
    now = datetime.now(timezone.utc).isoformat()
    store = {"id": str(uuid.uuid4()), "nome": nome, "referente": body.referente.strip(), "tipo": "negozio", "note": "", "review_link": "",
             "telefono_avvisi": re.sub(r"\D", "", body.telefono_avvisi), "email_commercialista": body.email_to.strip(), "msg_privacy": "", "msg_pronto": "",
             "msg_recensione": "", "msg_promemoria": "", "pagato": False, "last_payment_date": None, "created_at": now}
    await db.stores.insert_one(store)
    await db.contabilita_config.update_one({"store_id": store["id"]}, {"$set": {
        "store_id": store["id"], "condividi_admin": body.condividi_admin, "wa_numero": re.sub(r"\D", "", body.wa_numero), "wa_attivo": bool(body.wa_numero),
        "email_to": body.email_to.strip(), "email_from": body.email_from.strip(), "email_attivo": bool(body.email_to), "updated_at": now}}, upsert=True)
    return {"id": store["id"], "nome": nome}


@router.get("/report/confronto")
async def report_confronto(anno: int, request: Request):
    user = await _user(request)
    negozi = []
    for store, cfg, completo in await _stores_visibili(user):
        if not completo:
            continue
        mesi = []
        for m in range(1, 13):
            cur = await _fatturato_mese(store, anno, m)
            ap = await _fatturato_mese(store, anno - 1, m)
            mesi.append({"mese": m, "tot": round(cur["enel"] + cur["altro"], 2), "tot_ap": round(ap["enel"] + ap["altro"], 2)})
        tot, tot_ap = round(sum(x["tot"] for x in mesi), 2), round(sum(x["tot_ap"] for x in mesi), 2)
        negozi.append({"id": store["id"], "nome": store["nome"], "mesi": mesi, "tot": tot, "tot_ap": tot_ap,
                       "pct": round((tot - tot_ap) / tot_ap * 100, 2) if tot_ap and tot else None})
    centri = []
    for c in await _centri(user):
        mesi = []
        for m in range(1, 13):
            pdp = await _pdp_calcolo(c, anno, m)
            ha = pdp["compilato"] and pdp["tot_uscite"] > 0
            mesi.append({"mese": m, "risultato": pdp["risultato"] if ha else None, "uscite": pdp["tot_uscite"] if ha else None, "entrate": pdp["tot_entrate"] if ha else None})
        vals = [x["risultato"] for x in mesi if x["risultato"] is not None]
        centri.append({"id": c["id"], "nome": c["nome"], "mesi": mesi, "tot": round(sum(vals), 2) if vals else None})
    return {"anno": anno, "mesi": [MESI_IT[m] for m in range(1, 13)], "negozi": negozi, "centri": centri}


class StoricoInput(BaseModel):
    enel: float = 0
    altro: float = 0


@router.put("/report/storico/{store_id}/{anno}/{mese}")
async def put_storico(store_id: str, anno: int, mese: int, body: StoricoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].fatturato_storico.update_one({"store_id": store_id, "anno": anno, "mese": mese},
                                                {"$set": {"enel": _f(body.enel), "altro": _f(body.altro), "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True}
