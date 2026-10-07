import csv
import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

VENDITE_CATEGORIE = ["telefono_nuovo", "telefono_rigenerato", "telefono_ricondizionato", "telefono_usato", "pc", "router", "accessori", "stampanti", "altro"]
REGIMI_IVA = ["iva22", "art36", "art17"]
CATEGORIE_USATO = {"telefono_rigenerato", "telefono_ricondizionato", "telefono_usato"}
IVA_DEFAULT = {"telefono_usato": "art36"}
STATI_VENDITA = ["ordinato", "arrivato", "consegnato"]
MSG_ORDINATO = "Ciao {nome}! 😊\nIl tuo nuovo {articolo} è stato ordinato. Grazie di averci scelto!\nTi avviseremo appena arriva in negozio.\n{negozio}"
MSG_ARRIVATO = "Ciao {nome}! 😊\nIl tuo telefono {articolo} è arrivato in negozio: ti aspettiamo per prepararlo insieme e partire con la tua nuova esperienza!{saldo}\n{negozio}"
SHEET_PREFIX_STORE = {"M": "Morbegno", "SO": "Sondrio", "G": "Gravedona"}

router = APIRouter()
_deps: dict = {}


def setup(db, get_current_user, magazzino_scope, log_audit=None, **extra):
    _deps.update(db=db, get_current_user=get_current_user, magazzino_scope=magazzino_scope, log_audit=log_audit, **extra)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = None
    if auth.lower().startswith("bearer "):
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
    return await _deps["get_current_user"](request, creds)


def _user():
    return Depends(_current_user)


class VenditaInput(BaseModel):
    store_id: str
    client_id: str = ""
    cliente_nome: str = ""
    categoria: str = "telefono_nuovo"
    regime_iva: str = "iva22"
    articolo: str
    marca: str = ""
    modello: str = ""
    imei: str = ""
    magazzino_item_id: str = ""
    quantita: int = 1
    prezzo: float
    costo: Optional[float] = None
    pagamento: str = ""
    numero_fattura: str = ""
    data_vendita: Optional[str] = None
    note: str = ""
    ritiro_id: str = ""
    stato: str = "consegnato"
    pagato: bool = True
    acconto: float = 0
    fornitore: str = ""


class StatoVenditaInput(BaseModel):
    stato: str
    pagato: Optional[bool] = None
    numero_fattura: Optional[str] = None


def vendite_scope(user: dict) -> dict:
    if user["role"] in ("admin", "tecnico") or user.get("can_view_all"):
        return {}
    return {"store_id": {"$in": user.get("store_ids", [])}}


def _valida(data: dict) -> None:
    if data["categoria"] not in VENDITE_CATEGORIE:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    if data["regime_iva"] not in REGIMI_IVA:
        raise HTTPException(status_code=400, detail="Regime IVA non valido")
    if data["categoria"] not in CATEGORIE_USATO:
        data["regime_iva"] = "iva22"
    if data.get("stato") not in STATI_VENDITA:
        raise HTTPException(status_code=400, detail="Stato vendita non valido")
    data["acconto"] = max(float(data.get("acconto") or 0), 0)
    if data["acconto"] > data["prezzo"] * data["quantita"]:
        raise HTTPException(status_code=400, detail="L'acconto supera il prezzo")
    if data["prezzo"] < 0 or data["quantita"] < 1:
        raise HTTPException(status_code=400, detail="Prezzo o quantità non validi")
    if not data.get("client_id") and not (data.get("cliente_nome") or "").strip():
        raise HTTPException(status_code=400, detail="Indica il cliente")


async def _arricchisci(v: dict) -> dict:
    db = _deps["db"]
    if v.get("client_id") and not v.get("client_name"):
        c = await db.clients.find_one({"id": v["client_id"]}, {"_id": 0, "nome": 1, "cognome": 1, "telefono": 1})
        if c:
            v["client_name"] = f"{c.get('cognome', '')} {c.get('nome', '')}".strip()
            v["client_telefono"] = c.get("telefono", "")
    return v


async def _wa_vendita(v: dict, template: str, tipo: str, saldo_txt: str = "") -> None:
    """WhatsApp al cliente dal numero del negozio della vendita; esito salvato sulla vendita."""
    db = _deps["db"]
    c = await db.clients.find_one({"id": v.get("client_id")}, {"_id": 0, "nome": 1, "telefono": 1}) if v.get("client_id") else None
    store = await db.stores.find_one({"id": v["store_id"]}, {"_id": 0, "nome": 1})
    key = f"wa_{tipo}"
    if not c or not c.get("telefono"):
        await db.vendite.update_one({"id": v["id"]}, {"$set": {f"{key}_error": "Cliente senza numero di telefono"}})
        return
    msg = template.format(nome=c.get("nome", ""), articolo=v.get("articolo", ""), negozio=(store or {}).get("nome", ""), saldo=saldo_txt)
    try:
        await _deps["wa_send"](c["telefono"], msg, session=v["store_id"], tipo=f"vendita_{tipo}", client_id=v["client_id"])
        await db.vendite.update_one({"id": v["id"]}, {"$set": {f"{key}_sent_at": datetime.now(timezone.utc).isoformat(), f"{key}_error": None}})
    except Exception as e:
        await db.vendite.update_one({"id": v["id"]}, {"$set": {f"{key}_error": str(getattr(e, "detail", e))[:200]}})


async def _accoda_recensione(v: dict) -> None:
    if v.get("client_id") and _deps.get("accoda_recensione"):
        try:
            await _deps["accoda_recensione"](v["client_id"], v["store_id"])
            await _deps["db"].vendite.update_one({"id": v["id"]}, {"$set": {"review_queued_at": datetime.now(timezone.utc).isoformat()}})
        except Exception as e:
            await _deps["db"].vendite.update_one({"id": v["id"]}, {"$set": {"review_error": str(e)[:200]}})


async def _crea_item_ordine(data: dict) -> dict:
    """Articolo di magazzino creato al volo per una vendita su ordinazione (giacenza parte da 0)."""
    now = datetime.now(timezone.utc).isoformat()
    cond = {"telefono_usato": "usato", "telefono_rigenerato": "rigenerato", "telefono_ricondizionato": "rigenerato"}.get(data["categoria"], "nuovo")
    cat = "rigenerati" if cond != "nuovo" else ("accessori" if data["categoria"] == "accessori" else "telefoni")
    item = {"id": str(uuid.uuid4()), "nome": data["articolo"][:120], "barcode": (data.get("imei") or "")[:60], "condizione": cond, "regime_iva": data["regime_iva"],
            "categoria": cat, "store_id": data["store_id"], "quantita": 0, "prezzo_acquisto": data.get("costo"), "prezzo_vendita": data["prezzo"],
            "marca": (data.get("marca") or "")[:60], "modello": (data.get("modello") or "")[:60], "tipologia": "", "fornitore": (data.get("fornitore") or "")[:60],
            "note": "Ordinato per vendita cliente", "created_at": now, "updated_at": now}
    await _deps["db"].magazzino.insert_one(dict(item))
    return item


@router.get("/vendite/meta")
async def vendite_meta(user: dict = _user()):
    return {"categorie": VENDITE_CATEGORIE, "regimi_iva": REGIMI_IVA, "iva_default": IVA_DEFAULT, "stati": STATI_VENDITA}


@router.get("/vendite")
async def list_vendite(user: dict = _user(), store_id: str = "", categoria: str = "", regime_iva: str = "",
                       client_id: str = "", q: str = "", da: str = "", a: str = ""):
    db = _deps["db"]
    scope = vendite_scope(user)
    if store_id:
        scope["store_id"] = store_id
    if categoria:
        scope["categoria"] = categoria
    if regime_iva:
        scope["regime_iva"] = regime_iva
    if client_id:
        scope["client_id"] = client_id
    if da or a:
        rng = {}
        if da:
            rng["$gte"] = da
        if a:
            rng["$lte"] = a + "T23:59:59"
        scope["data_vendita"] = rng
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        scope["$or"] = [{"articolo": rx}, {"client_name": rx}, {"cliente_nome": rx}, {"imei": rx}, {"numero_fattura": rx}, {"modello": rx}]
    rows = await db.vendite.find(scope, {"_id": 0}).sort("data_vendita", -1).to_list(3000)
    return rows


@router.get("/vendite/stats")
async def vendite_stats(user: dict = _user(), store_id: str = "", da: str = "", a: str = ""):
    db = _deps["db"]
    scope = vendite_scope(user)
    if store_id:
        scope["store_id"] = store_id
    if da or a:
        rng = {}
        if da:
            rng["$gte"] = da
        if a:
            rng["$lte"] = a + "T23:59:59"
        scope["data_vendita"] = rng
    rows = await db.vendite.find(scope, {"_id": 0, "categoria": 1, "regime_iva": 1, "prezzo": 1, "costo": 1, "quantita": 1}).to_list(10000)
    per_cat = {c: {"n": 0, "incasso": 0.0, "margine": 0.0} for c in VENDITE_CATEGORIE}
    per_iva = {r: {"n": 0, "incasso": 0.0} for r in REGIMI_IVA}
    tot = {"n": 0, "incasso": 0.0, "margine": 0.0}
    for r in rows:
        q = r.get("quantita") or 1
        inc = float(r.get("prezzo") or 0) * q
        mar = inc - float(r.get("costo") or 0) * q if r.get("costo") is not None else 0.0
        c = per_cat.setdefault(r.get("categoria", "altro"), {"n": 0, "incasso": 0.0, "margine": 0.0})
        c["n"] += 1; c["incasso"] += inc; c["margine"] += mar
        i = per_iva.setdefault(r.get("regime_iva", "iva22"), {"n": 0, "incasso": 0.0})
        i["n"] += 1; i["incasso"] += inc
        tot["n"] += 1; tot["incasso"] += inc; tot["margine"] += mar
    return {"totale": tot, "per_categoria": per_cat, "per_iva": per_iva}


@router.post("/vendite")
async def create_vendita(input: VenditaInput, user: dict = _user()):
    db = _deps["db"]
    data = input.model_dump()
    _valida(data)
    if not data.get("client_id"):
        raise HTTPException(status_code=400, detail="Ogni vendita deve avere un cliente in anagrafica: cerca il cliente o crealo con '+ Nuovo cliente'")
    if user["role"] == "negozio" and data["store_id"] not in user.get("store_ids", []):
        raise HTTPException(status_code=403, detail="Puoi registrare vendite solo per il tuo negozio")
    now = datetime.now(timezone.utc)
    data.update({"id": str(uuid.uuid4()), "created_by": user["id"], "created_by_name": user["name"],
                 "created_at": now.isoformat(), "updated_at": now.isoformat(),
                 "data_vendita": data.get("data_vendita") or now.isoformat()})
    data["stato_log"] = [{"stato": data["stato"], "at": now.isoformat(), "by": user["name"]}]
    if data["stato"] == "ordinato":
        data["pagato"] = False
        data["ordinato_at"] = now.isoformat()
        item = await db.magazzino.find_one({"id": data["magazzino_item_id"]}, {"_id": 0}) if data.get("magazzino_item_id") else None
        if not item:
            item = await _crea_item_ordine(data)
            data["magazzino_item_id"] = item["id"]
        await db.magazzino.update_one({"id": item["id"]}, {"$inc": {"quantita": -data["quantita"]}, "$set": {
            "in_ordine": True, "ordine_at": now.isoformat(), "ordine_vendita_id": data["id"], "fornitore": (data.get("fornitore") or item.get("fornitore") or "")[:60],
            "ordine_servizio_numero": f"Vendita {data.get('client_name') or data.get('cliente_nome') or ''}".strip(), "updated_at": now.isoformat()}})
        data["magazzino_nome"] = item.get("nome")
        await _arricchisci(data)
        await db.vendite.insert_one(dict(data))
        data.pop("_id", None)
        await _wa_vendita(data, MSG_ORDINATO, "ordinato")
        return data
    if data["stato"] == "arrivato":
        data["pagato"] = False
        data["arrivato_at"] = now.isoformat()
    if data.get("magazzino_item_id"):
        item = await db.magazzino.find_one({"id": data["magazzino_item_id"]}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Articolo di magazzino non trovato")
        if (item.get("quantita") or 0) < data["quantita"]:
            raise HTTPException(status_code=400, detail=f"Giacenza insufficiente ({item.get('quantita') or 0})")
        if data.get("costo") is None and item.get("prezzo_acquisto") is not None:
            data["costo"] = float(item["prezzo_acquisto"])
        upd = {"$inc": {"quantita": -data["quantita"]}, "$set": {"updated_at": now.isoformat()}}
        if item.get("categoria") == "rigenerati" and (item.get("quantita") or 0) - data["quantita"] <= 0:
            upd["$set"].update({"stato": "venduto", "venduto_at": now.isoformat(), "venduto_prezzo": data["prezzo"],
                                "venduto_da": user["name"], "margine": data["prezzo"] - float(item.get("prezzo_acquisto") or 0)})
        await db.magazzino.update_one({"id": item["id"]}, upd)
        data["magazzino_nome"] = item.get("nome")
        if item.get("store_id") and item.get("store_id") != data["store_id"]:
            import trasferimenti as _tr
            await _tr.registra(item["store_id"], data["store_id"], item, data["quantita"], "vendita", user, vendita_id=data["id"],
                               riferimento=f"Vendita {data.get('descrizione') or item.get('nome', '')}"[:80])
        if item.get("ritiro_id"):
            import report_ritiri as _rr
            await _rr.aggiorna_stato_ritiro(item["ritiro_id"], "venduto", data.get("numero_fattura") or "", user["name"])
            data["ritiro_id"] = item["ritiro_id"]
    await _arricchisci(data)
    await db.vendite.insert_one(dict(data))
    data.pop("_id", None)
    if data["stato"] == "arrivato":
        await _wa_vendita(data, MSG_ARRIVATO, "arrivato", _saldo_txt(data))
    elif data["stato"] == "consegnato":
        data["consegnato_at"] = now.isoformat()
        await db.vendite.update_one({"id": data["id"]}, {"$set": {"consegnato_at": now.isoformat()}})
        await _accoda_recensione(data)
    return data


def _saldo_txt(v: dict) -> str:
    saldo = round(float(v.get("prezzo") or 0) * int(v.get("quantita") or 1) - float(v.get("acconto") or 0), 2)
    return f"\nSaldo alla consegna: {saldo:.2f} €." if not v.get("pagato") and saldo > 0 else ""


async def arrivato_da_magazzino(item_id: str) -> list:
    """Chiamato dal carico arrivo in Magazzino: le vendite ordinate su quell'articolo passano ad Arrivato e il cliente riceve il WA."""
    db = _deps["db"]
    now = datetime.now(timezone.utc).isoformat()
    out = []
    async for v in db.vendite.find({"magazzino_item_id": item_id, "stato": "ordinato"}, {"_id": 0}):
        await db.vendite.update_one({"id": v["id"]}, {"$set": {"stato": "arrivato", "arrivato_at": now, "updated_at": now},
                                                      "$push": {"stato_log": {"stato": "arrivato", "at": now, "by": "magazzino"}}})
        v.update(stato="arrivato")
        await _wa_vendita(v, MSG_ARRIVATO, "arrivato", _saldo_txt(v))
        out.append(f"{v.get('articolo', '')} ({v.get('client_name') or v.get('cliente_nome') or 'cliente'})")
    return out


ORDINE_FERMO_GIORNI = 5


async def avvisi_ordini_fermi() -> list:
    """Ogni mattina: WA al negozio per i telefoni ordinati per i clienti non arrivati dopo 5 giorni (ripetuto ogni 5 giorni)."""
    db = _deps["db"]
    now = datetime.now(timezone.utc)
    limite = (now - timedelta(days=ORDINE_FERMO_GIORNI)).isoformat()
    per_store: dict = {}
    async for v in db.vendite.find({"stato": "ordinato", "ordinato_at": {"$lte": limite}}, {"_id": 0}):
        ultimo = v.get("avviso_ordine_fermo_at")
        if ultimo and ultimo > limite:
            continue
        per_store.setdefault(v["store_id"], []).append(v)
    esiti = []
    for store_id, lst in per_store.items():
        s = await db.stores.find_one({"id": store_id}, {"_id": 0, "nome": 1, "telefono_avvisi": 1})
        numero = re.sub(r"\D", "", (s or {}).get("telefono_avvisi") or "")
        if not numero:
            esiti.append({"negozio": (s or {}).get("nome"), "ok": False, "motivo": "numero avvisi mancante"})
            continue
        righe = []
        for v in lst:
            giorni = (now - datetime.fromisoformat(v["ordinato_at"])).days
            righe.append(f"• {v.get('articolo', '')} per {v.get('client_name') or v.get('cliente_nome') or 'cliente'}"
                         + (f" ({v.get('fornitore')})" if v.get("fornitore") else "") + f" – ordinato da {giorni} giorni")
        testo = (f"⏰ *{s['nome']}* – telefoni ordinati non ancora arrivati:\n" + "\n".join(righe)
                 + "\n\nSollecita il fornitore o avvisa il cliente. Quando arriva, segnalo 'Arrivato' in Magazzino o Vendite.")
        try:
            await _deps["wa_send"](numero, testo, session=store_id, tipo="vendita_ordine_fermo")
            await db.vendite.update_many({"id": {"$in": [v["id"] for v in lst]}}, {"$set": {"avviso_ordine_fermo_at": now.isoformat()}})
            esiti.append({"negozio": s["nome"], "ok": True, "ordini": len(lst)})
        except Exception as e:
            esiti.append({"negozio": s["nome"], "ok": False, "motivo": str(e)[:200]})
    if esiti:
        await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "ordini_fermi", "at": now.isoformat(), "esiti": esiti})
    return esiti


@router.post("/vendite/{vendita_id}/whatsapp/arrivato")
async def wa_arrivato_manuale(vendita_id: str, user: dict = _user()):
    """Reinvia (o invia) al cliente l'avviso 'il tuo telefono è arrivato in negozio', in qualsiasi stato."""
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    v = await _deps["db"].vendite.find_one(scope, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    await _wa_vendita(v, MSG_ARRIVATO, "arrivato", _saldo_txt(v))
    v = await _deps["db"].vendite.find_one({"id": vendita_id}, {"_id": 0})
    if v.get("wa_arrivato_error"):
        raise HTTPException(status_code=400, detail=v["wa_arrivato_error"])
    return v


@router.post("/vendite/{vendita_id}/stato")
async def cambia_stato_vendita(vendita_id: str, input: StatoVenditaInput, user: dict = _user()):
    """Ordinato → Arrivato (magazzino torna a 0 + WA cliente) → Consegnato/Ritirato (recensione)."""
    db = _deps["db"]
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    v = await db.vendite.find_one(scope, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    if input.stato not in STATI_VENDITA:
        raise HTTPException(status_code=400, detail="Stato non valido")
    attuale = v.get("stato") or "consegnato"
    if input.stato == attuale and input.pagato is None and input.numero_fattura is None:
        return v
    now = datetime.now(timezone.utc).isoformat()
    upd = {"stato": input.stato, "updated_at": now}
    indietro = STATI_VENDITA.index(input.stato) < STATI_VENDITA.index(attuale)
    if indietro:
        if attuale == "consegnato":
            upd["consegnato_at"] = None
            upd["pagato"] = False if input.pagato is None else input.pagato
        if input.stato == "ordinato":
            upd["arrivato_at"] = None
            upd["ordinato_at"] = v.get("ordinato_at") or now
            if v.get("magazzino_item_id"):
                await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$inc": {"quantita": -(v.get("quantita") or 1)},
                                                                                "$set": {"in_ordine": True, "ordine_vendita_id": vendita_id, "updated_at": now}})
        await db.vendite.update_one({"id": vendita_id}, {"$set": upd, "$push": {"stato_log": {"stato": input.stato, "at": now, "by": user.get("name", ""), "indietro": True}}})
        return await db.vendite.find_one({"id": vendita_id}, {"_id": 0})
    if input.pagato is not None:
        upd["pagato"] = input.pagato
    if input.numero_fattura is not None:
        upd["numero_fattura"] = input.numero_fattura
    if input.stato == "arrivato" and attuale == "ordinato":
        upd["arrivato_at"] = now
        if v.get("magazzino_item_id"):
            await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$inc": {"quantita": v.get("quantita") or 1},
                                                                            "$set": {"in_ordine": False, "arrivato_at": now, "updated_at": now}, "$unset": {"ordine_vendita_id": ""}})
    if input.stato == "consegnato" and attuale != "consegnato":
        upd["consegnato_at"] = now
        upd["consegnato_da"] = user.get("name", "")
        if input.pagato is None:
            upd["pagato"] = True
        if attuale == "ordinato" and v.get("magazzino_item_id"):
            await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$inc": {"quantita": v.get("quantita") or 1}, "$set": {"in_ordine": False, "updated_at": now}, "$unset": {"ordine_vendita_id": ""}})
        if v.get("magazzino_item_id"):
            item = await db.magazzino.find_one({"id": v["magazzino_item_id"]}, {"_id": 0, "categoria": 1, "quantita": 1, "prezzo_acquisto": 1, "ritiro_id": 1})
            if item and item.get("categoria") == "rigenerati" and (item.get("quantita") or 0) <= 0:
                await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$set": {"stato": "venduto", "venduto_at": now, "venduto_prezzo": v.get("prezzo"), "venduto_da": user.get("name", ""),
                                                                                       "margine": float(v.get("prezzo") or 0) - float(item.get("prezzo_acquisto") or 0)}})
            if item and item.get("ritiro_id"):
                import report_ritiri as _rr
                await _rr.aggiorna_stato_ritiro(item["ritiro_id"], "venduto", upd.get("numero_fattura") or v.get("numero_fattura") or "", user["name"])
    await db.vendite.update_one({"id": vendita_id}, {"$set": upd, "$push": {"stato_log": {"stato": input.stato, "at": now, "by": user.get("name", "")}}})
    v = await db.vendite.find_one({"id": vendita_id}, {"_id": 0})
    if input.stato == "arrivato" and attuale == "ordinato":
        await _wa_vendita(v, MSG_ARRIVATO, "arrivato", _saldo_txt(v))
    if input.stato == "consegnato" and attuale != "consegnato":
        await _accoda_recensione(v)
    return await db.vendite.find_one({"id": vendita_id}, {"_id": 0})


class AssegnaClienteInput(BaseModel):
    client_id: str


@router.post("/vendite/{vendita_id}/cliente")
async def assegna_cliente_vendita(vendita_id: str, input: AssegnaClienteInput, user: dict = _user()):
    """Collega una vendita (es. importata senza scheda) a un cliente in anagrafica."""
    db = _deps["db"]
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    v = await db.vendite.find_one(scope, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    c = await db.clients.find_one({"id": input.client_id}, {"_id": 0, "nome": 1, "cognome": 1, "telefono": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    now = datetime.now(timezone.utc).isoformat()
    await db.vendite.update_one({"id": vendita_id}, {"$set": {"client_id": input.client_id, "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(),
                                                              "client_telefono": c.get("telefono", ""), "updated_at": now}})
    return await db.vendite.find_one({"id": vendita_id}, {"_id": 0})


@router.get("/vendite/{vendita_id}")
async def get_vendita(vendita_id: str, user: dict = _user()):
    db = _deps["db"]
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    v = await db.vendite.find_one(scope, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    return v


@router.patch("/vendite/{vendita_id}")
async def update_vendita(vendita_id: str, input: VenditaInput, user: dict = _user()):
    db = _deps["db"]
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    old = await db.vendite.find_one(scope, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    data = input.model_dump()
    _valida(data)
    data.pop("magazzino_item_id", None)
    for k in ("stato", "stato_log"):
        data.pop(k, None)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["client_name"] = None
    await _arricchisci(data)
    await db.vendite.update_one({"id": vendita_id}, {"$set": data})
    if data.get("fornitore") and old.get("magazzino_item_id"):
        await db.magazzino.update_one({"id": old["magazzino_item_id"]}, {"$set": {"fornitore": data["fornitore"][:60]}})
    return await db.vendite.find_one({"id": vendita_id}, {"_id": 0})


@router.delete("/vendite/{vendita_id}")
async def delete_vendita(vendita_id: str, user: dict = _user()):
    db = _deps["db"]
    scope = vendite_scope(user)
    scope["id"] = vendita_id
    v = await db.vendite.find_one(scope, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vendita non trovata")
    if v.get("magazzino_item_id"):
        import trasferimenti as _tr
        await _tr.annulla_vendita(vendita_id)
        if v.get("stato") == "ordinato":
            await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$inc": {"quantita": v.get("quantita") or 1}, "$set": {"in_ordine": False}, "$unset": {"ordine_vendita_id": ""}})
        else:
            await db.magazzino.update_one({"id": v["magazzino_item_id"]}, {"$inc": {"quantita": v.get("quantita") or 1},
                                                                            "$set": {"stato": "disponibile"}})
    await db.vendite.delete_one({"id": vendita_id})
    return {"status": "deleted"}


# ---------- Import registro ritiri/vendite 2026 (fogli Google) ----------
class VenditeImportInput(BaseModel):
    sheet_url: str
    gids: dict = {}  # {gid: nome_negozio}; se vuoto usa il gid nell'url e il prefisso del N° ritiro
    force: bool = False


def _euro(v: str) -> Optional[float]:
    s = (v or "").replace("€", "").replace(".", "").replace(",", ".").strip()
    if not s or s.upper() == "X":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _data(v: str) -> Optional[str]:
    s = (v or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


@router.post("/vendite/import-sheet")
async def import_vendite_sheet(input: VenditeImportInput, user: dict = _user()):
    db = _deps["db"]
    if user["role"] not in ("admin", "operatore") and not user.get("can_view_all"):
        raise HTTPException(status_code=403, detail="Solo admin/ufficio")
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9\-_]+)", input.sheet_url)
    if not m:
        raise HTTPException(status_code=400, detail="Link Google Sheet non valido")
    sheet_id = m.group(1)
    gids = dict(input.gids)
    if not gids:
        g = re.search(r"gid=(\d+)", input.sheet_url)
        gids = {g.group(1) if g else "0": ""}
    stores = {s["nome"].lower(): s["id"] for s in await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1}).to_list(100)}
    now = datetime.now(timezone.utc).isoformat()
    esito = {"vendite": 0, "in_vendita_magazzino": 0, "saltate": 0, "senza_negozio": 0}
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
        for gid, store_nome in gids.items():
            r = await http.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}")
            if r.status_code != 200:
                continue
            rows = list(csv.reader(io.StringIO(r.text)))
            for idx, row in enumerate(rows[1:], start=2):
                row = [c.strip() for c in row] + [""] * 10
                n_rit = row[0]
                if not n_rit or not row[2]:
                    continue
                # colonne: N° ritiro, data, modello, valore ritiro, cliente, [vuota su Gravedona], venduto, valore, fattura, note
                off = 1 if (row[5] == "" and row[6].upper() in ("SI", "PEZZI RICAMBIO", "PER USO INTERNO", "IN VENDITA", "")) and len(rows[0]) >= 10 and rows[0][5] == "" else 0
                venduto = row[5 + off].upper()
                valore_vendita = _euro(row[6 + off])
                fattura = row[7 + off]
                note = row[8 + off]
                prefix = re.match(r"([A-Za-z]+)", n_rit)
                nome_store = store_nome or SHEET_PREFIX_STORE.get((prefix.group(1) if prefix else "").upper(), "")
                sid = stores.get(nome_store.lower())
                if not sid:
                    esito["senza_negozio"] += 1
                    continue
                key = f"{sheet_id}:{gid}:{idx}"
                if await db.vendite.find_one({"import_key": key}) or await db.magazzino.find_one({"import_key": key}):
                    esito["saltate"] += 1
                    continue
                costo = _euro(row[3])
                modello = row[2]
                cliente = row[4].title()
                data_rit = _data(row[1]) or now
                if venduto == "SI":
                    await db.vendite.insert_one({
                        "id": str(uuid.uuid4()), "store_id": sid, "client_id": "", "cliente_nome": cliente,
                        "categoria": "telefono_usato", "regime_iva": "art36", "articolo": modello, "modello": modello,
                        "quantita": 1, "prezzo": valore_vendita or 0.0, "costo": costo, "pagamento": "",
                        "numero_fattura": fattura, "data_vendita": data_rit, "note": f"Import registro ritiri {n_rit}. {note}".strip(),
                        "import_key": key, "created_by": user["id"], "created_by_name": "Import foglio", "created_at": now, "updated_at": now})
                    esito["vendite"] += 1
                elif venduto == "IN VENDITA":
                    await db.magazzino.insert_one({
                        "id": str(uuid.uuid4()), "nome": f"{modello} (usato {n_rit})", "categoria": "rigenerati", "condizione": "usato",
                        "regime_iva": "art36", "store_id": sid, "quantita": 1, "prezzo_acquisto": costo, "prezzo_vendita": valore_vendita,
                        "stato": "disponibile", "note": f"Ritirato da {cliente} il {row[1]}. {note}".strip(), "import_key": key,
                        "barcode": "", "created_at": now, "updated_at": now})
                    esito["in_vendita_magazzino"] += 1
                else:
                    esito["saltate"] += 1
    return esito
