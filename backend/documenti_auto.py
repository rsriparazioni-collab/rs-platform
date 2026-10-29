"""Documenti: classificazione automatica degli allegati (bolletta / documento / altro) leggendo il contenuto
e promemoria 'manda l'ultima bolletta' un mese prima della scadenza contratto."""
import base64
import logging
import os
import re
import uuid
from datetime import datetime, timezone, date

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("documenti")
router = APIRouter(tags=["documenti"])
_d: dict = {}
TIPI = ("bolletta", "documento", "altro")


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _user(request: Request):
    return await _d["get_current_user_req"](request)


def _regole(testo: str) -> str | None:
    t = testo.lower()
    if re.search(r"\b(pod|pdr)\b|it\d{3}e|kwh|smc|consumo|fornitura|periodo di fatturazione|totale da pagare|bolletta|fattura n", t):
        return "bolletta"
    if re.search(r"carta d.identit|codice fiscale|tessera sanitaria|patente|passaporto|repubblica italiana|comune di|luogo di nascita|data di nascita|cittadinanza", t):
        return "documento"
    return None


def testo_documento(data: bytes, content_type: str) -> str:
    """Testo di un PDF (o di un'immagine via AI non necessario qui): usato per abbinare POD/PDR/cognome."""
    if content_type == "application/pdf" or data[:4] == b"%PDF":
        import pymupdf
        try:
            return "\n".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf"))[:8000]
        except Exception:
            return ""
    return ""


async def classifica_contenuto(data: bytes, content_type: str, nome: str) -> dict:
    """Prima regole sul testo (gratis), poi AI (gpt-5.4, anche su immagine) se il testo non basta."""
    testo, img = "", None
    if content_type == "application/pdf" or data[:4] == b"%PDF":
        import pymupdf
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
            testo = "\n".join(p.get_text() for p in doc)[:6000]
            if len(testo.strip()) < 60 and len(doc):
                img = base64.b64encode(doc[0].get_pixmap(dpi=90).tobytes("png")).decode()
        except Exception as e:
            return {"tipo": "altro", "fonte": "errore", "dettaglio": str(e)}
    elif content_type.startswith("image/"):
        img = base64.b64encode(data).decode()
    else:
        return {"tipo": "altro", "fonte": "formato"}
    if testo.strip():
        r = _regole(testo)
        if r:
            return {"tipo": r, "fonte": "regole"}
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return {"tipo": "altro", "fonte": "no-ai"}
    from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage
    prompt = ("Classifica questo file allegato alla pratica di un cliente di energia. Rispondi con UNA sola parola: "
              "'bolletta' (fattura/bolletta luce o gas di qualsiasi fornitore), 'documento' (carta d'identità, patente, passaporto, tessera sanitaria/codice fiscale), oppure 'altro'.")
    chat = LlmChat(api_key=key, session_id=f"doc-{uuid.uuid4().hex[:8]}", system_message="Rispondi solo con una parola.").with_model("openai", "gpt-5.4")
    try:
        msg = UserMessage(text=prompt + (f"\n\nNome file: {nome}\nTESTO:\n{testo}" if testo.strip() else f"\n\nNome file: {nome}"), file_contents=[ImageContent(image_base64=img)] if img else None)
        risp = str(await chat.send_message(msg)).strip().lower()
    except Exception as e:
        return {"tipo": "altro", "fonte": "errore-ai", "dettaglio": str(e)[:200]}
    tipo = next((t for t in ("bolletta", "documento") if t in risp), "altro")
    return {"tipo": tipo, "fonte": "ai"}


async def classifica_allegato(att: dict) -> dict:
    db = _d["db"]
    try:
        data, ct = _d["get_object"](att["storage_path"])
    except Exception as e:
        return {"id": att["id"], "tipo": "altro", "fonte": "errore", "dettaglio": str(e)}
    r = await classifica_contenuto(data, att.get("content_type") or ct or "", att.get("original_filename") or "")
    await db.attachments.update_one({"id": att["id"]}, {"$set": {"tipo": r["tipo"], "tipo_auto": r["fonte"], "tipo_auto_at": _now().isoformat()}})
    return {"id": att["id"], "nome": att.get("original_filename"), **r}


def _da_classificare(extra: dict) -> dict:
    return {**extra, "is_deleted": False, "client_id": {"$ne": None}, "$or": [{"tipo": {"$in": [None, "", "altro"]}}], "tipo_auto": {"$in": [None]}}


@router.post("/clients/{client_id}/attachments/classifica")
async def classifica_cliente(client_id: str, request: Request):
    user = await _user(request)
    await _d["get_scoped_client"](client_id, user)
    atts = await _d["db"].attachments.find(_da_classificare({"client_id": client_id}), {"_id": 0}).to_list(50)
    out = [await classifica_allegato(a) for a in atts]
    return {"classificati": len(out), "risultati": out}


@router.post("/attachments/classifica-batch")
async def classifica_batch(request: Request, limit: int = 40):
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return await classifica_notturna(limit)


async def classifica_notturna(limit: int = 60) -> dict:
    """Cron: classifica gli allegati vecchi non ancora tipizzati (i più recenti prima), un lotto per notte."""
    db = _d["db"]
    atts = await db.attachments.find(_da_classificare({}), {"_id": 0}).sort("created_at", -1).to_list(limit)
    esiti = {"bolletta": 0, "documento": 0, "altro": 0}
    for a in atts:
        r = await classifica_allegato(a)
        esiti[r["tipo"]] = esiti.get(r["tipo"], 0) + 1
    rimasti = await db.attachments.count_documents(_da_classificare({}))
    logger.info(f"classificazione allegati: {esiti}, rimasti {rimasti}")
    return {"classificati": len(atts), "esiti": esiti, "rimasti": rimasti}


# ---------- promemoria bollette un mese prima della scadenza ----------
async def promemoria_bollette_rinnovo() -> dict:
    """Cron 9:00: ai clienti CambiaOra con contratto in scadenza tra 28 e 31 giorni, WhatsApp dal negozio 'inviaci l'ultima bolletta' (una volta per scadenza)."""
    db = _d["db"]
    oggi = date.today()
    inviati, errori = 0, []
    cur = db.clients.find({"telefono": {"$nin": [None, ""]}, "data_contratto": {"$nin": [None, ""]}, "gestione": {"$ne": "enel"}, "anonimizzato_at": {"$in": [None]},
                           "lavorazione": {"$nin": ["annullato", "rinnovato", "perso", ""]}},
                          {"_id": 0, "id": 1, "nome": 1, "telefono": 1, "venditore_id": 1, "data_contratto": 1, "bollette_rinnovo_scadenza": 1, "gestione": 1, "pod": 1, "pdr": 1, "origine": 1, "fornitore_provenienza": 1, "nuovo_fornitore": 1})
    async for c in cur:
        if not _d["cliente_energia"](c):
            continue
        cc = _d["compute_dates"](dict(c))
        g = cc.get("giorni_alla_scadenza")
        if g is None or not (28 <= g <= 31) or c.get("bollette_rinnovo_scadenza") == cc["data_scadenza"]:
            continue
        store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0})
        sess = await _d["wa_sessione_negozio"](store)
        msg = _d["store_msg"](store, "msg_bollette", nome=c.get("nome", ""))
        try:
            await _d["wa_send"](c["telefono"], msg, session=sess, tipo="bollette_rinnovo", client_id=c["id"])
            await db.clients.update_one({"id": c["id"]}, {"$set": {"bollette_rinnovo_scadenza": cc["data_scadenza"], "bollette_msg_sent_at": _now().isoformat()}})
            inviati += 1
        except HTTPException as e:
            errori.append({"client_id": c["id"], "errore": str(e.detail)})
    return {"inviati": inviati, "errori": errori, "giorno": oggi.isoformat()}
