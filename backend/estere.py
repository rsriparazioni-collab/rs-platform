import os
import uuid
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/estere")
_d: dict = {}
TIPI = {"ue_rc": "UE con P.IVA (reverse charge TD17/TD18/TD19)", "extra_ue": "Extra-UE (IVA in dogana)", "ebay": "eBay / marketplace (reverse charge)"}
MESI_IT = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def require_admin(user: dict = Depends(_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


def _calcola(doc: dict) -> dict:
    imp = round(float(doc.get("imponibile") or 0), 2)
    pct = float(doc.get("iva_pct") if doc.get("iva_pct") is not None else 22)
    if doc["tipo"] in ("ue_rc", "ebay"):
        iva = round(imp * pct / 100, 2)
        doc.update({"iva_integrata": iva, "iva_debito": iva, "iva_credito": iva, "iva_dogana": 0.0, "costo_totale": imp,
                    "nota_fiscale": f"Reverse charge: integrazione IVA {pct:g}% a debito e a credito (saldo 0). Da trasmettere allo SdI (TD17/18/19) entro il 15 del mese successivo."})
    else:
        dog = round(float(doc.get("iva_dogana") or 0), 2)
        doc.update({"iva_integrata": 0.0, "iva_debito": 0.0, "iva_credito": dog, "costo_totale": round(imp + dog, 2),
                    "nota_fiscale": "Extra-UE: nessuna IVA in fattura; l'IVA è quella pagata in dogana (detraibile con la bolletta doganale)."})
    doc["imponibile"] = imp
    doc["iva_pct"] = pct
    return doc


class EsteraInput(BaseModel):
    centro_id: str
    data: str
    fornitore: str
    paese: str = ""
    tipo: str = "ue_rc"
    numero: str = ""
    imponibile: float
    iva_pct: Optional[float] = 22
    iva_dogana: Optional[float] = 0
    valuta: str = "EUR"
    note: str = ""
    attachment_id: str = ""


@router.get("")
async def lista(anno: int, mese: int, centro_id: str = "", user: dict = Depends(require_admin)):
    q = {"anno": anno, "mese": mese}
    if centro_id:
        q["centro_id"] = centro_id
    items = await _d["db"].fatture_estere.find(q, {"_id": 0}).sort("data", 1).to_list(500)
    tot = {"imponibile": round(sum(i["imponibile"] for i in items), 2), "iva_integrata": round(sum(i["iva_integrata"] for i in items), 2),
           "iva_dogana": round(sum(i.get("iva_dogana") or 0 for i in items), 2), "costo_totale": round(sum(i["costo_totale"] for i in items), 2),
           "da_inviare": sum(1 for i in items if not i.get("inviata_at"))}
    return {"items": items, "totali": tot, "tipi": TIPI}


@router.post("")
async def crea(body: EsteraInput, user: dict = Depends(require_admin)):
    if body.tipo not in TIPI:
        raise HTTPException(status_code=400, detail="Tipo non valido")
    try:
        d = date.fromisoformat(body.data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    if body.imponibile <= 0:
        raise HTTPException(status_code=400, detail="Imponibile obbligatorio")
    doc = _calcola({**body.model_dump(), "id": str(uuid.uuid4()), "anno": d.year, "mese": d.month, "inviata_at": None,
                    "created_at": _now().isoformat(), "created_by": user["name"]})
    await _d["db"].fatture_estere.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/fattura/{fid}")
async def modifica(fid: str, body: EsteraInput, user: dict = Depends(require_admin)):
    old = await _d["db"].fatture_estere.find_one({"id": fid}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    d = date.fromisoformat(body.data)
    doc = _calcola({**old, **body.model_dump(), "anno": d.year, "mese": d.month, "updated_at": _now().isoformat()})
    await _d["db"].fatture_estere.update_one({"id": fid}, {"$set": doc})
    return doc


@router.delete("/fattura/{fid}")
async def elimina(fid: str, user: dict = Depends(require_admin)):
    res = await _d["db"].fatture_estere.delete_one({"id": fid})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    return {"status": "ok"}


class InviataInput(BaseModel):
    inviata: bool = True


@router.post("/fattura/{fid}/inviata")
async def segna_inviata(fid: str, body: InviataInput, user: dict = Depends(require_admin)):
    res = await _d["db"].fatture_estere.update_one({"id": fid}, {"$set": {"inviata_at": _now().isoformat() if body.inviata else None, "inviata_da": user["name"] if body.inviata else None}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    return {"status": "ok"}


async def totale_pdp(centro_id: str, anno: int, mese: int) -> float:
    """Costo delle fatture estere del mese per il PDP (imponibile + IVA dogana)."""
    tot = 0.0
    async for i in _d["db"].fatture_estere.find({"centro_id": centro_id, "anno": anno, "mese": mese}, {"_id": 0, "costo_totale": 1}):
        tot += i.get("costo_totale") or 0
    return round(tot, 2)


@router.get("/riepilogo-commercialista")
async def riepilogo(anno: int, mese: int, user: dict = Depends(require_admin)):
    """Testo pronto da inviare al commercialista con le fatture estere del mese, per entità."""
    return {"testo": await _testo_riepilogo(anno, mese)}


async def _testo_riepilogo(anno: int, mese: int) -> str:
    db = _d["db"]
    centri = {c["id"]: c["nome"] for c in await _d["centri_tutti"]()}
    righe = [f"Fatture estere {MESI_IT[mese]} {anno} — da integrare/trasmettere (TD17/18/19) entro il 15/{(mese % 12) + 1:02d}"]
    n = 0
    for cid, nome in centri.items():
        items = await db.fatture_estere.find({"centro_id": cid, "anno": anno, "mese": mese}, {"_id": 0}).sort("data", 1).to_list(500)
        if not items:
            continue
        righe.append(f"\n{nome}:")
        for i in items:
            n += 1
            righe.append(f"• {i['data']} {i['fornitore']} ({i.get('paese') or '-'}) n.{i.get('numero') or '-'} — {TIPI[i['tipo']].split(' (')[0]} — imponibile € {i['imponibile']:.2f}"
                         + (f", IVA integrata € {i['iva_integrata']:.2f}" if i['iva_integrata'] else f", IVA dogana € {i.get('iva_dogana') or 0:.2f}")
                         + (" ✔ inviata" if i.get("inviata_at") else " ⏳ DA INVIARE"))
    if not n:
        righe.append("Nessuna fattura estera registrata.")
    return "\n".join(righe)


async def promemoria(giorno: int) -> dict:
    """1 e 10 del mese: estere del mese precedente non inviate; 28: verifica fatture eBay. WhatsApp all'amministratore."""
    db = _d["db"]
    cfg = await db.settings.find_one({"key": "estere_cfg"}, {"_id": 0})
    tel = ((cfg or {}).get("value") or {}).get("telefono") or os.environ.get("ESTERE_PROMEMORIA_TEL", "")
    if not tel:
        return {"inviato": False, "motivo": "telefono non configurato"}
    oggi = date.today()
    if giorno == 28:
        testo = f"🧾 Promemoria: verifica le fatture eBay/estere di {MESI_IT[oggi.month]} e caricale in Contabilità → Fatture estere, così il 1° del mese sono pronte per il commercialista."
    else:
        pm = oggi.month - 1 or 12
        pa = oggi.year if oggi.month > 1 else oggi.year - 1
        da_inviare = await db.fatture_estere.count_documents({"anno": pa, "mese": pm, "inviata_at": None})
        tot = await db.fatture_estere.count_documents({"anno": pa, "mese": pm})
        if giorno == 10 and not da_inviare:
            return {"inviato": False, "motivo": "nessuna fattura da inviare"}
        testo = (f"🧾 Fatture estere di {MESI_IT[pm]}: {tot} registrate, {da_inviare} ancora da inviare al commercialista. "
                 + ("ULTIMO AVVISO: la trasmissione TD17/18/19 scade il 15. " if giorno == 10 else "Vanno trasmesse entro il 15: mandale nei primi giorni del mese. ")
                 + "Apri Contabilità → Fatture estere → 'Testo per il commercialista'.")
    sess = await _d["store_id_by_name"]("Sondrio") or "default"
    await _d["wa_send"](tel, testo, session=sess, tipo="promemoria_estere")
    return {"inviato": True, "giorno": giorno}


class CfgInput(BaseModel):
    telefono: str


@router.get("/config")
async def get_cfg(user: dict = Depends(require_admin)):
    cfg = await _d["db"].settings.find_one({"key": "estere_cfg"}, {"_id": 0})
    return (cfg or {}).get("value") or {"telefono": ""}


@router.put("/config")
async def put_cfg(body: CfgInput, user: dict = Depends(require_admin)):
    await _d["db"].settings.update_one({"key": "estere_cfg"}, {"$set": {"value": {"telefono": body.telefono.strip()}}}, upsert=True)
    return {"telefono": body.telefono.strip()}
