"""Scadenzario F24 / affitti: scadenze reali inserite a mano (IVA, INPS, F24, affitto, altro), anche ricorrenti mensili,
+ stime del piano fiscale. Avviso WhatsApp all'amministrazione N giorni prima e il giorno stesso se non pagata. Solo promemoria: non entra nel PDP."""
import logging
import uuid
from calendar import monthrange
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("scadenzario")
router = APIRouter(prefix="/scadenzario", tags=["scadenzario"])
_d: dict = {}
TIPI = ("iva", "inps", "f24", "affitto", "altro")
TIPO_LABEL = {"iva": "IVA", "inps": "INPS", "f24": "F24 / imposte", "affitto": "Affitto", "altro": "Altro"}


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _admin(request: Request) -> dict:
    user = await _d["user"](request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


class ScadenzaInput(BaseModel):
    centro_id: str
    tipo: str = "f24"
    voce: str
    importo: float = Field(ge=0)
    data: str
    ricorrenza: str = "nessuna"  # nessuna | mensile
    fino_a: Optional[str] = None  # per mensile: ultimo mese (YYYY-MM-DD), opzionale
    note: str = ""


def _clamp(anno: int, mese: int, giorno: int) -> str:
    return date(anno, mese, min(giorno, monthrange(anno, mese)[1])).isoformat()


def _istanze(docs: list, anno: int, mese: int) -> list:
    """Scadenze del mese: singole + istanze virtuali delle ricorrenti (id = 'tplid:YYYY-MM')."""
    pref = f"{anno:04d}-{mese:02d}"
    out = []
    for s in docs:
        if s.get("ricorrenza") == "mensile":
            if s["data"][:7] > pref or (s.get("fino_a") and s["fino_a"][:7] < pref):
                continue
            iid = f"{s['id']}:{pref}"
            out.append({**s, "id": iid, "template_id": s["id"], "data": _clamp(anno, mese, int(s["data"][8:10])), "pagata_at": (s.get("pagate") or {}).get(pref)})
        elif s["data"][:7] == pref:
            out.append({k: v for k, v in s.items() if k != "pagate"})
    return out


async def _docs(db, centro_ids: list) -> list:
    return await db.scadenze_f24.find({"centro_id": {"$in": centro_ids}}, {"_id": 0}).to_list(2000)


@router.get("")
async def lista(anno: int, mese: int, request: Request):
    user = await _d["user"](request)
    db = _d["db"]
    centri = await _d["centri"](user)
    nomi = {c["id"]: c["nome"] for c in centri}
    items = _istanze(await _docs(db, list(nomi)), anno, mese)
    for i in items:
        i["centro_nome"] = nomi.get(i["centro_id"], i["centro_id"])
    stime = []
    pref = f"{anno:04d}-{mese:02d}"
    for c in centri:
        try:
            p = await _d["piano"](c, anno)
        except Exception as e:  # il piano può fallire senza dati
            logger.warning(f"piano fiscale {c['id']}: {e}")
            continue
        for s in p["scadenze"]:
            if s["data"][:7] == pref and s["importo"] > 0:
                stime.append({**s, "centro_id": c["id"], "centro_nome": c["nome"]})
    items.sort(key=lambda s: s["data"])
    oggi = date.today().isoformat()
    tot = round(sum(i["importo"] for i in items), 2)
    da_pagare = round(sum(i["importo"] for i in items if not i.get("pagata_at")), 2)
    scadute = [i for i in items if not i.get("pagata_at") and i["data"] < oggi]
    cfg = await db.settings.find_one({"key": "scadenzario_cfg"}, {"_id": 0}) or {}
    return {"items": items, "stime_piano": sorted(stime, key=lambda s: s["data"]), "totale": tot, "da_pagare": da_pagare, "scadute": len(scadute),
            "giorni_preavviso": (cfg.get("value") or {}).get("giorni_preavviso", 5), "tipi": TIPO_LABEL,
            "nota": "Lo scadenzario è solo un promemoria: gli importi non entrano nel PDP. Le stime del piano fiscale vanno confermate col commercialista."}


@router.post("")
async def crea(body: ScadenzaInput, request: Request):
    user = await _admin(request)
    if body.tipo not in TIPI:
        raise HTTPException(status_code=400, detail="Tipo non valido")
    if body.ricorrenza not in ("nessuna", "mensile"):
        raise HTTPException(status_code=400, detail="Ricorrenza non valida")
    try:
        date.fromisoformat(body.data)
        if body.fino_a:
            date.fromisoformat(body.fino_a)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    await _d["centro"](user, body.centro_id)
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "pagata_at": None, "pagate": {}, "creato_da": user["name"], "created_at": _now().isoformat()}
    await _d["db"].scadenze_f24.insert_one(doc)
    doc.pop("_id", None)
    return doc


class PagataInput(BaseModel):
    pagata: bool


@router.put("/{sid}/pagata")
async def segna_pagata(sid: str, body: PagataInput, request: Request):
    await _admin(request)
    db = _d["db"]
    val = _now().isoformat() if body.pagata else None
    if ":" in sid:
        tpl, pref = sid.split(":", 1)
        res = await db.scadenze_f24.update_one({"id": tpl}, {"$set": {f"pagate.{pref}": val}})
    else:
        res = await db.scadenze_f24.update_one({"id": sid}, {"$set": {"pagata_at": val}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Scadenza non trovata")
    return {"ok": True, "pagata_at": val}


@router.delete("/{sid}")
async def elimina(sid: str, request: Request):
    await _admin(request)
    tpl = sid.split(":", 1)[0]
    res = await _d["db"].scadenze_f24.delete_one({"id": tpl})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Scadenza non trovata")
    return {"ok": True}


class CfgInput(BaseModel):
    giorni_preavviso: int = Field(ge=1, le=30)


@router.put("/config")
async def set_cfg(body: CfgInput, request: Request):
    await _admin(request)
    await _d["db"].settings.update_one({"key": "scadenzario_cfg"}, {"$set": {"value": {"giorni_preavviso": body.giorni_preavviso}}}, upsert=True)
    return {"ok": True, "giorni_preavviso": body.giorni_preavviso}


def _eur(v: float) -> str:
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def alert_scadenze() -> dict:
    """Cron giornaliero: WhatsApp all'amministrazione per le scadenze manuali tra N giorni e per quelle di oggi non pagate (una volta per scadenza/giorno)."""
    db = _d["db"]
    cfg = await db.settings.find_one({"key": "scadenzario_cfg"}, {"_id": 0}) or {}
    n = (cfg.get("value") or {}).get("giorni_preavviso", 5)
    oggi = date.today()
    admin = await db.users.find_one({"role": "admin"}, {"_id": 0}) or {"role": "admin"}
    centri = {c["id"]: c["nome"] for c in await _d["centri"](admin)}
    docs = await _docs(db, list(centri))
    righe = []
    for target, label in ((oggi + timedelta(days=n), f"tra {n} giorni"), (oggi, "OGGI")):
        for s in _istanze(docs, target.year, target.month):
            if s["data"] != target.isoformat() or s.get("pagata_at"):
                continue
            key = f"{s['id']}|{label}"
            if await db.scadenze_alert_log.find_one({"key": key}):
                continue
            righe.append(f"• {label} ({s['data'][8:]}/{s['data'][5:7]}) — {centri.get(s['centro_id'], '')}: {TIPO_LABEL.get(s['tipo'], s['tipo'])} {s['voce']} {_eur(s['importo'])}")
            await db.scadenze_alert_log.insert_one({"id": str(uuid.uuid4()), "key": key, "scadenza_id": s["id"], "data": s["data"], "sent_at": _now().isoformat()})
    if not righe:
        return {"inviati": 0}
    testo = "📅 *Scadenzario F24 / affitti*\n" + "\n".join(righe) + "\nSegna come pagata in Contabilità → Scadenzario."
    try:
        await _d["wa_send"](_d["numero_amministrazione"], testo, session=await _d["store_id_by_name"]("Sondrio") or "default", tipo="scadenzario")
    except HTTPException as e:
        logger.warning(f"WA scadenzario non inviato: {e.detail}")
        return {"inviati": 0, "errore": e.detail}
    return {"inviati": len(righe)}
