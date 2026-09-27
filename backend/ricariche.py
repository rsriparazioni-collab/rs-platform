import csv
import io
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}

COLONNE = ["#", "Partner", "Utente", "Operatore ricarica", "Importo ricarica", "Data/Ora generazione riga"]


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


class MappingInput(BaseModel):
    utente: str
    store_id: str


def _parse(content: bytes) -> list[dict]:
    testo = content.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(testo), delimiter=";"))
    if not rows or not all(c in rows[0] for c in COLONNE):
        raise HTTPException(status_code=400, detail="Formato non riconosciuto: attese le colonne " + ", ".join(COLONNE))
    idx = {c: rows[0].index(c) for c in rows[0]}
    esito_col = next((c for c in rows[0] if c.lower().startswith("esito")), None)
    note_col = next((c for c in rows[0] if c.lower().startswith("note")), None)
    num_col = next((c for c in rows[0] if c.lower().startswith("numero")), None)
    out = []
    for r in rows[1:]:
        if len(r) < len(COLONNE) or not r[idx["#"]].strip():
            continue
        try:
            at = datetime.strptime(r[idx["Data/Ora generazione riga"]].strip(), "%d/%m/%Y %H:%M")
        except ValueError:
            continue
        operatore = r[idx["Operatore ricarica"]].split(" - ")[0].strip()
        out.append({"id": r[idx["#"]].strip(), "partner": r[idx["Partner"]].strip(), "utente": r[idx["Utente"]].strip(), "operatore": operatore,
                    "descrizione": r[idx["Operatore ricarica"]].strip(), "importo": float(r[idx["Importo ricarica"]].replace(",", ".") or 0),
                    "at": at.isoformat(), "mese": at.strftime("%Y-%m"), "numero": r[idx[num_col]].strip() if num_col else "",
                    "esito": (r[idx[esito_col]].strip().lower() if esito_col else "eseguita"), "note": r[idx[note_col]].strip().strip('"') if note_col else ""})
    return out


async def _mapping() -> dict:
    db = _d["db"]
    mapping = {m["utente"]: m["store_id"] async for m in db.ricariche_mapping.find({}, {"_id": 0})}
    utenti = await db.ricariche.distinct("utente")
    if any(u not in mapping for u in utenti):
        stores = await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1}).to_list(100)
        venditori = await db.venditori.find({"store_id": {"$ne": ""}}, {"_id": 0, "nome": 1, "store_id": 1}).to_list(100)
        users = await db.users.find({"store_ids.0": {"$exists": True}}, {"_id": 0, "name": 1, "store_ids": 1}).to_list(100)
        for u in utenti:
            if u in mapping:
                continue
            primo = u.split(" ")[0].strip().lower()
            sid = next((v["store_id"] for v in venditori if v["nome"].strip().lower() == primo), None) \
                or next((x["store_ids"][0] for x in users if x["name"].strip().lower() == primo), None) \
                or next((s["id"] for s in stores if s["nome"].strip().lower() == primo), "")
            mapping[u] = sid
            await db.ricariche_mapping.update_one({"utente": u}, {"$set": {"store_id": sid}}, upsert=True)
    return mapping


@router.post("/ricariche/import")
async def import_ricariche(file: UploadFile = File(...), admin: dict = Depends(_admin)):
    db = _d["db"]
    righe = _parse(await file.read())
    if not righe:
        raise HTTPException(status_code=400, detail="Nessuna riga valida nel file")
    esistenti = {r["id"] async for r in db.ricariche.find({"id": {"$in": [r["id"] for r in righe]}}, {"_id": 0, "id": 1})}
    nuove = [r for r in righe if r["id"] not in esistenti]
    for r in righe:
        if r["id"] in esistenti:
            await db.ricariche.update_one({"id": r["id"]}, {"$set": {"esito": r["esito"], "note": r["note"]}})
    if nuove:
        await db.ricariche.insert_many([dict(r) for r in nuove])
    mesi = sorted({r["mese"] for r in righe})
    await db.ricariche_import_log.insert_one({"id": str(uuid.uuid4()), "file": file.filename, "righe": len(righe), "nuove": len(nuove),
                                              "aggiornate": len(righe) - len(nuove), "mesi": mesi, "at": datetime.now(timezone.utc).isoformat(), "user_name": admin["name"]})
    await _mapping()
    return {"righe": len(righe), "nuove": len(nuove), "aggiornate": len(righe) - len(nuove), "mesi": mesi}


@router.get("/ricariche/riepilogo")
async def riepilogo(anno: int, mese: int, admin: dict = Depends(_admin)):
    db = _d["db"]
    m = f"{anno:04d}-{mese:02d}"
    righe = await db.ricariche.find({"mese": m}, {"_id": 0}).sort("at", -1).to_list(20000)
    mapping = await _mapping()
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    per_utente, per_store, per_operatore = defaultdict(lambda: {"n": 0, "totale": 0.0, "fallite": 0}), defaultdict(lambda: {"n": 0, "totale": 0.0, "fallite": 0}), defaultdict(lambda: {"n": 0, "totale": 0.0})
    tot = {"n": 0, "totale": 0.0, "fallite": 0, "totale_fallite": 0.0}
    for r in righe:
        sid = mapping.get(r["utente"], "")
        r["store_id"] = sid
        r["store_name"] = stores.get(sid, "Non assegnato")
        for b in (per_utente[r["utente"]], per_store[r["store_name"]]):
            if r["esito"] == "eseguita":
                b["n"] += 1; b["totale"] = round(b["totale"] + r["importo"], 2)
            else:
                b["fallite"] += 1
        if r["esito"] == "eseguita":
            po = per_operatore[r["operatore"]]
            po["n"] += 1; po["totale"] = round(po["totale"] + r["importo"], 2)
            tot["n"] += 1; tot["totale"] = round(tot["totale"] + r["importo"], 2)
        else:
            tot["fallite"] += 1; tot["totale_fallite"] = round(tot["totale_fallite"] + r["importo"], 2)
    fmt = lambda d: sorted([{"nome": k, **v} for k, v in d.items()], key=lambda x: -x["totale"])
    mesi = sorted(await db.ricariche.distinct("mese"), reverse=True)
    ultimo = await db.ricariche_import_log.find_one({}, {"_id": 0}, sort=[("at", -1)])
    return {"mese": m, "totale": tot, "per_utente": fmt(per_utente), "per_negozio": fmt(per_store), "per_operatore": fmt(per_operatore),
            "righe": righe[:500], "mesi_disponibili": mesi, "ultimo_import": ultimo,
            "mapping": [{"utente": u, "store_id": s, "store_name": stores.get(s, "")} for u, s in sorted(mapping.items())]}


@router.put("/ricariche/mapping")
async def set_mapping(input: MappingInput, admin: dict = Depends(_admin)):
    await _d["db"].ricariche_mapping.update_one({"utente": input.utente}, {"$set": {"store_id": input.store_id}}, upsert=True)
    return {"ok": True}


async def ricariche_per_store(mese: str) -> dict:
    """Totale € ricariche eseguite (da CSV importato) per store_id nel mese; {} se nessun import per quel mese."""
    db = _d["db"]
    righe = await db.ricariche.find({"mese": mese, "esito": "eseguita"}, {"_id": 0, "utente": 1, "importo": 1}).to_list(20000)
    if not righe:
        return {}
    mapping = await _mapping()
    out = defaultdict(float)
    for r in righe:
        out[mapping.get(r["utente"], "")] = round(out[mapping.get(r["utente"], "")] + r["importo"], 2)
    return dict(out)
