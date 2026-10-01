import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException

_d: dict = {}
STATO_ORDINE = "in_ordine"
STATO_PRONTO = "pronto_ritiro"


def setup(**deps):
    _d.update(deps)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def apri_ordine(data: dict, user: dict) -> None:
    """Vendita su ordinazione: crea (o usa) l'articolo di magazzino, lo mette in ordine (giacenza negativa) e lega il servizio."""
    db = _d["db"]
    qta = max(int(data.get("quantita") or 1), 1)
    art = data.get("ordine_articolo") or {}
    item = None
    if data.get("magazzino_item_id"):
        item = await db.magazzino.find_one({"id": data["magazzino_item_id"]}, {"_id": 0})
    if not item:
        nome = (art.get("nome") or data.get("prodotto") or "").strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Indica il nome del prodotto da ordinare")
        item = {"id": str(uuid.uuid4()), "nome": nome[:120], "barcode": (art.get("codice") or "")[:60], "condizione": art.get("condizione") or "nuovo", "regime_iva": "iva22",
                "categoria": art.get("categoria") or "altro", "store_id": data.get("venditore_id") or "", "quantita": 0,
                "prezzo_acquisto": art.get("costo"), "prezzo_vendita": art.get("prezzo_vendita") or data.get("importo"),
                "marca": (art.get("marca") or "")[:60], "modello": (art.get("modello") or "")[:60], "tipologia": "", "fornitore": (data.get("ordine_fornitore") or "")[:60],
                "note": "Ordinato per vendita cliente", "created_at": _now(), "updated_at": _now()}
        await db.magazzino.insert_one(dict(item))
    cliente = await db.clients.find_one({"id": data["client_id"]}, {"_id": 0, "nome": 1, "cognome": 1})
    etichetta = f"Vendita {cliente.get('cognome', '')} {cliente.get('nome', '')}".strip() if cliente else "Vendita"
    await db.magazzino.update_one({"id": item["id"]}, {"$inc": {"quantita": -qta}, "$set": {
        "in_ordine": True, "ordine_at": _now(), "ordine_servizio_id": data["id"], "ordine_servizio_numero": etichetta,
        "fornitore": (data.get("ordine_fornitore") or item.get("fornitore") or "")[:60], "updated_at": _now()}})
    data.update({"magazzino_item_id": item["id"], "magazzino_nome": item["nome"], "magazzino_store_id": item.get("store_id", ""), "quantita": qta,
                 "prodotto": data.get("prodotto") or item["nome"], "stato": STATO_ORDINE, "pagato": False, "ordine_at": _now(),
                 "acconto": float(data.get("acconto") or 0)})


async def arrivato(item_id: str) -> list:
    """Chiamato all'arrivo dell'articolo: le vendite in ordine passano a pronto_ritiro e il cliente riceve il WhatsApp."""
    db = _d["db"]
    out = []
    async for s in db.servizi.find({"magazzino_item_id": item_id, "tipo": {"$in": ["vendita", "accessori"]}, "stato": STATO_ORDINE}, {"_id": 0}):
        await db.servizi.update_one({"id": s["id"]}, {"$set": {"stato": STATO_PRONTO, "arrivato_at": _now(), "updated_at": _now()}})
        c = await db.clients.find_one({"id": s["client_id"]}, {"_id": 0, "nome": 1, "telefono": 1})
        store = await db.stores.find_one({"id": s.get("venditore_id")}, {"_id": 0, "nome": 1})
        saldo = round(float(s.get("importo") or 0) - float(s.get("acconto") or 0), 2)
        if c and c.get("telefono"):
            msg = (f"Ciao {c.get('nome', '')}! 😊\nIl tuo {s.get('prodotto') or 'prodotto'} ordinato è arrivato ed è pronto per il ritiro presso {(store or {}).get('nome', 'il nostro negozio')}."
                   + (f"\nSaldo alla consegna: {saldo:.2f} €." if saldo > 0 else "") + "\nTi aspettiamo!")
            try:
                await _d["wa_send"](c["telefono"], msg, session=s.get("venditore_id") or "default", tipo="ordine_arrivato", client_id=s["client_id"], servizio_id=s["id"])
                await db.servizi.update_one({"id": s["id"]}, {"$set": {"arrivo_msg_sent_at": _now(), "arrivo_msg_error": None}})
            except Exception as e:
                await db.servizi.update_one({"id": s["id"]}, {"$set": {"arrivo_msg_error": str(getattr(e, "detail", e))}})
        else:
            await db.servizi.update_one({"id": s["id"]}, {"$set": {"arrivo_msg_error": "Cliente senza numero di telefono"}})
        out.append(s.get("prodotto") or s["id"])
    return out


async def consegna(servizio_id: str, user: dict) -> dict:
    """Ritiro e saldo: la vendita si chiude (consegnato, pagato) e l'articolo resta scaricato."""
    db = _d["db"]
    s = await _d["get_scoped_servizio"](servizio_id, user)
    if s.get("stato") not in (STATO_PRONTO, STATO_ORDINE):
        raise HTTPException(status_code=400, detail="La vendita non è in attesa di ritiro")
    now = _now()
    await db.servizi.update_one({"id": servizio_id}, {"$set": {"stato": "consegnato", "pagato": True, "last_payment_date": date.today().isoformat(),
                                                               "data_uscita": date.today().isoformat(), "consegnato_at": now, "consegnato_da": user.get("name", ""), "updated_at": now}})
    item = await db.magazzino.find_one({"id": s.get("magazzino_item_id")}, {"_id": 0, "categoria": 1, "quantita": 1})
    if item and item.get("categoria") == "rigenerati" and (item.get("quantita") or 0) <= 0:
        await db.magazzino.update_one({"id": s["magazzino_item_id"]}, {"$set": {"stato": "venduto", "venduto_at": now, "venduto_prezzo": s.get("importo"), "venduto_da": user.get("name", "")}})
    return {"status": "ok", "saldo": round(float(s.get("importo") or 0) - float(s.get("acconto") or 0), 2)}
