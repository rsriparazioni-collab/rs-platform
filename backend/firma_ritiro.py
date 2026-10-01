import asyncio
import base64
import logging
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("firma_ritiro")
router = APIRouter()
_d: dict = {}
OTP_MINUTI = 30


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


def link_firma(token: str) -> str:
    return f"{os.environ.get('FRONTEND_URL', '').rstrip('/')}/firma/{token}"


def normalizza_telefono(t: str) -> str:
    d = re.sub(r"\D", "", t or "")
    if len(d) < 9:
        raise HTTPException(status_code=400, detail="Numero di telefono del cliente obbligatorio (almeno 9 cifre)")
    return d


def prepara_firma(data: dict) -> None:
    """Campi firma al momento della creazione bolla."""
    data["firma_token"] = uuid.uuid4().hex
    data["firma_otp"] = f"{random.randint(0, 999999):06d}"
    data["firma_otp_scadenza"] = (_now() + timedelta(minutes=OTP_MINUTI)).isoformat()
    data["firma_stato"] = "in_attesa"


async def invia_richiesta_firma(ritiro: dict, nuovo_otp: bool = False) -> dict:
    db = _d["db"]
    upd = {}
    if nuovo_otp or not ritiro.get("firma_otp") or ritiro.get("firma_otp_scadenza", "") < _now().isoformat():
        upd = {"firma_otp": f"{random.randint(0, 999999):06d}", "firma_otp_scadenza": (_now() + timedelta(minutes=OTP_MINUTI)).isoformat()}
        ritiro.update(upd)
    store = await db.stores.find_one({"id": ritiro.get("store_id")}, {"_id": 0, "nome": 1})
    msg = (f"Ciao {ritiro.get('nome', '')}, grazie per il ritiro del tuo {ritiro.get('articolo', 'dispositivo')} presso {(store or {}).get('nome', 'RS Riparazioni')}.\n"
           f"Bolla N. {ritiro.get('numero')}" + (f" - valore EUR {ritiro['prezzo_ritiro']:.2f}" if ritiro.get("prezzo_ritiro") is not None else "") + ".\n\n"
           f"Per firmare la bolla puoi:\n1) aprire questo link e firmare col dito: {link_firma(ritiro['firma_token'])}\n"
           f"2) oppure comunicare al negozio il codice OTP: *{ritiro['firma_otp']}* (valido {OTP_MINUTI} minuti).")
    esito = {"ok": True}
    try:
        await _d["wa_send"](ritiro["telefono"], msg, session=ritiro.get("store_id") or "default", tipo="firma_ritiro", client_id=ritiro.get("client_id", ""))
        upd["firma_inviata_at"] = _now().isoformat()
    except Exception as e:
        esito = {"ok": False, "error": str(getattr(e, "detail", e))}
        upd["firma_invio_errore"] = esito["error"]
    if upd:
        await db.ritiri.update_one({"id": ritiro["id"]}, {"$set": upd})
    return esito


async def _rigenera_bolla(ritiro_id: str) -> None:
    """Rigenera la bolla (con firme) e, se ci sono documenti, la riunisce con i documenti già caricati."""
    db = _d["db"]
    r = await db.ritiri.find_one({"id": ritiro_id}, {"_id": 0})
    pdf = _d["build_bolla"](r)
    base = _d["put_object"](f"{_d['app_name']}/ritiri/{r['numero']}_firmata_{uuid.uuid4().hex[:6]}.pdf", pdf, "application/pdf")
    upd = {"bolla_base_path": base["path"], "storage_path": base["path"]}
    if r.get("documenti") and r.get("storage_path"):
        try:
            merged_old, _ = _d["get_object"](r["storage_path"])
            import fitz
            old = fitz.open("pdf", merged_old)
            nuovo = fitz.open("pdf", pdf)
            if old.page_count > 1:
                nuovo.insert_pdf(old, from_page=1, to_page=old.page_count - 1)
            res = _d["put_object"](f"{_d['app_name']}/ritiri/{r['numero']}_firmata_docs_{uuid.uuid4().hex[:6]}.pdf", nuovo.tobytes(), "application/pdf")
            upd["storage_path"] = res["path"]
        except Exception as e:
            logger.warning(f"Riunione documenti bolla {r['numero']} fallita: {e}")
    await db.ritiri.update_one({"id": ritiro_id}, {"$set": upd})
    if _d.get("drive_upload"):
        asyncio.create_task(_d["drive_upload"](ritiro_id))


class OtpInput(BaseModel):
    codice: str


async def firma_otp(ritiro_id: str, codice: str, user: dict) -> dict:
    db = _d["db"]
    r = await db.ritiri.find_one({"id": ritiro_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Ritiro non trovato")
    if r.get("firma_stato") == "firmata":
        raise HTTPException(status_code=400, detail="Bolla già firmata")
    if re.sub(r"\D", "", codice) != r.get("firma_otp") or r.get("firma_otp_scadenza", "") < _now().isoformat():
        raise HTTPException(status_code=400, detail="Codice OTP errato o scaduto: reinvia il messaggio al cliente")
    now = _now().isoformat()
    await db.ritiri.update_one({"id": ritiro_id}, {"$set": {"firma_stato": "firmata", "firma_metodo": "otp", "firma_at": now, "firma_verificata_da": user.get("name", ""), "firma_png": None}})
    await _rigenera_bolla(ritiro_id)
    return {"status": "ok", "firma_metodo": "otp", "firma_at": now}


async def reinvia(ritiro_id: str) -> dict:
    r = await _d["db"].ritiri.find_one({"id": ritiro_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Ritiro non trovato")
    if not r.get("telefono"):
        raise HTTPException(status_code=400, detail="Il ritiro non ha un numero di telefono")
    if not r.get("firma_token"):
        prepara_firma(r)
        await _d["db"].ritiri.update_one({"id": ritiro_id}, {"$set": {k: r[k] for k in ("firma_token", "firma_otp", "firma_otp_scadenza", "firma_stato")}})
    return await invia_richiesta_firma(r, nuovo_otp=True)


# ---------- pubblico (link dal telefono del cliente) ----------
@router.get("/public/firma/{token}")
async def public_info(token: str):
    r = await _d["db"].ritiri.find_one({"firma_token": token}, {"_id": 0, "numero": 1, "nome": 1, "cognome": 1, "articolo": 1, "marca": 1, "modello": 1, "prezzo_ritiro": 1, "data_ritiro": 1, "firma_stato": 1, "firma_at": 1, "store_id": 1})
    if not r:
        raise HTTPException(status_code=404, detail="Link non valido")
    store = await _d["db"].stores.find_one({"id": r.pop("store_id", "")}, {"_id": 0, "nome": 1})
    r["negozio"] = (store or {}).get("nome", "")
    return r


class FirmaInput(BaseModel):
    firma_png: str


@router.post("/public/firma/{token}")
async def public_firma(token: str, body: FirmaInput):
    db = _d["db"]
    r = await db.ritiri.find_one({"firma_token": token}, {"_id": 0, "id": 1, "firma_stato": 1, "numero": 1})
    if not r:
        raise HTTPException(status_code=404, detail="Link non valido")
    if r.get("firma_stato") == "firmata":
        raise HTTPException(status_code=400, detail="Bolla già firmata")
    m = re.match(r"^data:image/png;base64,(.+)$", body.firma_png or "")
    if not m:
        raise HTTPException(status_code=400, detail="Firma non valida")
    raw = base64.b64decode(m.group(1))
    if len(raw) < 500 or len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Firma vuota o troppo grande")
    res = _d["put_object"](f"{_d['app_name']}/ritiri/firme/{r['numero']}_{uuid.uuid4().hex[:6]}.png", raw, "image/png")
    now = _now().isoformat()
    await db.ritiri.update_one({"id": r["id"]}, {"$set": {"firma_stato": "firmata", "firma_metodo": "link", "firma_at": now, "firma_png": res["path"]}})
    await _rigenera_bolla(r["id"])
    return {"status": "ok", "firma_at": now}
