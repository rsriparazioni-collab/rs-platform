import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()
_d: dict = {}

RICAMBIO_TIPOLOGIE = {
    "display": "Display", "batteria": "Batteria", "fotocamera": "Fotocamera", "connettore_ricarica": "Connettore ricarica",
    "vetro_posteriore": "Vetro posteriore", "altoparlante": "Altoparlante", "microfono": "Microfono", "tasti_flex": "Tasti / Flex",
    "scocca": "Scocca", "accessorio": "Accessorio", "altro": "Altro",
}
TIPOLOGIA_CATEGORIA = {"display": "display", "accessorio": "accessori"}


def setup(**deps):
    _d.update(deps)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = None
    if auth.lower().startswith("bearer "):
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
    return await _d["get_current_user"](request, creds)


def componi_nome(data: dict) -> str:
    if (data.get("nome") or "").strip():
        return data["nome"].strip()
    parts = [RICAMBIO_TIPOLOGIE.get(data.get("tipologia") or "", ""), data.get("marca") or "", data.get("modello") or ""]
    return " ".join(p for p in parts if p).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrdinaInput(BaseModel):
    magazzino_id: str = ""
    marca: str = ""
    modello: str = ""
    tipologia: str = "altro"
    quantita: int = 1
    note: str = ""
    da_store_id: str = ""  # ordina dal magazzino di un altro negozio (cedente)


class ArrivoInput(BaseModel):
    quantita: int = 1


async def _notifica_store(store_id: str, testo: str, session: str = "", **extra) -> None:
    db = _d["db"]
    store = await db.stores.find_one({"id": store_id}, {"_id": 0, "telefono_avvisi": 1, "nome": 1})
    await db.notifiche.insert_one({"id": str(uuid.uuid4()), "store_id": store_id, "testo": testo, "letta": False, "at": _now(),
                                   "tipo": extra.pop("tipo", "ricambio_richiesto"), **extra})
    if store and store.get("telefono_avvisi"):
        try:
            await _d["wa_send"](store["telefono_avvisi"], testo, session=session or store_id, tipo="avviso_negozio")
        except Exception as e:
            logger.warning("Avviso WA negozio %s fallito: %s", store_id, e)


@router.post("/servizi/{servizio_id}/ricambi/ordina")
async def ordina_ricambio(servizio_id: str, input: OrdinaInput, user: dict = Depends(_current_user)):
    """Scala il ricambio anche se assente o a zero: crea l'articolo, va in negativo e lo segna 'in ordine'."""
    db = _d["db"]
    svc = await _d["get_scoped_servizio"](servizio_id, user)
    if svc.get("tipo") != "riparazione":
        raise HTTPException(status_code=400, detail="Ricambi solo per riparazioni")
    if input.quantita < 1:
        raise HTTPException(status_code=400, detail="Quantità non valida")
    if input.tipologia not in RICAMBIO_TIPOLOGIE:
        raise HTTPException(status_code=400, detail="Tipologia non valida")
    store_id = svc.get("venditore_id")
    now = _now()
    item = None
    cedente = input.da_store_id if input.da_store_id and input.da_store_id != store_id else ""
    if cedente and input.magazzino_id:
        item = await db.magazzino.find_one({"id": input.magazzino_id, "store_id": cedente}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Articolo non trovato nel magazzino del negozio cedente")
    elif input.magazzino_id:
        item = await db.magazzino.find_one({"id": input.magazzino_id}, {"_id": 0})
        if item and item.get("store_id") != store_id:
            same = await db.magazzino.find_one({"store_id": store_id, "nome": item["nome"]}, {"_id": 0})
            item = same or {**item, "id": None}
    if not item:
        rx = lambda v: {"$regex": f"^{re.escape((v or '').strip())}$", "$options": "i"}
        if input.modello:
            item = await db.magazzino.find_one({"store_id": store_id, "tipologia": input.tipologia, "marca": rx(input.marca), "modello": rx(input.modello)}, {"_id": 0})
    if not item or not item.get("id"):
        base = item or {}
        item = {"id": str(uuid.uuid4()), "nome": base.get("nome") or componi_nome(input.model_dump()), "barcode": "", "condizione": "nuovo",
                "regime_iva": "", "categoria": base.get("categoria") or TIPOLOGIA_CATEGORIA.get(input.tipologia, "ricambi"), "store_id": store_id,
                "marca": base.get("marca") or input.marca.strip(), "modello": base.get("modello") or input.modello.strip(),
                "tipologia": base.get("tipologia") or input.tipologia, "quantita": 0, "prezzo_acquisto": base.get("prezzo_acquisto"),
                "prezzo_vendita": base.get("prezzo_vendita"), "note": input.note, "created_by": user["id"], "created_at": now, "updated_at": now}
        if not item["nome"]:
            raise HTTPException(status_code=400, detail="Indica marca/modello o seleziona un articolo")
        await db.magazzino.insert_one(dict(item))
        item.pop("_id", None)
    nuova = (item.get("quantita") or 0) - input.quantita
    await db.magazzino.update_one({"id": item["id"]}, {"$set": {"quantita": nuova, "in_ordine": True, "ordine_at": now, "ordine_servizio_id": servizio_id,
                                                              "ordine_servizio_numero": svc.get("numero_riparazione") or svc.get("numero", ""), "updated_at": now}})
    uso = {"item_id": item["id"], "nome": item["nome"], "quantita": input.quantita, "prezzo_vendita": item.get("prezzo_vendita"), "at": now, "in_ordine": True}
    if cedente:
        uso["da_store_id"] = cedente
        await _d["trasferimenti"].registra(cedente, store_id, item, input.quantita, "riparazione", user, servizio_id=servizio_id,
                                           riferimento=f"Riparazione {svc.get('numero_riparazione') or ''}".strip(), in_ordine=True)
        mio = await db.stores.find_one({"id": store_id}, {"_id": 0, "nome": 1}) or {}
        await _notifica_store(cedente, f"📦 {mio.get('nome', 'Altro negozio')} ha richiesto {input.quantita} x {item['nome']} dal vostro magazzino (esaurito): "
                              f"è stato messo in ordine a vostro carico. Al suo arrivo registrate il carico e consegnatelo.", session=store_id,
                              servizio_id=servizio_id, item_id=item["id"], da_store_id=store_id, titolo=f"Ordine per altro negozio: {item['nome']}")
    upd = {"$push": {"ricambi_usati": uso}, "$set": {"updated_at": now}}
    if svc.get("stato") in ("ingresso", "preventivo", "in_attesa_cliente", "attesa_ricambio_cliente", "in_lavorazione"):
        upd["$set"]["stato"] = "attesa_ricambio_carico"
    await db.servizi.update_one({"id": servizio_id}, upd)
    return {"status": "ok", "item_id": item["id"], "nome": item["nome"], "giacenza": nuova, "in_ordine": True}


@router.post("/magazzino/{item_id}/arrivo")
async def arrivo_ricambio(item_id: str, input: ArrivoInput, user: dict = Depends(_current_user)):
    """Carico dell'arrivo del pezzo ordinato: giacenza risale (verso 0) e le riparazioni in attesa passano in lavorazione."""
    db = _d["db"]
    scope = _d["magazzino_scope"](user)
    scope["id"] = item_id
    item = await db.magazzino.find_one(scope, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    if input.quantita < 1:
        raise HTTPException(status_code=400, detail="Quantità non valida")
    now = _now()
    nuova = (item.get("quantita") or 0) + input.quantita
    upd = {"$set": {"quantita": nuova, "updated_at": now, "ultimo_arrivo_at": now}}
    if nuova >= 0:
        upd["$unset"] = {"in_ordine": "", "ordine_at": "", "ordine_servizio_id": "", "ordine_servizio_numero": ""}
    await db.magazzino.update_one({"id": item_id}, upd)
    sbloccate = []
    vendite_pronte = []
    if nuova >= 0:
        await _d["trasferimenti"].arrivato(item_id)
        vendite_pronte = await _d["vendite_arrivato"](item_id) if _d.get("vendite_arrivato") else []
        if _d.get("vendite_registro_arrivato"):
            vendite_pronte += await _d["vendite_registro_arrivato"](item_id)
        async for s in db.servizi.find({"ricambi_usati": {"$elemMatch": {"item_id": item_id, "in_ordine": True}}}, {"_id": 0}):
            usati = [{**u, "in_ordine": False, "arrivato_at": now} if u.get("item_id") == item_id else u for u in s.get("ricambi_usati") or []]
            set_ = {"ricambi_usati": usati, "updated_at": now}
            if s.get("stato") in ("attesa_ricambio_carico", "attesa_ricambio_cliente"):
                set_["stato"] = "ricambio_arrivato"
            await db.servizi.update_one({"id": s["id"]}, {"$set": set_, "$push": {"stato_log": {"stato": "ricambio_arrivato", "at": now, "user_name": "magazzino"}}} if "stato" in set_ else {"$set": set_})
            if "stato" in set_ and _d.get("avviso_ricambio_arrivato"):
                asyncio.create_task(_d["avviso_ricambio_arrivato"]({**s, **set_}))
            sbloccate.append(s.get("numero_riparazione") or s["id"])
    return {"status": "ok", "quantita": nuova, "in_ordine": nuova < 0, "riparazioni_sbloccate": sbloccate, "vendite_pronte": vendite_pronte}


@router.get("/magazzino/da-ordinare")
async def da_ordinare(user: dict = Depends(_current_user)):
    db = _d["db"]
    scope = _d["magazzino_scope"](user)
    scope["in_ordine"] = True
    items = await db.magazzino.find(scope, {"_id": 0}).sort("ordine_at", 1).to_list(1000)
    smap = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    ids = [i["id"] for i in items]
    vendite = {v["magazzino_item_id"]: v async for v in db.vendite.find({"magazzino_item_id": {"$in": ids}, "stato": "ordinato"}, {"_id": 0, "magazzino_item_id": 1, "client_name": 1, "cliente_nome": 1, "client_telefono": 1, "acconto": 1, "prezzo": 1, "ordinato_at": 1})}
    servizi = {s["magazzino_item_id"]: s async for s in db.servizi.find({"magazzino_item_id": {"$in": ids}, "tipo": {"$in": ["vendita", "accessori"]}, "stato": "in_ordine"}, {"_id": 0, "magazzino_item_id": 1, "client_id": 1})}
    for i in items:
        i["store_name"] = smap.get(i.get("store_id", ""), "-")
        i["da_ordinare"] = -(i.get("quantita") or 0)
        v = vendite.get(i["id"])
        s = servizi.get(i["id"])
        if v:
            i.update(tipo_ordine="vendita", cliente=v.get("client_name") or v.get("cliente_nome") or "", cliente_telefono=v.get("client_telefono", ""),
                     acconto=v.get("acconto") or 0, prezzo=v.get("prezzo"))
        elif s:
            c = await db.clients.find_one({"id": s.get("client_id")}, {"_id": 0, "nome": 1, "cognome": 1, "telefono": 1})
            i.update(tipo_ordine="vendita", cliente=f"{(c or {}).get('cognome', '')} {(c or {}).get('nome', '')}".strip(), cliente_telefono=(c or {}).get("telefono", ""))
        else:
            i["tipo_ordine"] = "ricambio"
    return items


@router.get("/magazzino/tipologie")
async def tipologie():
    return [{"id": k, "label": v} for k, v in RICAMBIO_TIPOLOGIE.items()]


def _notifiche_scope(user: dict) -> dict:
    if user["role"] == "admin":
        return {}
    if user["role"] == "tecnico" or user.get("can_view_all"):
        return {"solo_admin": {"$ne": True}}
    return {"store_id": {"$in": user.get("store_ids", [])}, "solo_admin": {"$ne": True}}


@router.get("/notifiche")
async def lista_notifiche(user: dict = Depends(_current_user), solo_non_lette: bool = False):
    db = _d["db"]
    scope = _notifiche_scope(user)
    non_lette = await db.notifiche.count_documents({**scope, "letta": False})
    if solo_non_lette:
        scope["letta"] = False
    items = await db.notifiche.find(scope, {"_id": 0}).sort("at", -1).to_list(50)
    smap = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    for n in items:
        n["store_name"] = smap.get(n.get("store_id", ""), "-")
    return {"non_lette": non_lette, "items": items}


@router.post("/notifiche/{notifica_id}/letta")
async def segna_letta(notifica_id: str, user: dict = Depends(_current_user)):
    res = await _d["db"].notifiche.update_one({**_notifiche_scope(user), "id": notifica_id},
                                               {"$set": {"letta": True, "letta_at": _now(), "letta_da": user["name"]}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return {"status": "ok"}


@router.post("/notifiche/leggi-tutte")
async def segna_tutte_lette(user: dict = Depends(_current_user)):
    res = await _d["db"].notifiche.update_many({**_notifiche_scope(user), "letta": False},
                                                {"$set": {"letta": True, "letta_at": _now(), "letta_da": user["name"]}})
    return {"status": "ok", "aggiornate": res.modified_count}
