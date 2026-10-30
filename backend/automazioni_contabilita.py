"""Automazioni contabilità semplici: spese ricorrenti mensili e promemoria del 1° del mese ("scarica i corrispettivi AdE").
Idempotenti: ogni spesa ricorrente viene creata al massimo una volta per mese (chiave ricorrente_id + mese)."""
import logging
import uuid
from calendar import monthrange
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("automazioni_contabilita")
router = APIRouter(prefix="/contabilita", tags=["contabilita"])
_d: dict = {}
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def setup(**deps):
    _d.update(deps)


class RicorrenteInput(BaseModel):
    store_id: str
    motivo: str
    importo: float
    giorno: int = 1
    riferimento: str = ""
    attiva: bool = True


@router.get("/spese-ricorrenti")
async def lista(store_id: str, request: Request):
    user = await _d["user"](request)
    await _d["store_completo"](user, store_id)
    return await _d["db"].spese_ricorrenti.find({"store_id": store_id}, {"_id": 0}).sort("giorno", 1).to_list(200)


@router.post("/spese-ricorrenti")
async def crea(body: RicorrenteInput, request: Request):
    user = await _d["user"](request)
    await _d["store_completo"](user, body.store_id)
    if not body.motivo.strip() or body.importo <= 0:
        raise HTTPException(status_code=400, detail="Scrivi il motivo e un importo maggiore di zero")
    if not 1 <= body.giorno <= 28:
        raise HTTPException(status_code=400, detail="Il giorno deve essere tra 1 e 28")
    doc = {**body.model_dump(), "id": str(uuid.uuid4()), "motivo": body.motivo.strip(), "importo": round(body.importo, 2), "created_at": datetime.now(timezone.utc).isoformat(), "created_by": user.get("name", "")}
    await _d["db"].spese_ricorrenti.insert_one(doc)
    doc.pop("_id", None)
    await genera_mese(date.today().year, date.today().month)
    return doc


@router.put("/spese-ricorrenti/{rid}")
async def modifica(rid: str, body: RicorrenteInput, request: Request):
    user = await _d["user"](request)
    old = await _d["db"].spese_ricorrenti.find_one({"id": rid}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Spesa ricorrente non trovata")
    await _d["store_completo"](user, old["store_id"])
    if not body.motivo.strip() or body.importo <= 0:
        raise HTTPException(status_code=400, detail="Scrivi il motivo e un importo maggiore di zero")
    if not 1 <= body.giorno <= 28:
        raise HTTPException(status_code=400, detail="Il giorno deve essere tra 1 e 28")
    upd = {**body.model_dump(), "store_id": old["store_id"], "motivo": body.motivo.strip(), "importo": round(body.importo, 2), "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name", "")}
    await _d["db"].spese_ricorrenti.update_one({"id": rid}, {"$set": upd})
    if body.attiva and not old.get("attiva"):
        await genera_mese(date.today().year, date.today().month)
    return {**old, **upd}


@router.delete("/spese-ricorrenti/{rid}")
async def elimina(rid: str, request: Request):
    user = await _d["user"](request)
    old = await _d["db"].spese_ricorrenti.find_one({"id": rid}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Spesa ricorrente non trovata")
    await _d["store_completo"](user, old["store_id"])
    await _d["db"].spese_ricorrenti.delete_one({"id": rid})
    return {"ok": True}


async def genera_mese(anno: int, mese: int) -> dict:
    """Crea le spese di cassa del mese dalle ricorrenti attive (una sola volta per ricorrente/mese; non tocca quelle già create)."""
    db = _d["db"]
    pref = f"{anno:04d}-{mese:02d}"
    create = 0
    async for r in db.spese_ricorrenti.find({"attiva": True}, {"_id": 0}):
        if await db.spese_cassa.find_one({"ricorrente_id": r["id"], "ricorrente_mese": pref}, {"_id": 0, "id": 1}):
            continue
        giorno = min(int(r.get("giorno") or 1), monthrange(anno, mese)[1])
        await db.spese_cassa.insert_one({"id": str(uuid.uuid4()), "store_id": r["store_id"], "data": f"{pref}-{giorno:02d}", "motivo": r["motivo"], "importo": round(float(r["importo"]), 2),
                                         "riferimento": r.get("riferimento") or "", "ricorrente_id": r["id"], "ricorrente_mese": pref, "created_at": datetime.now(timezone.utc).isoformat(), "created_by": "automatico (spesa ricorrente)"})
        create += 1
    return {"create": create, "mese": pref}


@router.post("/spese-ricorrenti/genera")
async def genera_ora(anno: int, mese: int, request: Request):
    user = await _d["user"](request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return await genera_mese(anno, mese)


async def promemoria_ade_primo_mese() -> dict:
    """Cron del 1° del mese: WhatsApp a ogni negozio (numero corrispettivi) → scarica i corrispettivi AdE del mese precedente e caricali; genera anche le spese ricorrenti del mese."""
    oggi = date.today()
    db = _d["db"]
    ricorrenti = await genera_mese(oggi.year, oggi.month)
    anno, mese = (oggi.year, oggi.month - 1) if oggi.month > 1 else (oggi.year - 1, 12)
    key = f"promemoria-ade-{anno}-{mese:02d}"
    if await db.scadenze_alert_log.find_one({"key": key}):
        return {"inviati": 0, "motivo": "già inviato", **ricorrenti}
    inviati = 0
    async for cfg in db.contabilita_config.find({"wa_numero": {"$nin": ["", None]}}, {"_id": 0, "store_id": 1, "wa_numero": 1}):
        store = await db.stores.find_one({"id": cfg["store_id"]}, {"_id": 0, "nome": 1})
        if not store:
            continue
        testo = (f"📥 *Corrispettivi {MESI[mese]} – {store['nome']}*\nÈ il momento di scaricare dal portale Agenzia delle Entrate (Fatture e Corrispettivi → Consultazione → Corrispettivi) il file del mese di {MESI[mese]} "
                 f"e caricarlo nel gestionale: Contabilità → Cassa & Corrispettivi → Confronto AdE.\nIl gestionale controlla da solo giorno per giorno e ti dice se c'è qualcosa da sistemare.")
        try:
            await _d["wa_send"](cfg["wa_numero"], testo, session=cfg["store_id"], tipo="promemoria_ade")
            inviati += 1
        except Exception as e:
            logger.warning(f"promemoria AdE {cfg['store_id']}: {e}")
    await db.scadenze_alert_log.insert_one({"key": key, "at": datetime.now(timezone.utc).isoformat(), "n": inviati})
    return {"inviati": inviati, **ricorrenti}
