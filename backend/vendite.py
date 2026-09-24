import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

VENDITE_CATEGORIE = ["telefono_nuovo", "telefono_rigenerato", "telefono_usato", "pc", "router", "accessori", "stampanti", "altro"]
REGIMI_IVA = ["iva22", "art36", "art17"]
CATEGORIE_USATO = {"telefono_rigenerato", "telefono_usato"}
SHEET_PREFIX_STORE = {"M": "Morbegno", "SO": "Sondrio", "G": "Gravedona"}

router = APIRouter()
_deps: dict = {}


def setup(db, get_current_user, magazzino_scope, log_audit=None):
    _deps.update(db=db, get_current_user=get_current_user, magazzino_scope=magazzino_scope, log_audit=log_audit)


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
    if data["prezzo"] < 0 or data["quantita"] < 1:
        raise HTTPException(status_code=400, detail="Prezzo o quantità non validi")
    if not data.get("client_id") and not (data.get("cliente_nome") or "").strip():
        raise HTTPException(status_code=400, detail="Indica il cliente (esistente o nome libero)")


async def _arricchisci(v: dict) -> dict:
    db = _deps["db"]
    if v.get("client_id") and not v.get("client_name"):
        c = await db.clients.find_one({"id": v["client_id"]}, {"_id": 0, "nome": 1, "cognome": 1, "telefono": 1})
        if c:
            v["client_name"] = f"{c.get('cognome', '')} {c.get('nome', '')}".strip()
            v["client_telefono"] = c.get("telefono", "")
    return v


@router.get("/vendite/meta")
async def vendite_meta(user: dict = _user()):
    return {"categorie": VENDITE_CATEGORIE, "regimi_iva": REGIMI_IVA}


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
    if user["role"] == "negozio" and data["store_id"] not in user.get("store_ids", []):
        raise HTTPException(status_code=403, detail="Puoi registrare vendite solo per il tuo negozio")
    now = datetime.now(timezone.utc)
    data.update({"id": str(uuid.uuid4()), "created_by": user["id"], "created_by_name": user["name"],
                 "created_at": now.isoformat(), "updated_at": now.isoformat(),
                 "data_vendita": data.get("data_vendita") or now.isoformat()})
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
        if item.get("ritiro_id"):
            import report_ritiri as _rr
            await _rr.aggiorna_stato_ritiro(item["ritiro_id"], "venduto", data.get("numero_fattura") or "", user["name"])
            data["ritiro_id"] = item["ritiro_id"]
    await _arricchisci(data)
    await db.vendite.insert_one(dict(data))
    data.pop("_id", None)
    return data


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
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["client_name"] = None
    await _arricchisci(data)
    await db.vendite.update_one({"id": vendita_id}, {"$set": data})
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
