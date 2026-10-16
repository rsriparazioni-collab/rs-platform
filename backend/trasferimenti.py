import io
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}


def setup(**deps):
    _d.update(deps)


async def _current_user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iva(regime: str) -> float:
    return 0.22 if (regime or "iva22") == "iva22" else 0.0


async def registra(da_store_id: str, a_store_id: str, item: dict, quantita: int, origine: str, user: dict,
                   servizio_id: str = "", riferimento: str = "", vendita_id: str = "", in_ordine: bool = False) -> dict:
    """Movimento tra negozi: il cedente (da) scarica, il ricevente (a) riceve. Base per la fattura tra negozi."""
    db = _d["db"]
    prezzo = item.get("prezzo_acquisto") if item.get("prezzo_acquisto") is not None else item.get("prezzo_vendita")
    doc = {"id": str(uuid.uuid4()), "da_store_id": da_store_id, "a_store_id": a_store_id, "item_id": item["id"], "nome": item.get("nome", ""),
           "categoria": item.get("categoria", ""), "regime_iva": item.get("regime_iva") or "iva22", "quantita": quantita,
           "prezzo_unitario": float(prezzo or 0), "prezzo_vendita": item.get("prezzo_vendita"), "origine": origine, "servizio_id": servizio_id,
           "riferimento": riferimento, "vendita_id": vendita_id, "in_ordine": in_ordine, "fatturato": False, "numero_fattura": "",
           "stato_consegna": "da_consegnare", "portato_da": "", "pagato": False,
           "user_name": user.get("name", ""), "at": _now(), "mese": _now()[:7]}
    await db.trasferimenti.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def annulla(servizio_id: str, item_id: str) -> None:
    await _d["db"].trasferimenti.delete_one({"servizio_id": servizio_id, "item_id": item_id, "fatturato": False})


async def annulla_vendita(vendita_id: str) -> None:
    await _d["db"].trasferimenti.delete_one({"vendita_id": vendita_id, "fatturato": False})


async def arrivato(item_id: str) -> None:
    await _d["db"].trasferimenti.update_many({"item_id": item_id, "in_ordine": True}, {"$set": {"in_ordine": False, "arrivato_at": _now()}})


def _scope(user: dict) -> dict:
    if user["role"] in ("admin", "tecnico") or user.get("can_view_all"):
        return {}
    ids = user.get("store_ids", [])
    return {"$or": [{"da_store_id": {"$in": ids}}, {"a_store_id": {"$in": ids}}]}


class FatturaInput(BaseModel):
    fatturato: bool = True
    numero_fattura: str = ""


class PrezzoInput(BaseModel):
    prezzo_unitario: float
    regime_iva: Optional[str] = None


class ConsegnaInput(BaseModel):
    portato_da: str = ""
    stato_consegna: str = ""  # da_consegnare | in_viaggio | arrivato
    pagato: Optional[bool] = None
    note_consegna: str = ""


@router.patch("/magazzino/trasferimenti/{tid}/consegna")
async def aggiorna_consegna(tid: str, input: ConsegnaInput, user: dict = Depends(_current_user)):
    """Chi porta il pezzo, quando parte/arriva e se è stato pagato (indipendente dalla fattura)."""
    if input.stato_consegna and input.stato_consegna not in ("da_consegnare", "in_viaggio", "arrivato"):
        raise HTTPException(status_code=400, detail="Stato consegna non valido")
    upd = {"consegna_updated_by": user.get("name", ""), "consegna_updated_at": _now()}
    if input.portato_da.strip():
        upd["portato_da"] = input.portato_da.strip()
    if input.note_consegna.strip():
        upd["note_consegna"] = input.note_consegna.strip()
    if input.stato_consegna:
        upd["stato_consegna"] = input.stato_consegna
        if input.stato_consegna == "in_viaggio":
            upd["partito_at"] = _now()
        if input.stato_consegna == "arrivato":
            upd["consegnato_at"] = _now()
    if input.pagato is not None:
        upd["pagato"] = input.pagato
        upd["pagato_at"] = _now() if input.pagato else None
        upd["pagato_da"] = user.get("name", "") if input.pagato else ""
    res = await _d["db"].trasferimenti.update_one({**_scope(user), "id": tid}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trasferimento non trovato")
    return await _d["db"].trasferimenti.find_one({"id": tid}, {"_id": 0})


async def _lista(user: dict, anno: int, mese: int, da_store: str, a_store: str, solo_da_fatturare: bool) -> dict:
    db = _d["db"]
    q = {**_scope(user)}
    if anno and mese:
        q["mese"] = f"{anno:04d}-{mese:02d}"
    if da_store:
        q["da_store_id"] = da_store
    if a_store:
        q["a_store_id"] = a_store
    if solo_da_fatturare:
        q["fatturato"] = False
    righe = await db.trasferimenti.find(q, {"_id": 0}).sort("at", -1).to_list(5000)
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    coppie = defaultdict(lambda: {"righe": [], "imponibile": 0.0, "iva": 0.0, "totale": 0.0, "pezzi": 0, "da_fatturare": 0.0})
    for r in righe:
        r["da_store"] = stores.get(r["da_store_id"], "-")
        r["a_store"] = stores.get(r["a_store_id"], "-")
        imp = round(r["prezzo_unitario"] * r["quantita"], 2)
        iva = round(imp * _iva(r.get("regime_iva")), 2)
        r.update({"imponibile": imp, "iva": iva, "totale": round(imp + iva, 2)})
        c = coppie[(r["da_store_id"], r["a_store_id"])]
        c["da_store"], c["a_store"], c["da_store_id"], c["a_store_id"] = r["da_store"], r["a_store"], r["da_store_id"], r["a_store_id"]
        c["righe"].append(r)
        c["imponibile"] = round(c["imponibile"] + imp, 2)
        c["iva"] = round(c["iva"] + iva, 2)
        c["totale"] = round(c["totale"] + imp + iva, 2)
        c["pezzi"] += r["quantita"]
        if not r["fatturato"]:
            c["da_fatturare"] = round(c["da_fatturare"] + imp + iva, 2)
        if not r.get("pagato"):
            c["non_pagato"] = round(c.get("non_pagato", 0.0) + imp + iva, 2)
        if r.get("stato_consegna", "da_consegnare") != "arrivato":
            c["da_consegnare"] = c.get("da_consegnare", 0) + r["quantita"]
    return {"righe": righe, "coppie": sorted(coppie.values(), key=lambda c: (c["da_store"], c["a_store"])),
            "totale": round(sum(c["totale"] for c in coppie.values()), 2), "stores": [{"id": k, "nome": v} for k, v in stores.items()]}


@router.get("/magazzino/trasferimenti")
async def lista_trasferimenti(user: dict = Depends(_current_user), anno: int = 0, mese: int = 0, da_store: str = "", a_store: str = "", solo_da_fatturare: bool = False):
    return await _lista(user, anno, mese, da_store, a_store, solo_da_fatturare)


@router.get("/magazzino/trasferimenti/export")
async def export_trasferimenti(user: dict = Depends(_current_user), anno: int = 0, mese: int = 0, da_store: str = "", a_store: str = ""):
    data = await _lista(user, anno, mese, da_store, a_store, False)
    rows = [[r["at"][:10], r["da_store"], r["a_store"], r["nome"], r.get("categoria", ""), r["quantita"], r["prezzo_unitario"], r.get("regime_iva", ""),
             r["imponibile"], r["iva"], r["totale"], r["origine"], r.get("riferimento", ""), "in ordine" if r.get("in_ordine") else "consegnato",
             r.get("portato_da", ""), {"in_viaggio": "in viaggio", "arrivato": "arrivato"}.get(r.get("stato_consegna"), "da consegnare"), (r.get("consegnato_at") or "")[:10],
             "sì" if r.get("pagato") else "no",
             "sì" if r["fatturato"] else "no", r.get("numero_fattura", ""), r.get("user_name", "")] for r in data["righe"]]
    for c in data["coppie"]:
        rows.append(["TOTALE", c["da_store"], c["a_store"], "", "", c["pezzi"], "", "", c["imponibile"], c["iva"], c["totale"], "", "", "", "", "", "", "", "", "", ""])
    fname = f"trasferimenti_{anno:04d}-{mese:02d}.xlsx" if anno and mese else "trasferimenti.xlsx"
    return _d["xlsx_response"]("Trasferimenti", ["Data", "Negozio cedente", "Negozio ricevente", "Articolo", "Categoria", "Q.tà", "Prezzo unit.", "Regime IVA",
                                                 "Imponibile", "IVA", "Totale", "Origine", "Riferimento", "Stato", "Portato da", "Consegna", "Arrivato il", "Pagato", "Fatturato", "N. fattura", "Operatore"], rows, fname)


@router.post("/magazzino/trasferimenti/{tid}/fatturato")
async def segna_fatturato(tid: str, input: FatturaInput, user: dict = Depends(_current_user)):
    res = await _d["db"].trasferimenti.update_one({**_scope(user), "id": tid}, {"$set": {"fatturato": input.fatturato, "numero_fattura": input.numero_fattura.strip(),
                                                                                       "fatturato_at": _now() if input.fatturato else None, "fatturato_da": user["name"]}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trasferimento non trovato")
    return {"ok": True}


@router.patch("/magazzino/trasferimenti/{tid}")
async def modifica_prezzo(tid: str, input: PrezzoInput, user: dict = Depends(_current_user)):
    upd = {"prezzo_unitario": input.prezzo_unitario}
    if input.regime_iva:
        upd["regime_iva"] = input.regime_iva
    res = await _d["db"].trasferimenti.update_one({**_scope(user), "id": tid, "fatturato": False}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Trasferimento non trovato o già fatturato")
    return {"ok": True}
