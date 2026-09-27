import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, List

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}
logger = logging.getLogger(__name__)

VOCI = {
    "fisso_mensile": "Fisso mensile",
    "cambiaora": "Contratti CambiaOra (luce/gas)",
    "sim": "SIM attivate",
    "internet": "Internet / fibra",
    "fisso": "Telefono fisso",
    "enel": "Operazioni ENEL (registro KPI)",
}
ENEL_VOCI = ["swa", "voltura", "subentro", "allaccio", "prima_attivazione", "ricontratto", "mr_servizi_enel", "chiamata_enel_eco"]
PROVENIENZE = ["Iliad", "CoopVoce", "Poste", "WindTre", "Very", "TIM", "Kena", "Vodafone", "Ho", "Fastweb", "Lyca", "Digi", "Altro"]


def setup(**deps):
    _d.update(deps)


async def _admin(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    user = await _d["get_current_user"](request, creds)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegolaInput(BaseModel):
    nome: str
    destinatario_tipo: str = "store"  # store | user
    destinatario_id: str = ""  # "" = tutti i destinatari del tipo
    voce: str
    modalita: str = "per_unita"  # per_unita | forfait
    importo: float = 0
    operatore_tel: str = ""
    tipo_attivazione: str = ""  # sim: nuovo | mnp | cambio_offerta
    provenienza_in: List[str] = []
    provenienza_not_in: List[str] = []
    enel_voci: List[str] = []
    soglia: int = 0
    conteggio_globale: bool = False
    solo_incassato: bool = False
    mesi_pagamento: int = 0
    e_gara: bool = False
    valido_da: str = ""  # YYYY-MM
    valido_a: str = ""
    attiva: bool = True
    note: str = ""


class TrattenutaInput(BaseModel):
    trattenuta_pct: float = 0
    trattenuta_iva: bool = False


class PlafondInput(BaseModel):
    store_id: str = ""
    importo: float
    causale: str = ""
    mese: str = ""


class GaraPagataInput(BaseModel):
    regola_id: str
    mese: str
    pagata: bool = True


class PerIproInput(BaseModel):
    per_ipro: bool


# ---------------- Regole CRUD ----------------
@router.get("/compensi/meta")
async def compensi_meta(admin: dict = Depends(_admin)):
    db = _d["db"]
    stores = await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1, "trattenuta_pct": 1, "trattenuta_iva": 1}).sort("nome", 1).to_list(100)
    users = await db.users.find({"active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "role": 1, "store_ids": 1}).sort("name", 1).to_list(100)
    return {"voci": VOCI, "enel_voci": ENEL_VOCI, "provenienze": PROVENIENZE, "stores": stores, "users": users}


@router.get("/compensi/regole")
async def lista_regole(admin: dict = Depends(_admin)):
    return await _d["db"].compensi_regole.find({}, {"_id": 0}).sort([("destinatario_tipo", 1), ("voce", 1), ("nome", 1)]).to_list(500)


@router.post("/compensi/regole")
async def crea_regola(input: RegolaInput, admin: dict = Depends(_admin)):
    if input.voce not in VOCI:
        raise HTTPException(status_code=400, detail="Voce non valida")
    doc = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": _now(), "updated_at": _now()}
    await _d["db"].compensi_regole.insert_one(dict(doc))
    return doc


@router.put("/compensi/regole/{regola_id}")
async def aggiorna_regola(regola_id: str, input: RegolaInput, admin: dict = Depends(_admin)):
    if input.voce not in VOCI:
        raise HTTPException(status_code=400, detail="Voce non valida")
    res = await _d["db"].compensi_regole.update_one({"id": regola_id}, {"$set": {**input.model_dump(), "updated_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Regola non trovata")
    return await _d["db"].compensi_regole.find_one({"id": regola_id}, {"_id": 0})


@router.delete("/compensi/regole/{regola_id}")
async def elimina_regola(regola_id: str, admin: dict = Depends(_admin)):
    res = await _d["db"].compensi_regole.delete_one({"id": regola_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regola non trovata")
    return {"ok": True}


@router.patch("/compensi/trattenute/{store_id}")
async def set_trattenuta(store_id: str, input: TrattenutaInput, admin: dict = Depends(_admin)):
    res = await _d["db"].stores.update_one({"id": store_id}, {"$set": input.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Negozio non trovato")
    return {"ok": True}


# ---------------- Plafond ricariche ----------------
@router.get("/compensi/plafond")
async def plafond(admin: dict = Depends(_admin)):
    db = _d["db"]
    movimenti = await db.plafond_movimenti.find({}, {"_id": 0}).sort("at", -1).to_list(500)
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    carichi = defaultdict(float)
    for m in movimenti:
        carichi[m.get("store_id", "")] += m["importo"]
    ricariche = defaultdict(float)
    async for s in db.servizi.find({"tipo": "sim", "ricarica_iniziale": {"$gt": 0}}, {"_id": 0, "venditore_id": 1, "ricarica_iniziale": 1}):
        sid = s.get("venditore_id", "")
        ricariche[sid if sid in carichi else ""] += s["ricarica_iniziale"]
    saldi = [{"store_id": sid, "store_name": stores.get(sid, "Plafond globale"), "carichi": round(carichi.get(sid, 0), 2),
              "ricariche": round(ricariche.get(sid, 0), 2), "saldo": round(carichi.get(sid, 0) - ricariche.get(sid, 0), 2)}
             for sid in sorted(set(carichi) | set(ricariche) | {""}, key=lambda x: stores.get(x, ""))]
    for m in movimenti:
        m["store_name"] = stores.get(m.get("store_id", ""), "Plafond globale")
    return {"saldi": saldi, "movimenti": movimenti[:100]}


@router.post("/compensi/plafond")
async def carica_plafond(input: PlafondInput, admin: dict = Depends(_admin)):
    doc = {"id": str(uuid.uuid4()), **input.model_dump(), "mese": input.mese or _now()[:7], "at": _now(), "user_name": admin["name"]}
    await _d["db"].plafond_movimenti.insert_one(dict(doc))
    return doc


@router.delete("/compensi/plafond/{mov_id}")
async def elimina_plafond(mov_id: str, admin: dict = Depends(_admin)):
    await _d["db"].plafond_movimenti.delete_one({"id": mov_id})
    return {"ok": True}


@router.post("/compensi/gare/pagata")
async def gara_pagata(input: GaraPagataInput, admin: dict = Depends(_admin)):
    db = _d["db"]
    if input.pagata:
        await db.compensi_gare_pagate.update_one({"regola_id": input.regola_id, "mese": input.mese},
                                                 {"$set": {"pagata_at": _now(), "user_name": admin["name"]}}, upsert=True)
    else:
        await db.compensi_gare_pagate.delete_one({"regola_id": input.regola_id, "mese": input.mese})
    return {"ok": True}


# ---------------- Per Ipro ----------------
def _puo_ipro(user: dict) -> bool:
    return user["role"] == "admin" or bool(user.get("can_assign_ipro"))


async def _current_user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


@router.post("/clients/{client_id}/per-ipro")
async def client_per_ipro(client_id: str, input: PerIproInput, user: dict = Depends(_current_user)):
    if not _puo_ipro(user):
        raise HTTPException(status_code=403, detail="Non hai il permesso di assegnare a Ipro")
    res = await _d["db"].clients.update_one({"id": client_id}, {"$set": {"per_ipro": input.per_ipro, "per_ipro_by": user["name"], "per_ipro_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    return {"per_ipro": input.per_ipro}


@router.post("/servizi/{servizio_id}/per-ipro")
async def servizio_per_ipro(servizio_id: str, input: PerIproInput, user: dict = Depends(_current_user)):
    if not _puo_ipro(user):
        raise HTTPException(status_code=403, detail="Non hai il permesso di assegnare a Ipro")
    res = await _d["db"].servizi.update_one({"id": servizio_id}, {"$set": {"per_ipro": input.per_ipro, "per_ipro_by": user["name"], "per_ipro_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Servizio non trovato")
    return {"per_ipro": input.per_ipro}


# ---------------- Calcolo ----------------
def _mese_str(anno: int, mese: int) -> str:
    return f"{anno:04d}-{mese:02d}"


def _shift(mese: str, delta: int) -> str:
    d = datetime.strptime(mese, "%Y-%m") + relativedelta(months=delta)
    return d.strftime("%Y-%m")


def _valida(regola: dict, mese: str) -> bool:
    if not regola.get("attiva", True):
        return False
    if regola.get("valido_da") and mese < regola["valido_da"]:
        return False
    if regola.get("valido_a") and mese > regola["valido_a"]:
        return False
    return True


def _mese_evento(doc: dict, campo: str) -> str:
    return ((doc.get(campo) or doc.get("created_at") or ""))[:7]


async def _eventi_mese(mese: str, ipro_store_id: str) -> dict:
    """Raccoglie gli eventi del mese: {voce: [ {store_id, user_id, ...} ]}."""
    db = _d["db"]
    eventi = defaultdict(list)
    async for c in db.clients.find({"gestione": {"$ne": "enel"}, "lavorazione": "cambio_effettuato", "anonimizzato_at": {"$in": [None]}}, {"_id": 0}):
        if _mese_evento(c, "data_contratto") != mese:
            continue
        incassato = _d["effective_pagato"](c.get("pagato", False), c.get("last_payment_date"))
        eventi["cambiaora"].append(_ev(c, ipro_store_id, incassato=incassato))
    async for s in db.servizi.find({"tipo": {"$in": ["sim", "internet", "fisso"]}}, {"_id": 0}):
        if _mese_evento(s, "data_attivazione") != mese:
            continue
        eventi[s["tipo"]].append(_ev(s, ipro_store_id, operatore_tel=(s.get("operatore_tel") or "").strip().lower(),
                                     tipo_attivazione=s.get("tipo_attivazione", ""), provenienza=(s.get("provenienza_operatore") or "").strip().lower(),
                                     incassato=bool(s.get("pagato")), ricarica=float(s.get("ricarica_iniziale") or 0), costo_sim=float(s.get("costo_sim") or 0)))
    async for a in db.attivita.find({"data": {"$gte": mese + "-01", "$lte": mese + "-31"}, "voce": {"$in": ENEL_VOCI}}, {"_id": 0}):
        per_ipro = False
        if a.get("client_id"):
            cli = await db.clients.find_one({"id": a["client_id"]}, {"_id": 0, "per_ipro": 1})
            per_ipro = bool(cli and cli.get("per_ipro"))
        for _ in range(int(a.get("quantita", 1))):
            eventi["enel"].append({"store_id": ipro_store_id if per_ipro else a.get("store_id", ""), "user_id": a["user_id"], "per_ipro": per_ipro,
                                   "enel_voce": a["voce"], "incassato": True})
    return eventi


def _ev(doc: dict, ipro_store_id: str, **extra) -> dict:
    per_ipro = bool(doc.get("per_ipro"))
    return {"store_id": ipro_store_id if per_ipro else doc.get("venditore_id", ""), "user_id": doc.get("operatore_id") or doc.get("created_by") or "",
            "per_ipro": per_ipro, "id": doc.get("id"), **extra}


def _match(regola: dict, e: dict) -> bool:
    ops = [o.strip().lower() for o in (regola.get("operatore_tel") or "").split(",") if o.strip()]
    if ops and e.get("operatore_tel") not in ops:
        return False
    if regola.get("tipo_attivazione") and e.get("tipo_attivazione") != regola["tipo_attivazione"]:
        return False
    p_in = [p.lower() for p in regola.get("provenienza_in") or []]
    p_out = [p.lower() for p in regola.get("provenienza_not_in") or []]
    if p_in and e.get("provenienza", "") not in p_in:
        return False
    if p_out and e.get("provenienza", "") in p_out:
        return False
    if regola.get("enel_voci") and e.get("enel_voce") not in regola["enel_voci"]:
        return False
    if regola.get("solo_incassato") and not e.get("incassato"):
        return False
    return True


def _appartiene(e: dict, tipo: str, dest_id: str) -> bool:
    if tipo == "store":
        return e["store_id"] == dest_id
    return not e["per_ipro"] and e["user_id"] == dest_id


async def calcola(mese: str, per_pagamento: bool = False) -> dict:
    """Se per_pagamento=True, `mese` è il mese in cui si paga: ogni regola guarda la competenza mese - mesi_pagamento."""
    db = _d["db"]
    stores = await db.stores.find({}, {"_id": 0}).to_list(100)
    users = await db.users.find({"active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "store_ids": 1}).to_list(100)
    ipro = next((s for s in stores if s["nome"].strip().lower() == "ipro"), None)
    ipro_id = ipro["id"] if ipro else "__ipro__"
    regole = [r for r in await db.compensi_regole.find({"attiva": True}, {"_id": 0}).to_list(500)]
    gare_pagate = {(g["regola_id"], g["mese"]) async for g in db.compensi_gare_pagate.find({}, {"_id": 0})}
    eventi_cache: dict = {}

    async def eventi(m: str) -> dict:
        if m not in eventi_cache:
            eventi_cache[m] = await _eventi_mese(m, ipro_id)
        return eventi_cache[m]

    destinatari = [("store", s["id"], s["nome"], s) for s in stores] + [("user", u["id"], u["name"], u) for u in users]
    out = []
    for tipo, dest_id, nome, obj in destinatari:
        righe = []
        for r in regole:
            if r["destinatario_tipo"] != tipo or (r.get("destinatario_id") and r["destinatario_id"] != dest_id):
                continue
            competenza = _shift(mese, -int(r.get("mesi_pagamento") or 0)) if per_pagamento else mese
            if not _valida(r, competenza):
                continue
            if r["voce"] == "fisso_mensile":
                righe.append({"regola_id": r["id"], "nome": r["nome"], "voce": r["voce"], "conteggio": 1, "importo_unitario": r["importo"], "totale": round(r["importo"], 2),
                              "competenza": competenza, "pagamento": _shift(competenza, int(r.get("mesi_pagamento") or 0)), "e_gara": False, "gara_pagata": True})
                continue
            ev = await eventi(competenza)
            match_tutti = [e for e in ev.get(r["voce"], []) if _match(r, e)]
            propri = [e for e in match_tutti if _appartiene(e, tipo, dest_id)]
            base = len(match_tutti) if r.get("conteggio_globale") else len(propri)
            if not propri:
                continue
            raggiunta = not r.get("soglia") or base >= r["soglia"]
            totale = 0.0
            if raggiunta:
                totale = r["importo"] if r["modalita"] == "forfait" else r["importo"] * len(propri)
            pagata = (r["id"], competenza) in gare_pagate if r.get("e_gara") else True
            righe.append({"regola_id": r["id"], "nome": r["nome"], "voce": r["voce"], "conteggio": len(propri), "conteggio_globale": base if r.get("conteggio_globale") else None,
                          "soglia": r.get("soglia") or 0, "soglia_raggiunta": raggiunta, "importo_unitario": r["importo"], "modalita": r["modalita"],
                          "totale": round(totale, 2), "competenza": competenza, "pagamento": _shift(competenza, int(r.get("mesi_pagamento") or 0)),
                          "e_gara": bool(r.get("e_gara")), "gara_pagata": pagata})
        ev_mese = await eventi(mese)
        sim_propri = [e for e in ev_mese.get("sim", []) if _appartiene(e, tipo, dest_id)]
        ricariche = round(sum(e.get("ricarica", 0) for e in sim_propri), 2)
        costo_sim = round(sum(e.get("costo_sim", 0) for e in sim_propri), 2)
        if not righe and not ricariche and not costo_sim:
            continue
        lordo = round(sum(x["totale"] for x in righe if x["gara_pagata"]), 2)
        in_attesa = round(sum(x["totale"] for x in righe if not x["gara_pagata"]), 2)
        pct = float(obj.get("trattenuta_pct") or 0) if tipo == "store" else 0.0
        trattenuta = round(lordo * pct / 100, 2)
        iva = round(trattenuta * 0.22, 2) if tipo == "store" and obj.get("trattenuta_iva") else 0.0
        out.append({"tipo": tipo, "id": dest_id, "nome": nome, "righe": righe, "lordo": lordo, "gare_in_attesa": in_attesa,
                    "trattenuta_pct": pct, "trattenuta": trattenuta, "iva_su_trattenuta": iva, "netto": round(lordo - trattenuta - iva, 2),
                    "ricariche_da_richiedere": ricariche, "costo_sim": costo_sim})
    return {"mese": mese, "per_pagamento": per_pagamento, "destinatari": out, "totale_netto": round(sum(d["netto"] for d in out), 2)}


@router.get("/compensi/calcolo")
async def compensi_calcolo(anno: int, mese: int, per_pagamento: bool = False, admin: dict = Depends(_admin)):
    return await calcola(_mese_str(anno, mese), per_pagamento)


# ---------------- Seed regole iniziali ----------------
async def seed() -> None:
    db = _d["db"]
    stores = {s["nome"].strip().lower(): s["id"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    for nome, pct, iva in (("tirano", 15, False), ("sondalo", 15, False), ("grosio", 15, True)):
        if nome in stores:
            await db.stores.update_one({"id": stores[nome], "trattenuta_pct": {"$exists": False}}, {"$set": {"trattenuta_pct": pct, "trattenuta_iva": iva}})
    await db.users.update_one({"name": {"$regex": "^deborah$", "$options": "i"}, "can_assign_ipro": {"$exists": False}}, {"$set": {"can_assign_ipro": True}})
    if await db.compensi_regole.count_documents({}) > 0:
        return
    base = {"destinatario_tipo": "store", "destinatario_id": "", "modalita": "per_unita", "operatore_tel": "", "tipo_attivazione": "", "provenienza_in": [],
            "provenienza_not_in": [], "enel_voci": [], "soglia": 0, "conteggio_globale": False, "solo_incassato": False, "mesi_pagamento": 0, "e_gara": False,
            "valido_da": "", "valido_a": "", "attiva": True, "note": "", "created_at": _now(), "updated_at": _now()}
    regole = [
        {"nome": "CambiaOra – contratto incassato (pagato a 2 mesi)", "voce": "cambiaora", "importo": 0, "solo_incassato": True, "mesi_pagamento": 2,
         "note": "Inserisci l'importo per contratto. Es. luglio viene pagato a settembre."},
        {"nome": "WindTre/Very – MNP compenso base", "voce": "sim", "operatore_tel": "WINDTRE,VERY", "tipo_attivazione": "mnp", "importo": 0, "note": "Compenso base X per MNP"},
        {"nome": "WindTre/Very – extra MNP da Iliad/CoopVoce/Poste (≥15 MNP globali)", "voce": "sim", "operatore_tel": "WINDTRE,VERY", "tipo_attivazione": "mnp",
         "provenienza_in": ["Iliad", "CoopVoce", "Poste"], "importo": 35, "soglia": 15, "conteggio_globale": True},
        {"nome": "WindTre/Very – extra MNP da altri operatori (≥15 MNP globali)", "voce": "sim", "operatore_tel": "WINDTRE,VERY", "tipo_attivazione": "mnp",
         "provenienza_not_in": ["Iliad", "CoopVoce", "Poste"], "importo": 15, "soglia": 15, "conteggio_globale": True},
        {"nome": "WindTre/Very – numero nuovo", "voce": "sim", "operatore_tel": "WINDTRE,VERY", "tipo_attivazione": "nuovo", "importo": 0},
        {"nome": "Lyca – SIM (solo Sondrio, 0 €: genera plafond)", "voce": "sim", "operatore_tel": "LYCA", "importo": 0, "destinatario_id": stores.get("sondrio", "")},
        {"nome": "Eolo – report inserito (pagato nel mese)", "voce": "internet", "operatore_tel": "EOLO", "importo": 0},
        {"nome": "Eolo – gara trimestrale (pagata a 3 mesi, a incasso avvenuto)", "voce": "internet", "operatore_tel": "EOLO", "modalita": "forfait", "importo": 0,
         "soglia": 1, "mesi_pagamento": 3, "e_gara": True, "note": "Imposta soglia e importo della gara Eolo in corso"},
        {"nome": "Kena – SIM", "voce": "sim", "operatore_tel": "KENA", "importo": 0, "note": "Regole Kena da definire"},
        {"nome": "Iliad – SIM", "voce": "sim", "operatore_tel": "ILIAD", "importo": 0, "note": "Regole Iliad da definire"},
        {"nome": "Ho – SIM", "voce": "sim", "operatore_tel": "HO", "importo": 0, "note": "Regole Ho da definire"},
        {"nome": "Fastweb – SIM", "voce": "sim", "operatore_tel": "FASTWEB", "importo": 0, "note": "Regole Fastweb da definire"},
        {"nome": "Ipro – operazioni ENEL", "voce": "enel", "importo": 0, "destinatario_id": stores.get("ipro", ""), "enel_voci": ENEL_VOCI,
         "note": "Compenso per operazione ENEL attribuita a Ipro"},
    ]
    await db.compensi_regole.insert_many([{"id": str(uuid.uuid4()), **base, **r} for r in regole])
    logger.info("Seed regole compensi completato")
