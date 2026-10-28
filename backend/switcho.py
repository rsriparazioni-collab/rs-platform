import os
import re
import uuid
import unicodedata
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typesafe_sdk import Choice, TypeSafeError

from jev import get_jev_client

router = APIRouter()
_d: dict = {}
logger = logging.getLogger("switcho")

CATEGORIE = {
    "annullata_ip": "Il back-office ha ANNULLATO la pratica perché l'IP della firma del mandato coincide con quello della scelta del deal; chiede di reinserirla da capo",
    "annullata_firma": "Il fornitore ha ANNULLATO la pratica per mancata firma del contratto, offerta scaduta o cliente che non ha confermato",
    "conferma_link": "Invita o sollecita il cliente a confermare/firmare un link, un plico o una mail ricevuti dal fornitore (es. entro 48 ore)",
    "documenti": "Chiede documenti o dati mancanti per la pratica: bolletta, documento d'identità, codice fiscale, punto di fornitura",
    "verifica": "Pone una domanda da verificare e a cui rispondere (es. conferma se l'IBAN è intestato al cliente)",
    "altro": "Altro: informazione generica, saluto o messaggio non riconducibile ai casi precedenti",
}
LABEL = {"annullata_ip": "Annullata (IP mandato)", "annullata_firma": "Annullata (mancata firma)", "conferma_link": "Cliente deve confermare link/plico",
         "documenti": "Servono documenti", "verifica": "Domanda da verificare", "altro": "Altro"}
STATO_PRATICA = {"annullata_ip": "annullato", "annullata_firma": "annullato", "conferma_link": "in_attesa_ok", "documenti": "attesa_documenti"}
FORNITORI = ["LENE", "ENI PLENITUDE", "ENIPLENITUDE", "ENI", "MAGIS", "SEGNOVERDE", "E.ON", "EON", "PULSEE", "OCTOPUS", "EDISON", "ILLUMIA", "IREN",
             "HERA", "A2A", "ACEA", "AGSM", "DOLOMITI", "SORGENIA", "ENEL", "WEKIWI", "ALPERIA", "ENGIE", "PLENITUDE"]
DEFAULT_CFG = {"gruppo_jid": "", "mittente": "393299899503", "session_risposta": "", "auto_avviso_cliente": True, "attivo": True}


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def require_addetto(user: dict = Depends(_current_user)):
    if not await _d["is_addetto"](user):
        raise HTTPException(status_code=403, detail="Sezione riservata agli addetti lavorazioni")
    return user


async def cfg() -> dict:
    doc = await _d["db"].settings.find_one({"key": "switcho_cfg"}, {"_id": 0})
    return {**DEFAULT_CFG, **((doc or {}).get("value") or {})}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def _spezza(testo: str) -> list:
    """Divide un messaggio in frasi; separa anche 'la stessa cosa per X e Y'."""
    parti = re.split(r"(?<=[.!?])\s+|\n+|\s+-\s+", testo)
    return [p.strip() for p in parti if p and p.strip()]


def trova_fornitore(testo: str) -> str:
    t = _norm(testo)
    for f in FORNITORI:
        if _norm(f) in t:
            return f.title() if f not in ("ENI", "EON", "A2A", "AGSM", "ACEA") else f
    return ""


async def _clienti_candidati() -> list:
    db = _d["db"]
    limite = (_now() - timedelta(days=400)).isoformat()
    proj = {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "telefono": 1, "venditore_id": 1, "lavorazione": 1, "gestione": 1, "created_at": 1, "nuovo_fornitore": 1}
    out = []
    async for c in db.clients.find({"anonimizzato_at": {"$in": [None]}, "gestione": {"$ne": "enel"}, "created_at": {"$gte": limite}}, proj):
        if _d["cliente_energia"](c) and c.get("cognome") and c.get("nome"):
            out.append(c)
    return out


def _match_clienti(testo: str, clienti: list) -> list:
    t = f" {_norm(testo)} "
    trovati = []
    for c in clienti:
        cogn = _norm(c["cognome"]).split()
        nomi = _norm(c["nome"]).split()
        if not cogn or not nomi:
            continue
        if all(f" {w} " in t for w in cogn) and f" {nomi[0]} " in t:
            trovati.append(c)
    return trovati


async def classifica(testo: str) -> dict:
    try:
        r = await get_jev_client().system_one(model="jev-latest", state={"messaggio_backoffice_energia": testo},
                                              questions={"categoria": Choice(instructions="Di che tipo è questo messaggio del back-office Switcho sulla pratica luce/gas?", criteria=CATEGORIE)})
        ch = r.choices["categoria"]
        return {"categoria": ch.choice, "confidenza": round(float(ch.confidence), 3), "ai": True}
    except (TypeSafeError, Exception) as e:
        logger.warning(f"Jev non disponibile: {e}")
        return {"categoria": _classifica_regole(testo), "confidenza": 0.0, "ai": False}


def _classifica_regole(testo: str) -> str:
    t = _norm(testo)
    if "annullat" in t and ("ip " in t or "mandato" in t):
        return "annullata_ip"
    if "annullat" in t or "scadut" in t:
        return "annullata_firma"
    if "confermare" in t or "conferma" in t and ("link" in t or "plico" in t):
        return "conferma_link"
    if "bollett" in t or "documento" in t or "serve" in t or "serv" in t:
        return "documenti"
    if "?" in testo:
        return "verifica"
    return "altro"


async def _documenti_cliente(client_id: str) -> list:
    return await _d["db"].attachments.find({"client_id": client_id, "is_deleted": False}, {"_id": 0, "id": 1, "original_filename": 1, "tipo": 1, "created_at": 1}).to_list(50)


async def _applica(seg: dict, c: dict, user_name: str = "Switcho") -> dict:
    """Aggiorna la pratica del cliente in base alla categoria e manda l'avviso al cliente se previsto."""
    db = _d["db"]
    cat = seg["categoria"]
    azioni = []
    nuovo = STATO_PRATICA.get(cat)
    fake_user = {"id": "switcho", "name": user_name, "role": "sistema"}
    if nuovo and c.get("lavorazione") != nuovo and c.get("lavorazione") not in ("cambio_effettuato", "rinnovato"):
        upd = {"lavorazione": nuovo, "updated_at": _now().isoformat()}
        if seg.get("fornitore") and not c.get("nuovo_fornitore"):
            upd["nuovo_fornitore"] = seg["fornitore"]
        await db.clients.update_one({"id": c["id"]}, {"$set": upd})
        await _d["log_lavorazione"](c, fake_user, nuovo, f"Switcho: {seg['testo'][:300]}")
        azioni.append(f"pratica → {nuovo}")
        c = {**c, **upd}
    elif nuovo:
        await _d["log_lavorazione"](c, fake_user, c.get("lavorazione", ""), f"Switcho (sollecito): {seg['testo'][:300]}")
        azioni.append("sollecito registrato")
    docs = await _documenti_cliente(c["id"]) if cat == "documenti" else []
    avviso = None
    if cat == "conferma_link" and (await cfg()).get("auto_avviso_cliente") and c.get("telefono"):
        ultimo = c.get("conferma_link_sent_at")
        if not ultimo or (_now() - datetime.fromisoformat(ultimo)) > timedelta(hours=20):
            store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0})
            sess = await _d["wa_sessione_negozio"](store)
            msg = _d["store_msg"](store, "msg_conferma_link", nome=c.get("nome", ""), fornitore=seg.get("fornitore") or "il fornitore")
            try:
                await _d["wa_send"](c["telefono"], msg, session=sess, tipo="conferma_link", client_id=c["id"])
                await db.clients.update_one({"id": c["id"]}, {"$set": {"conferma_link_sent_at": _now().isoformat()}})
                avviso = {"ok": True, "at": _now().isoformat(), "session": sess}
                azioni.append("WhatsApp al cliente inviato")
            except HTTPException as e:
                avviso = {"ok": False, "error": str(e.detail)}
                azioni.append(f"WhatsApp al cliente FALLITO: {e.detail}")
        else:
            azioni.append("WhatsApp al cliente già inviato nelle ultime 20 ore")
    return {"client_id": c["id"], "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "store_id": c.get("venditore_id"),
            "azioni": azioni, "documenti_disponibili": docs, "avviso_cliente": avviso, "lavorazione": c.get("lavorazione")}


async def processa_messaggio(msg: dict) -> list:
    """Crea una segnalazione per ogni cliente citato (o una 'da abbinare')."""
    db = _d["db"]
    clienti = await _clienti_candidati()
    cls = await classifica(msg["testo"])
    fornitore = trova_fornitore(msg["testo"])
    trovati = {c["id"]: c for c in _match_clienti(msg["testo"], clienti)}
    nomi_store = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    segnalazioni = []
    base = {"messaggio_id": msg["id"], "testo": msg["testo"], "categoria": cls["categoria"], "categoria_label": LABEL[cls["categoria"]],
            "confidenza": cls["confidenza"], "ai": cls["ai"], "fornitore": fornitore, "at": msg["at"], "stato": "aperta", "origine": msg.get("origine", "gruppo")}
    if not trovati:
        seg = {**base, "id": str(uuid.uuid4()), "client_id": None, "client_name": None, "azioni": ["cliente non riconosciuto: da abbinare"]}
        await db.switcho_segnalazioni.insert_one(seg)
        seg.pop("_id", None)
        return [seg]
    for c in trovati.values():
        seg = {**base, "id": str(uuid.uuid4())}
        esito = await _applica(seg, c) if cls["categoria"] != "altro" else {"client_id": c["id"], "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(),
                                                                                "store_id": c.get("venditore_id"), "azioni": ["nessuna azione automatica"], "documenti_disponibili": [], "avviso_cliente": None}
        seg.update(esito)
        seg["negozio"] = nomi_store.get(esito.get("store_id"), "-")
        if cls["categoria"] in ("verifica", "altro"):
            seg["stato"] = "aperta"
        await db.switcho_segnalazioni.insert_one(seg)
        seg.pop("_id", None)
        segnalazioni.append(seg)
    return segnalazioni


async def registra_messaggio(testo: str, mittente: str, origine: str, message_id: str = "", at: str = "") -> list:
    db = _d["db"]
    testo = (testo or "").strip()
    if not testo:
        return []
    mid = message_id or f"{origine}-{uuid.uuid4()}"
    if await db.switcho_messaggi.find_one({"id": mid}):
        return []
    msg = {"id": mid, "testo": testo, "mittente": mittente, "origine": origine, "at": at or _now().isoformat(), "ricevuto_at": _now().isoformat()}
    await db.switcho_messaggi.insert_one(msg)
    segs = await processa_messaggio(msg)
    await db.switcho_messaggi.update_one({"id": mid}, {"$set": {"segnalazioni": [s["id"] for s in segs]}})
    return segs


# ---------- webhook dal microservizio WhatsApp ----------
class InboxInput(BaseModel):
    text: str = ""
    sender: str = ""
    group_id: str = ""
    message_id: str = ""
    timestamp: str = ""
    session: str = ""


@router.post("/whatsapp/inbox")
async def inbox(input: InboxInput, request: Request):
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    tok = request.headers.get("X-Webhook-Secret", "") or request.headers.get("Authorization", "")[7:]
    if not secret or tok != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    c = await cfg()
    if not c.get("attivo"):
        return {"status": "ignorato", "motivo": "integrazione disattivata"}
    if c.get("gruppo_jid") and input.group_id != c["gruppo_jid"]:
        return {"status": "ignorato", "motivo": "altro gruppo"}
    mitt = re.sub(r"\D", "", input.sender)
    atteso = re.sub(r"\D", "", c.get("mittente") or "")
    if atteso and not mitt.endswith(atteso[-9:]):
        return {"status": "ignorato", "motivo": "mittente non Switcho"}
    segs = await registra_messaggio(input.text, mitt, "gruppo", input.message_id, input.timestamp)
    return {"status": "ok", "segnalazioni": len(segs)}


# ---------- API per gli addetti ----------
class IncollaInput(BaseModel):
    testo: str


@router.post("/switcho/incolla")
async def incolla(input: IncollaInput, user: dict = Depends(require_addetto)):
    """Incolla testo copiato dal gruppo WhatsApp: ogni riga '[hh:mm, gg/mm/aaaa] +39…: testo' o paragrafo diventa un messaggio."""
    righe = re.split(r"(?=\[\d{1,2}:\d{2}, \d{1,2}/\d{1,2}/\d{4}\])", input.testo)
    blocchi = []
    for r in righe:
        r = r.strip()
        if not r:
            continue
        m = re.match(r"\[(\d{1,2}:\d{2}), (\d{1,2})/(\d{1,2})/(\d{4})\]\s*([^:]+):\s*(.*)", r, re.S)
        if m:
            at = f"{m.group(4)}-{int(m.group(3)):02d}-{int(m.group(2)):02d}T{m.group(1)}:00"
            blocchi.append((m.group(6).strip(), m.group(5).strip(), at))
        else:
            blocchi.extend((p.strip(), "incolla", "") for p in re.split(r"\n\s*\n", r) if p.strip())
    tutte = []
    for testo, mitt, at in blocchi:
        tutte += await registra_messaggio(testo, mitt, "incolla", "", at)
    return {"messaggi": len(blocchi), "segnalazioni": tutte}


@router.get("/switcho/segnalazioni")
async def segnalazioni(stato: str = "aperta", limit: int = 200, user: dict = Depends(require_addetto)):
    q = {"stato": stato} if stato != "tutte" else {}
    items = await _d["db"].switcho_segnalazioni.find(q, {"_id": 0}).sort("at", -1).to_list(limit)
    for s in items:
        if s.get("client_id") and s["categoria"] == "documenti":
            s["documenti_disponibili"] = await _documenti_cliente(s["client_id"])
    return items


class AbbinaInput(BaseModel):
    client_id: str


@router.post("/switcho/segnalazioni/{seg_id}/abbina")
async def abbina(seg_id: str, input: AbbinaInput, user: dict = Depends(require_addetto)):
    db = _d["db"]
    seg = await db.switcho_segnalazioni.find_one({"id": seg_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segnalazione non trovata")
    c = await db.clients.find_one({"id": input.client_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente non trovato")
    esito = await _applica(seg, c, user_name=f"Switcho (abbinato da {user['name']})") if seg["categoria"] != "altro" else {
        "client_id": c["id"], "client_name": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "store_id": c.get("venditore_id"), "azioni": ["abbinato"], "documenti_disponibili": [], "avviso_cliente": None}
    store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0, "nome": 1})
    esito["negozio"] = (store or {}).get("nome", "-")
    esito["abbinato_da"] = user["name"]
    await db.switcho_segnalazioni.update_one({"id": seg_id}, {"$set": esito})
    return {**seg, **esito}


class CategoriaInput(BaseModel):
    categoria: str


@router.post("/switcho/segnalazioni/{seg_id}/categoria")
async def cambia_categoria(seg_id: str, input: CategoriaInput, user: dict = Depends(require_addetto)):
    if input.categoria not in CATEGORIE:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    db = _d["db"]
    seg = await db.switcho_segnalazioni.find_one({"id": seg_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segnalazione non trovata")
    upd = {"categoria": input.categoria, "categoria_label": LABEL[input.categoria], "corretta_da": user["name"]}
    if seg.get("client_id") and input.categoria != "altro":
        c = await db.clients.find_one({"id": seg["client_id"]}, {"_id": 0})
        if c:
            upd.update(await _applica({**seg, **upd}, c, user_name=f"Switcho (corretto da {user['name']})"))
    await db.switcho_segnalazioni.update_one({"id": seg_id}, {"$set": upd})
    return {**seg, **upd}


@router.post("/switcho/segnalazioni/{seg_id}/chiudi")
async def chiudi(seg_id: str, user: dict = Depends(require_addetto)):
    res = await _d["db"].switcho_segnalazioni.update_one({"id": seg_id}, {"$set": {"stato": "chiusa", "chiusa_da": user["name"], "chiusa_at": _now().isoformat()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Segnalazione non trovata")
    return {"status": "ok"}


@router.post("/switcho/segnalazioni/{seg_id}/avvisa-cliente")
async def avvisa_cliente(seg_id: str, user: dict = Depends(require_addetto)):
    """Manda (o rimanda) al cliente, dal suo negozio, l'avviso di confermare il link."""
    db = _d["db"]
    seg = await db.switcho_segnalazioni.find_one({"id": seg_id}, {"_id": 0})
    if not seg or not seg.get("client_id"):
        raise HTTPException(status_code=404, detail="Segnalazione senza cliente")
    c = await db.clients.find_one({"id": seg["client_id"]}, {"_id": 0})
    if not c or not c.get("telefono"):
        raise HTTPException(status_code=400, detail="Cliente senza telefono")
    store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0})
    sess = await _d["wa_sessione_negozio"](store)
    msg = _d["store_msg"](store, "msg_conferma_link", nome=c.get("nome", ""), fornitore=seg.get("fornitore") or "il fornitore")
    await _d["wa_send"](c["telefono"], msg, session=sess, tipo="conferma_link", client_id=c["id"])
    await db.clients.update_one({"id": c["id"]}, {"$set": {"conferma_link_sent_at": _now().isoformat()}})
    await db.switcho_segnalazioni.update_one({"id": seg_id}, {"$set": {"avviso_cliente": {"ok": True, "at": _now().isoformat(), "session": sess, "da": user["name"]}},
                                                              "$push": {"azioni": f"WhatsApp al cliente inviato da {user['name']}"}})
    return {"status": "ok"}


@router.post("/switcho/segnalazioni/{seg_id}/richiedi-documenti")
async def richiedi_documenti(seg_id: str, user: dict = Depends(require_addetto)):
    """Chiede al cliente, dal suo negozio, di inviare bollette/documenti (testo msg_bollette del negozio)."""
    db = _d["db"]
    seg = await db.switcho_segnalazioni.find_one({"id": seg_id}, {"_id": 0})
    if not seg or not seg.get("client_id"):
        raise HTTPException(status_code=404, detail="Segnalazione senza cliente")
    c = await db.clients.find_one({"id": seg["client_id"]}, {"_id": 0})
    if not c or not c.get("telefono"):
        raise HTTPException(status_code=400, detail="Cliente senza telefono")
    store = await db.stores.find_one({"id": c.get("venditore_id")}, {"_id": 0})
    sess = await _d["wa_sessione_negozio"](store)
    msg = _d["store_msg"](store, "msg_bollette", nome=c.get("nome", ""))
    await _d["wa_send"](c["telefono"], msg, session=sess, tipo="richiesta_documenti", client_id=c["id"])
    await db.clients.update_one({"id": c["id"]}, {"$set": {"bollette_msg_sent_at": _now().isoformat()}})
    await db.switcho_segnalazioni.update_one({"id": seg_id}, {"$set": {"richiesta_documenti": {"at": _now().isoformat(), "da": user["name"], "session": sess}},
                                                              "$push": {"azioni": f"Richiesta documenti al cliente inviata da {user['name']}"}})
    return {"status": "ok"}


async def chiudi_per_pratica(client_id: str, nuovo_stato: str, da: str = "") -> int:
    """Quando la pratica va a Cambio effettuato/Rinnovato, chiude le segnalazioni Switcho aperte di quel cliente."""
    if nuovo_stato not in ("cambio_effettuato", "rinnovato"):
        return 0
    res = await _d["db"].switcho_segnalazioni.update_many({"client_id": client_id, "stato": "aperta"},
                                                           {"$set": {"stato": "chiusa", "chiusa_at": _now().isoformat(), "chiusa_da": f"automatico ({nuovo_stato}{', ' + da if da else ''})"},
                                                            "$push": {"azioni": f"chiusa automaticamente: pratica → {nuovo_stato}"}})
    return res.modified_count


async def _invia_gruppo(testo: str, media: list | None = None) -> dict:
    c = await cfg()
    if not c.get("gruppo_jid"):
        raise HTTPException(status_code=400, detail="ID gruppo Switcho non configurato (Impostazioni Switcho)")
    sess = c.get("session_risposta") or await _d["store_id_by_name"]("Sondrio") or "default"
    payload = {"phone": c["gruppo_jid"], "message": testo, "session": sess}
    if media:
        payload["media"] = media
    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            resp = await http_client.post(f"{_d['WA_SERVICE']}/send", json=payload, headers=_d["wa_headers"]())
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Servizio WhatsApp non raggiungibile: {e}")
    ok = resp.status_code == 200 and bool(data.get("success"))
    await _d["db"].wa_log.insert_one({"id": str(uuid.uuid4()), "phone": c["gruppo_jid"], "session": sess, "message": testo[:1000], "tipo": "switcho_gruppo",
                                      "at": _now().isoformat(), "ok": ok, "error": None if ok else data.get("error", "Invio fallito"), "media": len(media or [])})
    if not ok:
        raise HTTPException(status_code=502, detail=data.get("error", "Invio al gruppo fallito (il microservizio deve supportare i gruppi/allegati)"))
    return data


class RispondiInput(BaseModel):
    testo: str
    attachment_ids: list[str] = []


@router.post("/switcho/segnalazioni/{seg_id}/rispondi")
async def rispondi(seg_id: str, input: RispondiInput, user: dict = Depends(require_addetto)):
    """Risponde nel gruppo Switcho (dal numero di Sondrio) con testo e/o documenti del cliente."""
    import base64
    db = _d["db"]
    seg = await db.switcho_segnalazioni.find_one({"id": seg_id}, {"_id": 0})
    if not seg:
        raise HTTPException(status_code=404, detail="Segnalazione non trovata")
    media = []
    for att in await db.attachments.find({"id": {"$in": input.attachment_ids}, "is_deleted": False}, {"_id": 0}).to_list(20):
        if seg.get("client_id") and att.get("client_id") != seg["client_id"]:
            continue
        data, ct = _d["get_object"](att["storage_path"])
        media.append({"filename": att.get("original_filename") or "documento", "mimetype": att.get("content_type") or ct, "base64": base64.b64encode(data).decode()})
    testo = input.testo.strip() or (f"Documenti di {seg.get('client_name')} in allegato." if media else "")
    if not testo and not media:
        raise HTTPException(status_code=400, detail="Scrivi un testo o seleziona almeno un documento")
    await _invia_gruppo(testo, media)
    await db.switcho_segnalazioni.update_one({"id": seg_id}, {"$set": {"risposta": {"testo": testo, "allegati": len(media), "da": user["name"], "at": _now().isoformat()}},
                                                              "$push": {"azioni": f"Risposta al gruppo da {user['name']} ({len(media)} allegati)"}})
    return {"status": "ok", "allegati": len(media)}


# ---------- promemoria 48 ore ----------
async def promemoria_conferma_link() -> dict:
    """Segnalazioni 'conferma_link' aperte da oltre 48h: agenda + WhatsApp agli addetti, una volta sola."""
    db = _d["db"]
    limite = (_now() - timedelta(hours=48)).isoformat()
    segs = await db.switcho_segnalazioni.find({"stato": "aperta", "categoria": "conferma_link", "client_id": {"$ne": None},
                                               "at": {"$lte": limite}, "promemoria_48h_at": {"$in": [None]}}, {"_id": 0}).to_list(200)
    if not segs:
        return {"promemoria": 0}
    cfg_lav = await db.settings.find_one({"key": "lavorazioni_cfg"}, {"_id": 0})
    addetti = await db.users.find({"id": {"$in": ((cfg_lav or {}).get("value") or {}).get("addetti", [])}, "attivo": {"$ne": False}}, {"_id": 0}).to_list(50)
    oggi = _now().date().isoformat()
    righe = []
    for s in segs:
        c = await db.clients.find_one({"id": s["client_id"]}, {"_id": 0, "lavorazione": 1})
        if not c or c.get("lavorazione") in ("cambio_effettuato", "rinnovato", "annullato"):
            await db.switcho_segnalazioni.update_one({"id": s["id"]}, {"$set": {"promemoria_48h_at": _now().isoformat(), "promemoria_skip": True}})
            continue
        righe.append(f"• {s['client_name']} ({s.get('negozio', '-')}, {s.get('fornitore') or 'fornitore'})")
        for u in addetti:
            await db.agenda_lavorazioni.insert_one({"id": str(uuid.uuid4()), "user_id": u["id"], "client_id": s["client_id"], "client_name": s["client_name"], "data": oggi,
                                                    "nota": f"Switcho: conferma link {s.get('fornitore') or ''} richiesta da oltre 48h e non chiusa — ricontattare il cliente", "fatto": False,
                                                    "origine": "switcho_48h", "created_at": _now().isoformat()})
        await db.switcho_segnalazioni.update_one({"id": s["id"]}, {"$set": {"promemoria_48h_at": _now().isoformat()}, "$push": {"azioni": "promemoria 48h agli addetti"}})
    if righe:
        testo = "⏰ Switcho: pratiche in attesa di conferma link da oltre 48 ore e non ancora chiuse:\n" + "\n".join(righe) + "\nRicontatta i clienti: le trovi in agenda nel Riepilogo Lavorazioni."
        for u in addetti:
            if u.get("telefono"):
                try:
                    await _d["wa_send"](u["telefono"], testo, session=(u.get("store_ids") or ["default"])[0], tipo="switcho_48h")
                except Exception as e:
                    logger.warning(f"promemoria 48h a {u['name']} fallito: {e}")
    return {"promemoria": len(righe)}


# ---------- configurazione (admin) ----------
class CfgInput(BaseModel):
    gruppo_jid: str = ""
    mittente: str = ""
    session_risposta: str = ""
    auto_avviso_cliente: bool = True
    attivo: bool = True


@router.get("/switcho/config")
async def get_config(user: dict = Depends(require_addetto)):
    c = await cfg()
    db = _d["db"]
    c["messaggi_ricevuti"] = await db.switcho_messaggi.count_documents({})
    c["ultimo_messaggio"] = await db.switcho_messaggi.find_one({}, {"_id": 0, "at": 1, "origine": 1, "testo": 1}, sort=[("ricevuto_at", -1)])
    c["webhook_url"] = "/api/whatsapp/inbox"
    return c


@router.put("/switcho/config")
async def put_config(input: CfgInput, user: dict = Depends(require_addetto)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    await _d["db"].settings.update_one({"key": "switcho_cfg"}, {"$set": {"value": input.model_dump()}}, upsert=True)
    return await cfg()


@router.get("/switcho/snippet")
async def snippet(user: dict = Depends(require_addetto)):
    """Codice da aggiungere al microservizio WhatsApp (Baileys) per inoltrare i messaggi del gruppo."""
    return {"istruzioni": "Aggiungi nel microservizio Baileys, dopo la creazione del socket di ogni sessione. Imposta le variabili CRM_URL (URL del gestionale) e CRM_WEBHOOK_SECRET (= WEBHOOK_CRON_SECRET del backend).",
            "codice": """// --- Inoltro messaggi dei gruppi al gestionale (Switcho) ---
sock.ev.on('messages.upsert', async ({ messages, type }) => {
  if (type !== 'notify') return;
  for (const m of messages) {
    const jid = m.key?.remoteJid || '';
    if (!jid.endsWith('@g.us') || m.key?.fromMe) continue;           // solo gruppi, non i nostri
    const text = m.message?.conversation || m.message?.extendedTextMessage?.text
              || m.message?.imageMessage?.caption || m.message?.documentMessage?.caption || '';
    if (!text) continue;
    const sender = (m.key?.participant || '').split('@')[0];
    try {
      await fetch(`${process.env.CRM_URL}/api/whatsapp/inbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': process.env.CRM_WEBHOOK_SECRET },
        body: JSON.stringify({ text, sender, group_id: jid, message_id: m.key.id, session: sessionName,
                               timestamp: new Date((Number(m.messageTimestamp) || 0) * 1000).toISOString() })
      });
    } catch (e) { console.error('inbox CRM', e.message); }
  }
});

// --- Invio a gruppi e con allegati: nell'endpoint POST /send ---
// const jid = phone.endsWith('@g.us') ? phone : `${phone.replace(/\\D/g, '')}@s.whatsapp.net`;
// if (Array.isArray(media) && media.length) {
//   for (const f of media) {
//     const buf = Buffer.from(f.base64, 'base64');
//     const isImg = (f.mimetype || '').startsWith('image/');
//     await sock.sendMessage(jid, isImg ? { image: buf, caption: message } : { document: buf, mimetype: f.mimetype, fileName: f.filename, caption: message });
//     message = '';
//   }
//   if (!message) return res.json({ success: true, session: sessionName });
// }
// await sock.sendMessage(jid, { text: message });
// Per conoscere l'ID del gruppo: const groups = await sock.groupFetchAllParticipating(); console.log(Object.values(groups).map(g => g.id + ' ' + g.subject));
"""}
