"""Incentivi RS: fondo premi autofinanziato da provvigioni EOLO/energia confermate, gettoni, classifica, simulazione, estratti conto negozi esterni."""
import base64
import csv
import io
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/incentivi", tags=["incentivi"])
_d: dict = {}

CONFIG_ID = "config"
TIER_KEYS = ["5", "10", "15", "20"]


def setup(**deps):
    _d.update(deps)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _user(request: Request) -> dict:
    return await _d["current_user"](request)


async def _admin(request: Request) -> dict:
    u = await _user(request)
    if u["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return u


# ---------------- Config ----------------
async def _default_config() -> dict:
    db = _d["db"]
    stores = {s["nome"].strip().lower(): s["id"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["name"].strip().lower(): u["id"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    fondo = [stores[n] for n in ("morbegno", "gravedona") if n in stores]
    srls = [stores[n] for n in ("sondrio",) if n in stores]
    return {"id": CONFIG_ID, "online": False, "gettone_lordo": 25.0, "costo_datore_fattore": 1.45, "eolo_fondo_pct": 50.0,
            "trattenuta_terzi_pct": 15.0, "energia_importo": 50.0, "energia_acquisizione": 25.0, "energia_lavorazione": 25.0,
            "premi_pct": [50, 30, 20], "tetto_fondo": 0.0, "padre_in_fondo": True,
            "partecipanti": [users[n] for n in ("kevin", "deborah", "silvio", "bruno") if n in users],
            "coef_eolo": 100.0, "coef_energia": 100.0, "coef_riparazione": 50.0, "valore_sim_nuova": 5.0, "valore_sim_mnp": 10.0, "valore_fisso": 20.0,
            "bonus_squadra_pct": 0.0,
            "negozi_fondo": fondo, "entita": [{"store_id": s, "entita": "ditta", "da": ""} for s in fondo] + [{"store_id": s, "entita": "srls", "da": ""} for s in srls],
            "persona_negozio": {stores["gravedona"]: users["kevin"]} if "gravedona" in stores and "kevin" in users else {},
            "spareggio": "contratti_eolo_energia", "updated_at": _now()}


async def get_config() -> dict:
    db = _d["db"]
    c = await db.incentivi_config.find_one({"id": CONFIG_ID}, {"_id": 0})
    if not c:
        c = await _default_config()
        await db.incentivi_config.insert_one(dict(c))
    return c


class ConfigInput(BaseModel):
    gettone_lordo: Optional[float] = None
    costo_datore_fattore: Optional[float] = None
    eolo_fondo_pct: Optional[float] = None
    trattenuta_terzi_pct: Optional[float] = None
    energia_importo: Optional[float] = None
    energia_acquisizione: Optional[float] = None
    energia_lavorazione: Optional[float] = None
    premi_pct: Optional[List[float]] = None
    tetto_fondo: Optional[float] = None
    padre_in_fondo: Optional[bool] = None
    partecipanti: Optional[List[str]] = None
    coef_eolo: Optional[float] = None
    coef_energia: Optional[float] = None
    coef_riparazione: Optional[float] = None
    valore_sim_nuova: Optional[float] = None
    valore_sim_mnp: Optional[float] = None
    valore_fisso: Optional[float] = None
    bonus_squadra_pct: Optional[float] = None
    negozi_fondo: Optional[List[str]] = None
    entita: Optional[List[dict]] = None
    persona_negozio: Optional[dict] = None
    spareggio: Optional[str] = None


@router.get("/config")
async def read_config(request: Request):
    await _admin(request)
    return await get_config()


@router.put("/config")
async def update_config(input: ConfigInput, request: Request):
    user = await _admin(request)
    db = _d["db"]
    old = await get_config()
    changes = {k: v for k, v in input.model_dump(exclude_unset=True).items() if v is not None}
    if "premi_pct" in changes and sum(changes["premi_pct"]) > 100:
        raise HTTPException(status_code=400, detail="La somma delle percentuali premi non può superare 100")
    diff = {k: {"prima": old.get(k), "dopo": v} for k, v in changes.items() if old.get(k) != v}
    if diff:
        await db.incentivi_config.update_one({"id": CONFIG_ID}, {"$set": {**changes, "updated_at": _now()}})
        await db.incentivi_config_log.insert_one({"id": str(uuid.uuid4()), "at": _now(), "user_id": user["id"], "user_name": user["name"], "modifiche": diff})
    return await get_config()


@router.get("/config/log")
async def config_log(request: Request):
    await _admin(request)
    return await _d["db"].incentivi_config_log.find({}, {"_id": 0}).sort("at", -1).to_list(200)


class OnlineInput(BaseModel):
    online: bool
    mese_partenza: str = ""
    forza: bool = False


async def checklist_online() -> dict:
    db = _d["db"]
    cfg = await get_config()
    users = {u["id"]: u async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "telefono": 1})}
    senza_tel = [users[u]["name"] for u in cfg.get("partecipanti", []) if u in users and not (users[u].get("telefono") or "").strip()]
    firmati = {f["user_id"] async for f in db.incentivi_firme.find({"stato": "firmata", "versione": cfg.get("updated_at", "")}, {"_id": 0, "user_id": 1})}
    senza_firma = [users[u]["name"] for u in cfg.get("partecipanti", []) if u in users and u not in firmati]
    voci = [
        {"id": "partecipanti", "label": "Almeno 2 partecipanti configurati", "ok": len(cfg.get("partecipanti", [])) >= 2, "dettaglio": f"{len(cfg.get('partecipanti', []))} partecipanti"},
        {"id": "regolamento", "label": "Regolamento PDF generato con le regole attuali", "ok": bool(cfg.get("regolamento_generato_at")) and cfg.get("regolamento_generato_at", "") >= cfg.get("updated_at", ""),
         "dettaglio": f"generato il {cfg.get('regolamento_generato_at', '')[:10]}" if cfg.get("regolamento_generato_at") else "non ancora generato"},
        {"id": "firme", "label": "Regolamento firmato digitalmente da tutti i partecipanti", "ok": not senza_firma, "dettaglio": ("mancano: " + ", ".join(senza_firma)) if senza_firma else "tutti firmato"},
        {"id": "telefoni", "label": "Numero WhatsApp per tutti i partecipanti", "ok": not senza_tel, "dettaglio": ("mancano: " + ", ".join(senza_tel)) if senza_tel else "tutti presenti"},
        {"id": "mese", "label": "Mese di partenza impostato", "ok": bool(cfg.get("mese_partenza")), "dettaglio": cfg.get("mese_partenza") or "da scegliere"},
        {"id": "soglie", "label": "Tabella soglie EOLO caricata per il mese di partenza", "ok": bool(cfg.get("mese_partenza")) and bool(await db.incentivi_soglie.find_one({"mese": cfg.get("mese_partenza")})), "dettaglio": ""},
    ]
    return {"voci": voci, "pronto": all(v["ok"] for v in voci), "online": cfg.get("online", False), "mese_partenza": cfg.get("mese_partenza", "")}


@router.get("/checklist")
async def get_checklist(request: Request):
    await _admin(request)
    return await checklist_online()


@router.post("/online")
async def set_online(input: OnlineInput, request: Request):
    user = await _admin(request)
    db = _d["db"]
    if input.mese_partenza:
        if not re.fullmatch(r"\d{4}-\d{2}", input.mese_partenza):
            raise HTTPException(status_code=400, detail="Mese di partenza non valido")
        await db.incentivi_config.update_one({"id": CONFIG_ID}, {"$set": {"mese_partenza": input.mese_partenza}})
    if input.online:
        ck = await checklist_online()
        if not ck["pronto"] and not input.forza:
            raise HTTPException(status_code=400, detail="Checklist incompleta: " + "; ".join(v["label"] for v in ck["voci"] if not v["ok"]))
    await db.incentivi_config.update_one({"id": CONFIG_ID}, {"$set": {"online": input.online, "online_at": _now(), "online_da": user["name"]}})
    await db.incentivi_config_log.insert_one({"id": str(uuid.uuid4()), "at": _now(), "user_id": user["id"], "user_name": user["name"], "modifiche": {"online": {"dopo": input.online}, **({"mese_partenza": {"dopo": input.mese_partenza}} if input.mese_partenza else {})}})
    return {"online": input.online}


class EntitaInput(BaseModel):
    store_id: str
    entita: str  # ditta | srls
    da: str = ""  # YYYY-MM


@router.post("/entita")
async def cambia_entita(input: EntitaInput, request: Request):
    """Tasto 'cambia entità': da `da` in poi il negozio appartiene all'altra società (storico intatto)."""
    user = await _admin(request)
    if input.entita not in ("ditta", "srls"):
        raise HTTPException(status_code=400, detail="Entità non valida")
    cfg = await get_config()
    ent = [e for e in cfg.get("entita", []) if not (e["store_id"] == input.store_id and e.get("da", "") == input.da)]
    ent.append({"store_id": input.store_id, "entita": input.entita, "da": input.da})
    await _d["db"].incentivi_config.update_one({"id": CONFIG_ID}, {"$set": {"entita": ent, "updated_at": _now()}})
    await _d["db"].incentivi_config_log.insert_one({"id": str(uuid.uuid4()), "at": _now(), "user_id": user["id"], "user_name": user["name"], "modifiche": {"entita": {"dopo": input.model_dump()}}})
    return await get_config()


def _entita_di(cfg: dict, store_id: str, mese: str) -> str:
    """Entità valida per il negozio nel mese: la regola con `da` più recente ≤ mese. '' = negozio terzo."""
    best, best_da = "", None
    for e in cfg.get("entita", []):
        if e["store_id"] != store_id or (e.get("da") and e["da"] > mese):
            continue
        if best_da is None or (e.get("da") or "") >= best_da:
            best, best_da = e["entita"], e.get("da") or ""
    return best


@router.get("/meta")
async def meta(request: Request):
    await _admin(request)
    db = _d["db"]
    stores = await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1}).sort("nome", 1).to_list(100)
    users = await db.users.find({"active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "role": 1, "store_ids": 1}).sort("name", 1).to_list(100)
    return {"stores": stores, "users": users}


# ---------------- Provvigioni (previste / confermate / storni) ----------------
def _ym(s) -> str:
    return (s or "")[:7]


async def _soglie_mese(mese: str) -> Optional[dict]:
    return await _d["db"].incentivi_soglie.find_one({"mese": mese}, {"_id": 0})


def _tier(n: int) -> Optional[str]:
    for k in reversed(TIER_KEYS):
        if n >= int(k):
            return k
    return None


def _importo_soglia(soglie: Optional[dict], prodotto: str, n_tot: int) -> float:
    if not soglie or not prodotto:
        return 0.0
    t = _tier(n_tot)
    if not t:
        return 0.0
    p = prodotto.strip().lower()
    for r in soglie.get("righe", []):
        if (r.get("prodotto") or "").strip().lower() == p:
            return float((r.get("soglie") or {}).get(t) or 0)
    return 0.0


@router.get("/previste")
async def previste(mese: str, request: Request):
    """Contratti del gestionale nel mese (competenza) non ancora caricati in pagamento: proposta di importo, editabile."""
    await _admin(request)
    db = _d["db"]
    cfg = await get_config()
    gia = {p["ref_id"] async for p in db.incentivi_provvigioni.find({"ref_id": {"$ne": ""}}, {"_id": 0, "ref_id": 1})}
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["id"]: u["name"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    out = []
    async for c in db.clients.find({"lavorazione": {"$in": ["cambio_effettuato", "rinnovato"]}, "anonimizzato_at": {"$in": [None]}}, {"_id": 0}):
        if _ym(c.get("data_contratto") or c.get("updated_at")) != mese:
            continue
        uid = c.get("operatore_id") or c.get("created_by") or ""
        out.append({"ref_id": f"client:{c['id']}", "fonte": "energia", "store_id": c.get("venditore_id", ""), "negozio": stores.get(c.get("venditore_id", ""), "—"),
                    "user_id": uid if uid in users else "", "persona": users.get(uid, "—"), "data_contratto": (c.get("data_contratto") or "")[:10],
                    "descrizione": f"{c.get('cognome', '')} {c.get('nome', '')} · {c.get('tipo_bolletta') or ''} · {(c.get('gestione') or 'cambiaora').upper()}".strip(),
                    "importo": float(cfg["energia_importo"]), "gia_caricata": f"client:{c['id']}" in gia, "anomalia": "" if uid in users else "Operatore non identificato"})
    eolo = [s async for s in db.servizi.find({"operatore_tel": {"$regex": "^eolo$", "$options": "i"}, "esito_attivazione": {"$nin": ["annullata", "respinta", "stornata", "non_riconosciuta"]}}, {"_id": 0})]
    eolo = [s for s in eolo if _ym(s.get("data_attivazione") or s.get("created_at")) == mese]
    soglie = await _soglie_mese(mese)
    n_tot = len(eolo)
    for s in eolo:
        uid = s.get("operatore_id") or s.get("created_by") or ""
        prod = s.get("categoria_prodotto") or s.get("prodotto") or ""
        out.append({"ref_id": f"servizio:{s['id']}", "fonte": "eolo", "store_id": s.get("venditore_id", ""), "negozio": stores.get(s.get("venditore_id", ""), "—"),
                    "user_id": uid if uid in users else "", "persona": users.get(uid, "—"), "data_contratto": (s.get("data_attivazione") or s.get("created_at") or "")[:10],
                    "descrizione": f"EOLO {prod} · {s.get('numero') or ''}".strip(), "importo": _importo_soglia(soglie, prod, n_tot), "gia_caricata": f"servizio:{s['id']}" in gia,
                    "anomalia": ("Operatore non identificato; " if uid not in users else "") + ("" if _importo_soglia(soglie, prod, n_tot) else "Importo soglia non trovato: inserire a mano")})
    return {"mese": mese, "n_eolo_totale": n_tot, "soglia_eolo": _tier(n_tot), "righe": out}


class ProvvigioneIn(BaseModel):
    ref_id: str = ""
    fonte: str  # eolo | energia
    store_id: str = ""
    user_id: str = ""
    importo: float
    data_contratto: str = ""
    descrizione: str = ""
    sezione: str = "compensi"  # compensi | gare | gara_retail | manuale


class ConfermaInput(BaseModel):
    mese: str  # mese di liquidazione (fattura)
    righe: List[ProvvigioneIn]


@router.post("/conferma")
async def conferma(input: ConfermaInput, request: Request):
    user = await _admin(request)
    db = _d["db"]
    if not re.fullmatch(r"\d{4}-\d{2}", input.mese):
        raise HTTPException(status_code=400, detail="Mese non valido")
    if await db.incentivi_chiusure.find_one({"mese": input.mese}):
        raise HTTPException(status_code=400, detail="Mese già chiuso: riaprilo prima di modificare")
    inseriti, saltati = 0, 0
    for r in input.righe:
        if r.fonte not in ("eolo", "energia"):
            raise HTTPException(status_code=400, detail="Fonte non valida")
        if r.ref_id and await db.incentivi_provvigioni.find_one({"ref_id": r.ref_id, "stato": "confermata"}):
            saltati += 1
            continue
        await db.incentivi_provvigioni.insert_one({"id": str(uuid.uuid4()), "mese": input.mese, "stato": "confermata", "origine": "gestionale" if r.ref_id.startswith(("client:", "servizio:")) else "manuale",
                                                   **r.model_dump(), "created_at": _now(), "created_by": user["name"]})
        inseriti += 1
    return {"inseriti": inseriti, "saltati_duplicati": saltati}


class StornoInput(BaseModel):
    provvigione_id: str
    mese: str  # mese in cui lo storno viene compensato
    motivo: str = ""


@router.post("/storno")
async def storno(input: StornoInput, request: Request):
    user = await _admin(request)
    db = _d["db"]
    p = await db.incentivi_provvigioni.find_one({"id": input.provvigione_id, "stato": "confermata"}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Provvigione non trovata")
    if await db.incentivi_provvigioni.find_one({"storno_di": p["id"]}):
        raise HTTPException(status_code=400, detail="Storno già registrato")
    if await db.incentivi_chiusure.find_one({"mese": input.mese}):
        raise HTTPException(status_code=400, detail="Mese già chiuso")
    doc = {**p, "id": str(uuid.uuid4()), "mese": input.mese, "stato": "stornata", "importo": -abs(float(p["importo"])), "storno_di": p["id"], "ref_id": "",
           "descrizione": f"STORNO {p.get('descrizione', '')} ({p['mese']}) {input.motivo}".strip(), "created_at": _now(), "created_by": user["name"]}
    await db.incentivi_provvigioni.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/provvigioni")
async def lista_provvigioni(mese: str, request: Request):
    await _admin(request)
    db = _d["db"]
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["id"]: u["name"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    righe = await db.incentivi_provvigioni.find({"mese": mese}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    for r in righe:
        r["negozio"] = stores.get(r.get("store_id"), r.get("negozio_nome") or "—")
        r["persona"] = users.get(r.get("user_id"), "—")
    return {"mese": mese, "righe": righe, "totale": round(sum(r["importo"] for r in righe), 2)}


@router.delete("/provvigioni/{pid}")
async def elimina_provvigione(pid: str, request: Request):
    await _admin(request)
    db = _d["db"]
    p = await db.incentivi_provvigioni.find_one({"id": pid}, {"_id": 0, "mese": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Non trovata")
    if await db.incentivi_chiusure.find_one({"mese": p["mese"]}):
        raise HTTPException(status_code=400, detail="Mese già chiuso")
    await db.incentivi_provvigioni.delete_one({"id": pid})
    return {"ok": True}


# ---------------- Import foglio Google (storico) ----------------
class ImportFoglioInput(BaseModel):
    sheet_id: str
    gid: str
    mese: str
    anteprima: bool = True


SEZIONI_FOGLIO = {0: "compensi", 4: "gare", 8: "gara_retail"}


def _parse_foglio(testo: str) -> list:
    rows = list(csv.reader(io.StringIO(testo)))
    out = []
    header_idx = next((i for i, r in enumerate(rows) if r and r[0].strip().upper() == "NEGOZIO"), None)
    if header_idx is None:
        return out
    for i, r in enumerate(rows[header_idx + 1:], start=header_idx + 1):
        for off, sez in SEZIONI_FOGLIO.items():
            if len(r) <= off + 3 or not r[off].strip():
                continue
            neg, tot, data, cod = r[off].strip(), r[off + 1].strip().replace(",", "."), r[off + 2].strip(), r[off + 3].strip()
            try:
                imp = float(tot)
            except ValueError:
                continue
            try:
                d = datetime.strptime(data, "%d/%m/%Y").date().isoformat() if data else ""
            except ValueError:
                d = data
            out.append({"negozio_nome": neg.upper(), "importo": imp, "data_contratto": d, "codice": cod, "sezione": sez, "riga": i})
    return out


@router.post("/import-foglio")
async def import_foglio(input: ImportFoglioInput, request: Request):
    user = await _admin(request)
    db = _d["db"]
    url = f"https://docs.google.com/spreadsheets/d/{input.sheet_id}/export?format=csv&gid={input.gid}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as cl:
        resp = await cl.get(url)
    if resp.status_code != 200 or "<html" in resp.text[:200].lower():
        raise HTTPException(status_code=400, detail="Foglio non leggibile: verifica che sia condiviso 'chiunque con il link'")
    righe = _parse_foglio(resp.text)
    stores = {s["nome"].strip().upper(): s["id"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    gia = {p["ref_id"] async for p in db.incentivi_provvigioni.find({"origine": "foglio", "mese": input.mese}, {"_id": 0, "ref_id": 1})}
    for r in righe:
        r["store_id"] = stores.get(r["negozio_nome"], "")
        r["ref_id"] = f"foglio:{input.gid}:{r['riga']}"
        r["duplicato"] = r["ref_id"] in gia
        r["anomalia"] = "" if r["store_id"] or r["negozio_nome"] == "PADRE" else "Negozio non riconosciuto"
    tot = round(sum(r["importo"] for r in righe), 2)
    if input.anteprima:
        return {"mese": input.mese, "righe": righe, "totale": tot, "nuove": sum(1 for r in righe if not r["duplicato"])}
    n = 0
    for r in righe:
        if r["duplicato"]:
            continue
        await db.incentivi_provvigioni.insert_one({"id": str(uuid.uuid4()), "mese": input.mese, "stato": "confermata", "origine": "foglio", "fonte": "eolo",
                                                   "ref_id": r["ref_id"], "store_id": r["store_id"], "negozio_nome": r["negozio_nome"], "user_id": "", "importo": r["importo"],
                                                   "data_contratto": r["data_contratto"], "descrizione": f"EOLO foglio {r['sezione']} {r['codice']}", "sezione": r["sezione"],
                                                   "created_at": _now(), "created_by": user["name"]})
        n += 1
    return {"mese": input.mese, "importate": n, "totale": tot}


# ---------------- Soglie EOLO (Carica gara) ----------------
PROMPT_GARA = ("Leggi il volantino 'Gara TOP Partner Retail' di EOLO e restituisci SOLO un JSON valido, senza testo attorno, con questa struttura: "
               '{"mese":"YYYY-MM","periodo":"testo","righe":[{"prodotto":"nome prodotto completo (es. EOLO Wi-Fi base, EOLO Wi-Fi +1 pacchetto Al Massimo o Senza Pensieri)","soglie":{"5":120,"10":150,"15":160,"20":170}}],'
               '"accessori":[{"voce":"Servizio Voce","importo":40}],"note":"eventuali note"}. Gli importi sono numeri in euro, le chiavi delle soglie sono il numero minimo di contratti (Da 5, Da 10, Da 15, Da 20).')


@router.post("/carica-gara")
async def carica_gara(request: Request, file: UploadFile = File(...)):
    await _admin(request)
    from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY mancante")
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Immagine troppo grande (max 12 MB)")
    b64 = base64.b64encode(raw).decode()
    chat = LlmChat(api_key=key, session_id=f"gara-{uuid.uuid4().hex[:8]}", system_message="Sei un lettore di tabelle. Rispondi solo con JSON.").with_model("openai", "gpt-5.4")
    try:
        testo = str(await chat.send_message(UserMessage(text=PROMPT_GARA, file_contents=[ImageContent(image_base64=b64)])))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lettura non riuscita: {e}")
    m = re.search(r"\{.*\}", testo, re.S)
    try:
        dati = json.loads(m.group(0) if m else testo)
    except Exception:
        raise HTTPException(status_code=502, detail="Risposta AI non interpretabile, riprova con una foto più nitida")
    return {"anteprima": dati}


class SoglieInput(BaseModel):
    mese: str
    periodo: str = ""
    righe: List[dict]
    accessori: List[dict] = []
    note: str = ""
    copiata_da: str = ""


@router.post("/soglie/copia")
async def copia_soglie(request: Request, da: str, a: str):
    """Copia la tabella gara di un mese su un altro (in attesa del volantino nuovo); segnata come 'copiata'."""
    user = await _admin(request)
    db = _d["db"]
    src = await db.incentivi_soglie.find_one({"mese": da}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail=f"Nessuna tabella per {da}")
    doc = {**src, "id": str(uuid.uuid4()), "mese": a, "copiata_da": da, "updated_at": _now(), "updated_by": user["name"]}
    await db.incentivi_soglie.update_one({"mese": a}, {"$set": doc}, upsert=True)
    return doc


@router.get("/soglie/storico")
async def soglie_storico(request: Request):
    """Mese per mese: tabella gara usata (originale/copiata), n. contratti EOLO liquidati e importo."""
    await _admin(request)
    db = _d["db"]
    soglie = {s["mese"]: s async for s in db.incentivi_soglie.find({}, {"_id": 0})}
    mesi = sorted(set(soglie) | {p["mese"] async for p in db.incentivi_provvigioni.find({"fonte": "eolo"}, {"_id": 0, "mese": 1})})
    out = []
    for m in mesi:
        pv = await db.incentivi_provvigioni.find({"mese": m, "fonte": "eolo"}, {"_id": 0, "importo": 1, "sezione": 1}).to_list(10000)
        s = soglie.get(m)
        out.append({"mese": m, "tabella": "nessuna" if not s else ("copiata" if s.get("copiata_da") else "originale"), "copiata_da": (s or {}).get("copiata_da", ""), "periodo": (s or {}).get("periodo", ""),
                    "n_righe": len((s or {}).get("righe", [])), "aggiornata_il": (s or {}).get("updated_at", "")[:10], "da": (s or {}).get("updated_by", ""),
                    "eolo_n": len(pv), "eolo_importo": _r(sum(p["importo"] for p in pv)), "gare_importo": _r(sum(p["importo"] for p in pv if p.get("sezione") in ("gare", "gara_retail")))})
    return out


@router.post("/soglie")
async def salva_soglie(input: SoglieInput, request: Request):
    user = await _admin(request)
    doc = {**input.model_dump(), "updated_at": _now(), "updated_by": user["name"]}
    await _d["db"].incentivi_soglie.update_one({"mese": input.mese}, {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return doc


@router.get("/soglie")
async def lista_soglie(request: Request, mese: str = ""):
    await _admin(request)
    q = {"mese": mese} if mese else {}
    return await _d["db"].incentivi_soglie.find(q, {"_id": 0}).sort("mese", -1).to_list(60)


# ---------------- Compensazioni (estratto conto negozi esterni) ----------------
class CompensazioneInput(BaseModel):
    mese: str
    store_id: str
    societa: str = "ditta"  # creditore: ditta | srls
    descrizione: str
    importo: float
    categoria: str = "altro"  # riparazioni | ricariche | sim | altro


@router.post("/compensazioni")
async def add_compensazione(input: CompensazioneInput, request: Request):
    user = await _admin(request)
    doc = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": _now(), "created_by": user["name"]}
    await _d["db"].incentivi_compensazioni.insert_one(dict(doc))
    return doc


@router.delete("/compensazioni/{cid}")
async def del_compensazione(cid: str, request: Request):
    await _admin(request)
    await _d["db"].incentivi_compensazioni.delete_one({"id": cid})
    return {"ok": True}


class PagatoInput(BaseModel):
    mese: str
    store_id: str
    societa: str
    pagato: bool


@router.post("/estratto-conto/pagato")
async def segna_pagato(input: PagatoInput, request: Request):
    user = await _admin(request)
    await _d["db"].incentivi_pagamenti.update_one({"mese": input.mese, "store_id": input.store_id, "societa": input.societa},
                                                  {"$set": {"pagato": input.pagato, "at": _now(), "da": user["name"]}}, upsert=True)
    return {"ok": True}


# ---------------- Calcolo ----------------
def _r(x) -> float:
    return round(float(x or 0), 2)


async def _attivita_mese(mese: str, partecipanti: set, cfg: dict) -> dict:
    """Valore classifica da riparazioni (stati reali lavorate: pronto/pronto_ritiro/consegnato, attribuite a chi le ha lavorate), SIM e fisso non-EOLO."""
    db = _d["db"]
    val = {u: {"riparazioni_n": 0, "riparazioni_margine": 0.0, "sim_nuova": 0, "sim_mnp": 0, "fisso": 0} for u in partecipanti}
    async for s in db.servizi.find({"tipo": {"$in": ["riparazione", "sim", "internet", "fisso"]}}, {"_id": 0, "tipo": 1, "stato": 1, "prezzo_finale": 1, "importo": 1, "costo_componente": 1, "con_ricambio": 1, "ricambi_usati": 1,
                                                                                                    "operatore_id": 1, "created_by": 1, "lavorato_da_id": 1, "lavorato_at": 1, "data_lavorazione": 1, "data_uscita": 1, "data_attivazione": 1, "created_at": 1,
                                                                                                    "tipo_attivazione": 1, "operatore_tel": 1, "esito_attivazione": 1}):
        if s["tipo"] == "riparazione":
            uid = s.get("lavorato_da_id") or s.get("operatore_id") or s.get("created_by") or ""
            if uid not in partecipanti or s.get("stato") not in ("pronto", "pronto_ritiro", "consegnato"):
                continue
            if _ym(s.get("lavorato_at") or s.get("data_lavorazione") or s.get("data_uscita") or s.get("created_at")) != mese:
                continue
            prezzo = float(s.get("prezzo_finale") or s.get("importo") or 0)
            costo = float(s.get("costo_componente") or 0) if s.get("con_ricambio") else sum(float(r.get("prezzo_acquisto") or r.get("costo") or 0) * int(r.get("quantita") or 1) for r in s.get("ricambi_usati") or [])
            val[uid]["riparazioni_n"] += 1
            val[uid]["riparazioni_margine"] += max(0.0, prezzo - costo)
        else:
            uid = s.get("operatore_id") or s.get("created_by") or ""
            if uid not in partecipanti:
                continue
            if _ym(s.get("data_attivazione") or s.get("created_at")) != mese or s.get("esito_attivazione") in ("annullata", "respinta", "stornata", "non_riconosciuta"):
                continue
            if s["tipo"] == "sim":
                val[uid]["sim_mnp" if s.get("tipo_attivazione") == "mnp" else "sim_nuova"] += 1
            elif (s.get("operatore_tel") or "").strip().lower() != "eolo":
                val[uid]["fisso"] += 1
    return val


async def calcola(mese: str, cfg: dict) -> dict:
    db = _d["db"]
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["id"]: u["name"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    partecipanti = [u for u in cfg.get("partecipanti", []) if u in users]
    pset = set(partecipanti)
    fondo_set = set(cfg.get("negozi_fondo", []))
    gettone, fatt = float(cfg["gettone_lordo"]), float(cfg["costo_datore_fattore"])
    tratt_pct = float(cfg["trattenuta_terzi_pct"]) / 100
    provv = await db.incentivi_provvigioni.find({"mese": mese}, {"_id": 0}).to_list(10000)
    anomalie = []

    per_persona = {u: {"user_id": u, "nome": users[u], "eolo_n": 0, "eolo_importo": 0.0, "energia_n": 0, "energia_importo": 0.0, "gettoni_n": 0} for u in partecipanti}
    fondo_lordo_eolo, energia_gruppo, gettoni_tot = 0.0, 0.0, 0
    fondo_per_entita = defaultdict(float)
    esterni = defaultdict(lambda: {"eolo": 0.0, "energia": 0.0, "n": 0, "righe": []})
    for p in provv:
        sid, imp, fonte = p.get("store_id", ""), float(p.get("importo") or 0), p.get("fonte")
        is_padre = not sid and (p.get("negozio_nome") == "PADRE")
        in_gruppo = sid in fondo_set or (is_padre and cfg.get("padre_in_fondo", True))
        ent = _entita_di(cfg, sid, mese) if sid else ("ditta" if is_padre else "")
        if not sid and not is_padre:
            anomalie.append({"tipo": "negozio_mancante", "descrizione": p.get("descrizione", ""), "importo": imp})
        uid = p.get("user_id", "") or (cfg.get("persona_negozio") or {}).get(sid, "")
        gett_applicato = uid in pset and imp > 0 and in_gruppo
        if gett_applicato:
            per_persona[uid]["gettoni_n"] += 1
            gettoni_tot += 1
            per_persona[uid][f"{fonte}_n"] += 1
            per_persona[uid][f"{fonte}_importo"] += imp
        elif uid in pset and imp < 0:
            per_persona[uid][f"{fonte}_importo"] += imp
        if in_gruppo:
            if fonte == "eolo":
                residuo = imp - (gettone * fatt if gett_applicato else 0)
                quota = residuo * float(cfg["eolo_fondo_pct"]) / 100
                fondo_lordo_eolo += quota
                fondo_per_entita[ent or "ditta"] += quota
            else:
                energia_gruppo += imp
        else:
            # negozi esterni / SRLS: trattenuta su EOLO (fatturato alla ditta) e su energia solo per terzi
            tr = imp * tratt_pct if (fonte == "eolo" or ent != "srls") else 0.0
            if fonte == "energia" and ent == "srls":
                tr = 0.0  # la SRLS incassa direttamente dal fornitore
            e = esterni[sid or p.get("negozio_nome", "?")]
            e[fonte] += imp
            e["n"] += 1
            e["righe"].append({"descrizione": p.get("descrizione", ""), "fonte": fonte, "importo": imp, "trattenuta": _r(tr), "netto": _r(imp - tr), "data": p.get("data_contratto", ""), "stato": p.get("stato")})

    fondo = max(0.0, fondo_lordo_eolo)
    tetto = float(cfg.get("tetto_fondo") or 0)
    fondo_eccedenza_tetto = 0.0
    if tetto and fondo > tetto:
        fondo_eccedenza_tetto, fondo = fondo - tetto, tetto

    att = await _attivita_mese(mese, pset, cfg)
    classifica = []
    for u in partecipanti:
        pp, a = per_persona[u], att[u]
        valore = (pp["eolo_importo"] * float(cfg["coef_eolo"]) / 100 + pp["energia_importo"] * float(cfg["coef_energia"]) / 100
                  + a["riparazioni_margine"] * float(cfg["coef_riparazione"]) / 100 + a["sim_nuova"] * float(cfg["valore_sim_nuova"])
                  + a["sim_mnp"] * float(cfg["valore_sim_mnp"]) + a["fisso"] * float(cfg["valore_fisso"]))
        classifica.append({**pp, **a, "valore": _r(valore), "contratti_eolo_energia": pp["eolo_n"] + pp["energia_n"],
                           "attivita_totali": pp["eolo_n"] + pp["energia_n"] + a["riparazioni_n"] + a["sim_nuova"] + a["sim_mnp"] + a["fisso"],
                           "gettoni_lordo": _r(pp["gettoni_n"] * gettone)})
    classifica.sort(key=lambda x: (-x["valore"], -x["contratti_eolo_energia"], -x["attivita_totali"], x["nome"]))
    premi_pct = list(cfg.get("premi_pct", []))
    i = 0
    while i < len(classifica):
        j = i
        while j + 1 < len(classifica) and (classifica[j + 1]["valore"], classifica[j + 1]["contratti_eolo_energia"], classifica[j + 1]["attivita_totali"]) == (classifica[i]["valore"], classifica[i]["contratti_eolo_energia"], classifica[i]["attivita_totali"]):
            j += 1
        pct_tot = sum(premi_pct[i:j + 1])
        for k in range(i, j + 1):
            classifica[k]["posizione"] = i + 1
            classifica[k]["premio_pct"] = _r(pct_tot / (j - i + 1))
            classifica[k]["premio_lordo"] = _r(fondo * pct_tot / 100 / (j - i + 1)) if classifica[k]["valore"] > 0 else 0.0
            classifica[k]["ex_aequo"] = j > i
        i = j + 1
    for c in classifica:
        c["totale_lordo"] = _r(c["gettoni_lordo"] + c["premio_lordo"])

    # Premio squadra: se il fondo del mese supera il miglior fondo dei 6 mesi precedenti, una % dell'eccedenza (presa dalla quota azienda EOLO, quindi autofinanziata) va in parti uguali a chi ha valore > 0
    bonus = {"attivo": float(cfg.get("bonus_squadra_pct") or 0) > 0, "pct": float(cfg.get("bonus_squadra_pct") or 0), "miglior_fondo_6m": 0.0, "mesi_confronto": [], "superato": False, "eccedenza": 0.0, "importo": 0.0, "per_persona": 0.0, "beneficiari": []}
    if bonus["attivo"] and not cfg.get("_no_bonus_ricorsione"):
        prec = sorted({p["mese"] async for p in db.incentivi_provvigioni.find({"mese": {"$lt": mese}, "fonte": "eolo"}, {"_id": 0, "mese": 1})})[-6:]
        fondi = []
        for m in prec:
            fondi.append((await calcola(m, {**cfg, "_no_bonus_ricorsione": True}))["fondo"]["fondo_disponibile"])
        bonus["mesi_confronto"] = [{"mese": m, "fondo": _r(f)} for m, f in zip(prec, fondi)]
        bonus["miglior_fondo_6m"] = _r(max(fondi) if fondi else 0)
        if fondi and fondo > max(fondi):
            quota_azienda_eccedenza = (fondo - max(fondi)) * (100 - float(cfg["eolo_fondo_pct"])) / max(float(cfg["eolo_fondo_pct"]), 1)
            bonus["superato"], bonus["eccedenza"] = True, _r(fondo - max(fondi))
            bonus["importo"] = _r(min(quota_azienda_eccedenza, bonus["eccedenza"]) * bonus["pct"] / 100)
            ben = [c for c in classifica if c["valore"] > 0]
            if ben and bonus["importo"] > 0:
                bonus["per_persona"] = _r(bonus["importo"] / len(ben))
                bonus["beneficiari"] = [c["nome"] for c in ben]
                for c in ben:
                    c["bonus_squadra"] = bonus["per_persona"]
                    c["totale_lordo"] = _r(c["totale_lordo"] + bonus["per_persona"])
    for c in classifica:
        c.setdefault("bonus_squadra", 0.0)
        c["costo_azienda"] = _r(c["totale_lordo"] * fatt)
        c["netto_stimato"] = _r(c["totale_lordo"] / 1.47)

    # entità di appartenenza della persona (dal negozio dell'utente)
    user_store = {u["id"]: (u.get("store_ids") or [""])[0] async for u in db.users.find({}, {"_id": 0, "id": 1, "store_ids": 1})}
    premi_per_entita = defaultdict(float)
    for c in classifica:
        c["negozio"] = stores.get(user_store.get(c["user_id"], ""), "—")
        c["entita"] = _entita_di(cfg, user_store.get(c["user_id"], ""), mese) or "ditta"
        premi_per_entita[c["entita"]] += c["totale_lordo"]

    premi_lordi = _r(sum(c["premio_lordo"] for c in classifica))
    bonus_lordi = _r(sum(c["bonus_squadra"] for c in classifica))
    gettoni_lordi = _r(gettoni_tot * gettone)
    costo_datore = _r((premi_lordi + gettoni_lordi + bonus_lordi) * fatt)
    eolo_gruppo = _r(sum(float(p.get("importo") or 0) for p in provv if p.get("fonte") == "eolo" and (p.get("store_id") in fondo_set or (not p.get("store_id") and p.get("negozio_nome") == "PADRE"))))
    trattenute_tot = _r(sum(r["trattenuta"] for e in esterni.values() for r in e["righe"]))

    comp = await db.incentivi_compensazioni.find({"mese": mese}, {"_id": 0}).to_list(2000)
    for c in comp:
        if c["store_id"] not in esterni and c["store_id"] not in fondo_set:
            esterni[c["store_id"]]  # negozio con sole compensazioni nel mese
    pag = {(p["store_id"], p["societa"]): p["pagato"] async for p in db.incentivi_pagamenti.find({"mese": mese}, {"_id": 0})}
    estratti = []
    for sid, e in esterni.items():
        ent = _entita_di(cfg, sid, mese) if sid in stores else ""
        dare_eolo = _r(sum(r["netto"] for r in e["righe"] if r["fonte"] == "eolo"))
        dare_energia = _r(sum(r["netto"] for r in e["righe"] if r["fonte"] == "energia" and ent != "srls"))
        avere = [c for c in comp if c["store_id"] == sid]
        avere_ditta = _r(sum(c["importo"] for c in avere if c["societa"] == "ditta"))
        avere_srls = _r(sum(c["importo"] for c in avere if c["societa"] == "srls"))
        estratti.append({"store_id": sid, "negozio": stores.get(sid, sid), "entita": ent or "terzo", "n_contratti": e["n"], "eolo_lordo": _r(e["eolo"]), "energia_lordo": _r(e["energia"]),
                         "dare_eolo": dare_eolo, "dare_energia": dare_energia,
                         "trattenuta": _r(sum(r["trattenuta"] for r in e["righe"])), "dare_ditta": _r(dare_eolo + dare_energia), "avere_ditta": avere_ditta, "avere_srls": avere_srls,
                         "saldo_ditta": _r(dare_eolo + dare_energia - avere_ditta), "saldo_srls": _r(-avere_srls), "compensazioni": avere, "righe": e["righe"],
                         "pagato_ditta": pag.get((sid, "ditta"), False), "pagato_srls": pag.get((sid, "srls"), False),
                         "nota": "Energia incassata direttamente dalla SRLS: fuori estratto conto" if ent == "srls" and e["energia"] else ""})
    estratti.sort(key=lambda x: -x["dare_ditta"])
    chiusura = await db.incentivi_chiusure.find_one({"mese": mese}, {"_id": 0, "approvato_da": 1, "at": 1})
    return {"mese": mese, "chiuso": bool(chiusura), "chiusura": chiusura,
            "fondo": {"eolo_gruppo_lordo": eolo_gruppo, "energia_gruppo_lordo": _r(energia_gruppo), "fondo_pct": cfg["eolo_fondo_pct"], "fondo_disponibile": _r(fondo),
                      "fondo_oltre_tetto": _r(fondo_eccedenza_tetto), "premi_assegnati": premi_lordi, "residuo": _r(fondo - premi_lordi), "per_entita": {k: _r(v) for k, v in fondo_per_entita.items()}},
            "costi": {"gettoni_n": gettoni_tot, "gettoni_lordi": gettoni_lordi, "premi_lordi": premi_lordi, "bonus_squadra_lordi": bonus_lordi, "costo_datore_totale": costo_datore,
                      "fattore_costo_datore": fatt, "trattenute_esterni": trattenute_tot,
                      "risultato_azienda": _r(eolo_gruppo + energia_gruppo + trattenute_tot - costo_datore), "premi_per_entita": {k: _r(v) for k, v in premi_per_entita.items()}},
            "classifica": classifica, "bonus_squadra": bonus, "estratti_conto": estratti, "anomalie": anomalie, "n_provvigioni": len(provv),
            "parametri": {k: cfg.get(k) for k in ("gettone_lordo", "eolo_fondo_pct", "trattenuta_terzi_pct", "premi_pct", "coef_eolo", "coef_energia", "coef_riparazione", "valore_sim_nuova", "valore_sim_mnp", "valore_fisso", "tetto_fondo", "costo_datore_fattore", "energia_lavorazione")}}


@router.get("/calcolo")
async def get_calcolo(mese: str, request: Request, override: str = ""):
    """Calcolo del mese. `override` (JSON) sovrascrive i parametri solo per questa chiamata: è la simulazione, nulla viene salvato."""
    await _admin(request)
    cfg = await get_config()
    if override:
        try:
            ov = json.loads(override)
            assert isinstance(ov, dict)
            cfg = {**cfg, **ov}
            for k in ("gettone_lordo", "eolo_fondo_pct", "costo_datore_fattore", "trattenuta_terzi_pct", "coef_eolo", "coef_energia", "coef_riparazione", "valore_sim_nuova", "valore_sim_mnp", "valore_fisso", "tetto_fondo"):
                cfg[k] = float(cfg.get(k) or 0)
            cfg["premi_pct"] = [float(x) for x in cfg.get("premi_pct", [])]
        except Exception:
            raise HTTPException(status_code=400, detail="Override non valido")
    return await calcola(mese, cfg)


@router.get("/storico")
async def storico(request: Request):
    await _admin(request)
    db = _d["db"]
    mesi = sorted({p["mese"] async for p in db.incentivi_provvigioni.find({}, {"_id": 0, "mese": 1})})
    chiusi = {c["mese"]: c async for c in db.incentivi_chiusure.find({}, {"_id": 0, "mese": 1, "approvato_da": 1, "at": 1, "fondo": 1, "premi": 1})}
    cfg = await get_config()
    out = []
    for m in mesi:
        if m in chiusi:
            out.append({"mese": m, "chiuso": True, **{k: chiusi[m].get(k) for k in ("approvato_da", "at", "fondo", "premi")}})
        else:
            c = await calcola(m, cfg)
            out.append({"mese": m, "chiuso": False, "fondo": c["fondo"]["fondo_disponibile"], "premi": c["fondo"]["premi_assegnati"]})
    return out


@router.post("/chiusura/{mese}")
async def chiudi(mese: str, request: Request):
    user = await _admin(request)
    db = _d["db"]
    if await db.incentivi_chiusure.find_one({"mese": mese}):
        raise HTTPException(status_code=400, detail="Mese già chiuso")
    c = await calcola(mese, await get_config())
    await db.incentivi_chiusure.insert_one({"id": str(uuid.uuid4()), "mese": mese, "approvato_da": user["name"], "at": _now(), "fondo": c["fondo"]["fondo_disponibile"],
                                            "premi": c["fondo"]["premi_assegnati"], "snapshot": c})
    return {"ok": True}


@router.delete("/chiusura/{mese}")
async def riapri(mese: str, request: Request):
    await _admin(request)
    await _d["db"].incentivi_chiusure.delete_one({"mese": mese})
    return {"ok": True}


@router.get("/chiusura/{mese}")
async def get_chiusura(mese: str, request: Request):
    await _admin(request)
    c = await _d["db"].incentivi_chiusure.find_one({"mese": mese}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Mese non chiuso")
    return c


# ---------------- Area dipendente ----------------
@router.get("/mio")
async def mio(mese: str, request: Request):
    user = await _user(request)
    cfg = await get_config()
    if not cfg.get("online") and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Incentivi non ancora attivi")
    if cfg.get("mese_partenza") and mese < cfg["mese_partenza"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail=f"La gara parte da {cfg['mese_partenza']}")
    if user["id"] not in cfg.get("partecipanti", []) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Non partecipi alla gara")
    c = await calcola(mese, cfg)
    cl = [{"posizione": x["posizione"], "nome": x["nome"], "negozio": x["negozio"], "ex_aequo": x["ex_aequo"], "io": x["user_id"] == user["id"]} for x in c["classifica"]]
    me = next((x for x in c["classifica"] if x["user_id"] == user["id"]), None)
    return {"mese": mese, "online": cfg.get("online"), "chiuso": c["chiuso"], "classifica": cl,
            "mio": {k: me[k] for k in ("posizione", "valore", "eolo_n", "energia_n", "riparazioni_n", "riparazioni_margine", "sim_nuova", "sim_mnp", "fisso", "gettoni_n", "gettoni_lordo", "premio_lordo", "premio_pct", "totale_lordo")} if me else None}


# ---------------- Spese nel PDP (quote girate pagate) ----------------
async def spese_pdp(centro: dict, anno: int, mese: int) -> dict:
    """Quote pagate ai negozi esterni nel mese: EOLO → centro della ditta (Morbegno/Gravedona), energia CambiaOra → centro della SRLS (Sondrio)."""
    m = f"{anno:04d}-{mese:02d}"
    if not await _d["db"].incentivi_pagamenti.find_one({"mese": m, "societa": "ditta", "pagato": True}):
        return {}
    cfg = await get_config()
    ent_centro = {_entita_di(cfg, sid, m) for sid in centro["store_ids"]}
    c = await calcola(m, cfg)
    out = {}
    for e in c["estratti_conto"]:
        if not e["pagato_ditta"]:
            continue
        if "ditta" in ent_centro and e["dare_eolo"]:
            out["Compensi EOLO negozi esterni (pagati)"] = _r(out.get("Compensi EOLO negozi esterni (pagati)", 0) + e["dare_eolo"])
        if "srls" in ent_centro and e["dare_energia"]:
            out["Compensi CambiaOra negozi esterni (pagati)"] = _r(out.get("Compensi CambiaOra negozi esterni (pagati)", 0) + e["dare_energia"])
    return out


# ---------------- Regolamento PDF ----------------
def _build_regolamento(cfg: dict, users: dict, stores: dict, firme: Optional[dict] = None) -> bytes:
    from fpdf import FPDF

    def t(s):
        return str(s).replace("€", "EUR").replace("–", "-").replace("—", "-").replace("→", "->").replace("×", "x").replace("≈", "~").encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF(format="A4", unit="mm"); pdf.set_auto_page_break(auto=True, margin=10); pdf.set_margins(12, 10, 12); pdf.add_page()
    pdf.set_font("helvetica", "B", 15); pdf.cell(0, 8, t("Regolamento Incentivi RS"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8); pdf.cell(0, 5, t(f"Versione regole del {cfg.get('updated_at', '')[:10]} - documento generato il {datetime.now(timezone.utc).date().isoformat()}"), new_x="LMARGIN", new_y="NEXT"); pdf.ln(2)

    def sez(titolo, righe):
        pdf.set_font("helvetica", "B", 11); pdf.cell(0, 7, t(titolo), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 9)
        for r in righe:
            pdf.multi_cell(0, 4.6, t("- " + r), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    for titolo, righe in regole_testo(cfg, users, stores):
        sez(titolo, righe)
    pdf.ln(4); pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, t("Luogo e data: ______________________________"), new_x="LMARGIN", new_y="NEXT"); pdf.ln(2)
    pdf.cell(95, 6, t("L'azienda"), new_x="RIGHT"); pdf.cell(95, 6, t("Il dipendente (per presa visione e accettazione)"), new_x="LMARGIN", new_y="NEXT"); pdf.ln(6)
    for u in cfg.get("partecipanti", []):
        f = (firme or {}).get(u)
        y = pdf.get_y()
        pdf.cell(95, 6, t("______________________________"), new_x="RIGHT")
        if f and f.get("firma_png"):
            try:
                pdf.image(io.BytesIO(base64.b64decode(f["firma_png"].split(",")[-1])), x=pdf.get_x() + 40, y=y - 5, h=9)
            except Exception:
                pass
            pdf.cell(95, 6, t(f"{users.get(u, u)}: firmato digitalmente il {f.get('firmato_at', '')[:16].replace('T', ' ')}"), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(95, 6, t(f"{users.get(u, u)}: ______________________________"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
    return bytes(pdf.output())


def regole_testo(cfg: dict, users: dict, stores: dict) -> list:
    premi = cfg.get("premi_pct", [])
    return [
        ("1. Partecipanti", [", ".join(users.get(u, u) for u in cfg.get("partecipanti", [])), "Negozi che alimentano il fondo: " + ", ".join(stores.get(s, s) for s in cfg.get("negozi_fondo", []))]),
        ("2. Gettone per contratto", [f"Per ogni contratto EOLO o luce/gas (CambiaOra/ENEL) confermato dal fornitore e attribuito al venditore: {cfg['gettone_lordo']:.2f} EUR lordi in busta paga.",
                                      "Il gettone matura nel mese in cui il fornitore conferma la provvigione (fattura), non alla firma del contratto.",
                                      "Contratti annullati, respinti o stornati dal fornitore non generano gettone; gli storni successivi vengono compensati sul mese seguente."]),
        ("3. Fondo premi", [f"Il fondo e' alimentato esclusivamente dalle provvigioni EOLO confermate dei negozi indicati: {cfg['eolo_fondo_pct']:.0f}% della provvigione residua dopo il costo del gettone.",
                            "Le provvigioni luce/gas coprono il gettone e restano all'azienda. SIM, riparazioni, vendite e negozi esterni non alimentano il fondo.",
                            "Il fondo non puo' essere negativo e viene distribuito solo se effettivamente incassato." + (f" Tetto mensile: {cfg['tetto_fondo']:.2f} EUR." if cfg.get("tetto_fondo") else "")]),
        ("4. Classifica mensile", ["Il punteggio e' il valore generato nel mese, con questi pesi:",
                                   f"EOLO: {cfg['coef_eolo']:.0f}% della provvigione confermata; luce/gas: {cfg['coef_energia']:.0f}% della provvigione confermata;",
                                   f"riparazioni lavorate (pronte/consegnate): {cfg['coef_riparazione']:.0f}% del margine (prezzo - ricambio); SIM nuova {cfg['valore_sim_nuova']:.2f} EUR, SIM MNP {cfg['valore_sim_mnp']:.2f} EUR, fisso/internet non EOLO {cfg['valore_fisso']:.2f} EUR (valori figurativi).",
                                   "Spareggio: piu' contratti EOLO+energia, poi piu' attivita' totali, infine premio diviso in parti uguali."]),
        ("5. Premi", ["Il fondo del mese e' ripartito tra i primi classificati: " + ", ".join(f"{i + 1}o {p:.0f}%" for i, p in enumerate(premi)) + ".",
                      "Un partecipante con valore zero nel mese non riceve premio. I premi sono importi lordi erogati in busta paga, soggetti a tassazione e contributi di legge.",
                      "Nessun premio e' dovuto finche' l'amministrazione non chiude il mese e conferma gli importi."]
         + ([f"Premio squadra: se il fondo del mese supera il miglior fondo dei 6 mesi precedenti, il {cfg['bonus_squadra_pct']:.0f}% dell'eccedenza (presa dalla quota azienda, mai dal fondo) viene diviso in parti uguali tra tutti i partecipanti con valore maggiore di zero."] if float(cfg.get("bonus_squadra_pct") or 0) > 0 else [])),
        ("6. Trasparenza", ["Ogni partecipante vede la propria posizione, i propri numeri e il proprio premio stimato nell'area 'I miei incentivi'; la classifica e' visibile a tutti, gli importi solo a chi li riceve.",
                            "Le regole possono essere modificate dall'amministrazione con preavviso; ogni modifica e' registrata con data e valori precedenti.",
                            "Il presente regolamento integra e non sostituisce il contratto di lavoro; le garanzie retributive esistenti restano invariate."]),
    ]


async def _nomi() -> tuple:
    db = _d["db"]
    users = {u["id"]: u["name"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    return users, stores


@router.get("/regolamento.pdf")
async def regolamento_pdf(request: Request):
    from fastapi.responses import Response
    await _admin(request)
    cfg = await get_config()
    users, stores = await _nomi()
    firme = {f["user_id"]: f async for f in _d["db"].incentivi_firme.find({"stato": "firmata", "versione": cfg.get("updated_at", "")}, {"_id": 0})}
    await _d["db"].incentivi_config.update_one({"id": CONFIG_ID}, {"$set": {"regolamento_generato_at": _now()}})
    return Response(content=_build_regolamento(cfg, users, stores, firme), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="regolamento_incentivi_rs.pdf"'})


# ---------------- Firma digitale regolamento ----------------
@router.post("/firme/invia")
async def firme_invia(request: Request):
    """Crea (o riusa) un link di firma per ogni partecipante e lo manda su WhatsApp. Una firma vale per la versione regole corrente."""
    user = await _admin(request)
    db = _d["db"]
    cfg = await get_config()
    versione = cfg.get("updated_at", "")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    inviati, senza_tel = 0, []
    for uid in cfg.get("partecipanti", []):
        u = await db.users.find_one({"id": uid}, {"_id": 0, "name": 1, "telefono": 1})
        if not u:
            continue
        f = await db.incentivi_firme.find_one({"user_id": uid, "versione": versione}, {"_id": 0})
        if not f:
            f = {"id": str(uuid.uuid4()), "user_id": uid, "nome": u["name"], "token": uuid.uuid4().hex, "versione": versione, "stato": "inviata", "created_at": _now(), "created_by": user["name"]}
            await db.incentivi_firme.insert_one(dict(f))
        if f["stato"] == "firmata":
            continue
        if not (u.get("telefono") or "").strip():
            senza_tel.append(u["name"])
            continue
        await _d["wa_send"](u["telefono"], f"Ciao {u['name']}, ecco il regolamento Incentivi RS da leggere e firmare col dito dal telefono:\n{base}/firma-regolamento/{f['token']}\nLa firma vale come presa visione e accettazione.", session="default", tipo="incentivi_firma")
        await db.incentivi_firme.update_one({"id": f["id"]}, {"$set": {"inviata_at": _now()}})
        inviati += 1
    return {"inviati": inviati, "senza_telefono": senza_tel}


@router.get("/firme")
async def firme_stato(request: Request):
    await _admin(request)
    cfg = await get_config()
    users, _ = await _nomi()
    firme = {f["user_id"]: f async for f in _d["db"].incentivi_firme.find({"versione": cfg.get("updated_at", "")}, {"_id": 0, "firma_png": 0})}
    return [{"user_id": u, "nome": users.get(u, u), **{k: firme.get(u, {}).get(k) for k in ("stato", "inviata_at", "firmato_at", "token")}} for u in cfg.get("partecipanti", [])]


@router.get("/public/firma-regolamento/{token}")
async def public_firma_info(token: str):
    f = await _d["db"].incentivi_firme.find_one({"token": token}, {"_id": 0, "firma_png": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Link non valido")
    cfg = await get_config()
    users, stores = await _nomi()
    return {"nome": f["nome"], "stato": f["stato"], "firmato_at": f.get("firmato_at"), "versione_attuale": f["versione"] == cfg.get("updated_at", ""),
            "regole": [{"titolo": tt, "righe": rr} for tt, rr in regole_testo(cfg, users, stores)]}


class FirmaRegolamentoInput(BaseModel):
    firma_png: str


@router.post("/public/firma-regolamento/{token}")
async def public_firma_salva(token: str, body: FirmaRegolamentoInput):
    db = _d["db"]
    f = await db.incentivi_firme.find_one({"token": token}, {"_id": 0, "id": 1, "stato": 1, "versione": 1, "nome": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Link non valido")
    if f["stato"] == "firmata":
        return {"ok": True, "gia_firmata": True}
    if (await get_config()).get("updated_at", "") != f["versione"]:
        raise HTTPException(status_code=400, detail="Le regole sono cambiate dopo l'invio: chiedi un nuovo link")
    if not body.firma_png.startswith("data:image/png;base64,") or len(body.firma_png) > 400_000:
        raise HTTPException(status_code=400, detail="Firma non valida")
    await db.incentivi_firme.update_one({"id": f["id"]}, {"$set": {"stato": "firmata", "firma_png": body.firma_png, "firmato_at": _now()}})
    return {"ok": True}


# ---------------- Fattura intercompany SRLS -> ditta ----------------
async def intercompany_righe(mese: str, cfg: dict) -> list:
    """Contratti energia di negozi SRLS (cliente di Sondrio) la cui pratica e' stata inserita da personale della ditta individuale: quota lavorazione."""
    db = _d["db"]
    stores_srls = {e["store_id"] for e in cfg.get("entita", []) if e["entita"] == "srls"}
    stores_ditta = {e["store_id"] for e in cfg.get("entita", []) if e["entita"] == "ditta"}
    users = {u["id"]: u async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "store_ids": 1, "role": 1})}
    out = []
    async for c in db.clients.find({"venditore_id": {"$in": list(stores_srls | stores_ditta)}, "lavorazione": {"$in": ["cambio_effettuato", "rinnovato"]}, "anonimizzato_at": {"$in": [None]}}, {"_id": 0}):
        if _ym(c.get("data_contratto") or c.get("updated_at")) != mese:
            continue
        uid = c.get("operatore_id") or c.get("created_by") or ""
        u = users.get(uid)
        base = {"data": (c.get("data_contratto") or "")[:10], "cliente": f"{c.get('cognome', '')} {c.get('nome', '')}".strip(), "tipo": c.get("tipo_bolletta") or "", "gestione": (c.get("gestione") or "cambiaora").upper(), "lavorato_da": u["name"] if u else "—"}
        if c.get("venditore_id") in stores_ditta:
            out.append({**base, "motivo": "contratto negozio ditta", "quota": float(cfg["energia_importo"])})
            continue
        if not u:
            continue
        u_stores = set(u.get("store_ids") or [])
        if u["role"] == "operatore" or (u_stores & stores_ditta and not (u_stores & stores_srls)):
            out.append({**base, "motivo": "pratica lavorata per la SRLS", "quota": float(cfg["energia_lavorazione"])})
    return out


@router.get("/intercompany")
async def intercompany(mese: str, request: Request):
    await _admin(request)
    cfg = await get_config()
    righe = await intercompany_righe(mese, cfg)
    return {"mese": mese, "righe": righe, "totale": _r(sum(r["quota"] for r in righe)), "quota": cfg["energia_lavorazione"]}


@router.get("/intercompany.pdf")
async def intercompany_pdf(mese: str, request: Request):
    from fpdf import FPDF
    from fastapi.responses import Response
    await _admin(request)
    cfg = await get_config()
    righe = await intercompany_righe(mese, cfg)

    def t(s):
        return str(s).replace("€", "EUR").replace("–", "-").encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF(format="A4", unit="mm"); pdf.set_auto_page_break(auto=True, margin=12); pdf.add_page()
    pdf.set_font("helvetica", "B", 14); pdf.cell(0, 8, t(f"Riepilogo quote lavorazione CambiaOra - {mese}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 5, t("Da: RS Riparazioni SRLS (negozio Sondrio, incassa la provvigione CambiaOra/ENEL: 50 EUR a contratto)\nA: Enrico Mangani ditta individuale (negozi Morbegno / Gravedona)\n"
                           f"Quote: {cfg['energia_importo']:.2f} EUR per ogni contratto dei negozi della ditta; {cfg['energia_lavorazione']:.2f} EUR per ogni pratica di Sondrio lavorata da personale della ditta. Documento di supporto alla fattura intercompany: verificare con il commercialista."), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3); pdf.set_font("helvetica", "B", 9)
    for w, h in ((20, "Data"), (50, "Cliente"), (14, "Tipo"), (20, "Gestione"), (28, "Lavorato da"), (36, "Motivo"), (18, "Quota")):
        pdf.cell(w, 6, t(h), border=1)
    pdf.ln(); pdf.set_font("helvetica", "", 8)
    for r in righe:
        for w, v in ((20, r["data"]), (50, r["cliente"][:30]), (14, r["tipo"]), (20, r["gestione"]), (28, r["lavorato_da"][:16]), (36, r["motivo"]), (18, f"{r['quota']:.2f}")):
            pdf.cell(w, 6, t(v), border=1)
        pdf.ln()
    if not righe:
        pdf.cell(0, 6, t("Nessun contratto nel mese."), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "B", 10); pdf.ln(2)
    pdf.cell(0, 7, t(f"Totale: {len(righe)} contratti = {sum(r['quota'] for r in righe):.2f} EUR"), new_x="LMARGIN", new_y="NEXT")
    return Response(content=bytes(pdf.output()), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="intercompany_{mese}.pdf"'})


# ---------------- Avviso WhatsApp settimanale ----------------
def _barra(pct: float) -> str:
    n = max(0, min(10, round(pct / 10)))
    return "█" * n + "░" * (10 - n)


async def invia_classifica_whatsapp() -> dict:
    db = _d["db"]
    cfg = await get_config()
    if not cfg.get("online"):
        return {"inviati": 0, "motivo": "incentivi non online"}
    oggi = datetime.now(timezone.utc)
    mese = f"{oggi.year:04d}-{oggi.month:02d}"
    c = await calcola(mese, cfg)
    storico = [(await calcola(m, cfg))["fondo"]["fondo_disponibile"] for m in sorted({p["mese"] async for p in db.incentivi_provvigioni.find({"mese": {"$lt": mese}}, {"_id": 0, "mese": 1})})[-6:]]
    rif = max(storico) if storico else 0
    fondo = c["fondo"]["fondo_disponibile"]
    pct = (fondo / rif * 100) if rif else (100 if fondo else 0)
    inviati = 0
    for x in c["classifica"]:
        u = await db.users.find_one({"id": x["user_id"]}, {"_id": 0, "telefono": 1, "name": 1})
        if not u or not u.get("telefono"):
            continue
        testo = (f"🏆 *Incentivi RS – {mese}*\nCiao {u['name']}, sei *{x['posizione']}º* in classifica con valore {x['valore']:.0f}.\n"
                 f"EOLO {x['eolo_n']} · energia {x['energia_n']} · riparazioni {x['riparazioni_n']} · SIM {x['sim_nuova'] + x['sim_mnp']}\n"
                 f"Gettoni maturati: {x['gettoni_n']} ({x['gettoni_lordo']:.2f} € lordi) · premio stimato {x['premio_lordo']:.2f} € lordi\n"
                 f"Fondo premi: {_barra(pct)} {fondo:.0f} €" + (f" (miglior mese {rif:.0f} €)" if rif else "") + "\n"
                 "Classifica: " + " · ".join(f"{y['posizione']}. {y['nome']}" for y in c["classifica"]) + "\n_Stima: diventa definitiva con la chiusura del mese._")
        await _d["wa_send"](u["telefono"], testo, session="default", tipo="incentivi_classifica")
        inviati += 1
    return {"inviati": inviati, "mese": mese}


@router.post("/cron/classifica")
async def cron_classifica(request: Request):
    _check_cron(request)
    import asyncio
    asyncio.create_task(invia_classifica_whatsapp())
    return {"status": "accepted"}


def _check_cron(request: Request):
    import hmac
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not token or not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def riepilogo_fine_mese() -> dict:
    """Il 1º del mese: all'amministrazione fondo, classifica finale e premi da confermare del mese appena chiuso."""
    oggi = datetime.now(timezone.utc)
    anno, mese_n = (oggi.year, oggi.month - 1) if oggi.month > 1 else (oggi.year - 1, 12)
    mese = f"{anno:04d}-{mese_n:02d}"
    cfg = await get_config()
    c = await calcola(mese, cfg)
    f, k = c["fondo"], c["costi"]
    righe = "\n".join(f"{x['posizione']}. {x['nome']} – valore {x['valore']:.0f} · gettoni {x['gettoni_n']} ({x['gettoni_lordo']:.2f} €) · premio {x['premio_lordo']:.2f} € → tot {x['totale_lordo']:.2f} € lordi" for x in c["classifica"])
    testo = (f"📊 *Incentivi RS – riepilogo {mese}*\n"
             f"EOLO gruppo {f['eolo_gruppo_lordo']:.2f} € · energia {f['energia_gruppo_lordo']:.2f} €\n"
             f"Fondo {f['fondo_disponibile']:.2f} € · premi {f['premi_assegnati']:.2f} € · gettoni {k['gettoni_n']} ({k['gettoni_lordi']:.2f} €)\n"
             f"Costo datore stimato {k['costo_datore_totale']:.2f} € · risultato azienda {k['risultato_azienda']:.2f} €\n\n{righe}\n\n"
             + ("✅ Mese già chiuso." if c["chiuso"] else "⚠️ Da confermare: Incentivi RS → Fondo & classifica → *Chiudi mese*.")
             + (f"\n⚠️ {len(c['anomalie'])} anomalie da verificare." if c["anomalie"] else "")
             + f"\nℹ️ Provvigioni caricate: {c['n_provvigioni']}. Ricorda: le gare EOLO si liquidano a 90 giorni (quelle di {mese} arrivano fra 3 mesi).")
    await _d["wa_send"](_d["numero_amministrazione"], testo, session="default", tipo="incentivi_riepilogo")
    return {"mese": mese, "inviato": True}


@router.post("/cron/riepilogo-mese")
async def cron_riepilogo(request: Request):
    _check_cron(request)
    import asyncio
    asyncio.create_task(riepilogo_fine_mese())
    return {"status": "accepted"}


@router.post("/invia-riepilogo")
async def invia_riepilogo_manuale(request: Request):
    await _admin(request)
    return await riepilogo_fine_mese()


async def sollecita_firme() -> dict:
    """Rimanda il link di firma a chi non ha firmato dopo 3 giorni (max 3 solleciti, uno ogni 3 giorni)."""
    db = _d["db"]
    cfg = await get_config()
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    limite = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=3)).isoformat()
    n = 0
    async for f in db.incentivi_firme.find({"stato": "inviata", "versione": cfg.get("updated_at", ""), "inviata_at": {"$lte": limite}, "solleciti": {"$not": {"$gte": 3}}}, {"_id": 0}):
        u = await db.users.find_one({"id": f["user_id"]}, {"_id": 0, "name": 1, "telefono": 1})
        if not u or not (u.get("telefono") or "").strip():
            continue
        await _d["wa_send"](u["telefono"], f"Ciao {u['name']}, promemoria: il regolamento Incentivi RS è ancora da firmare. Bastano 2 minuti dal telefono:\n{base}/firma-regolamento/{f['token']}", session="default", tipo="incentivi_firma_sollecito")
        await db.incentivi_firme.update_one({"id": f["id"]}, {"$set": {"inviata_at": _now()}, "$inc": {"solleciti": 1}})
        n += 1
    return {"solleciti": n}


@router.post("/cron/sollecito-firme")
async def cron_sollecito(request: Request):
    _check_cron(request)
    import asyncio
    asyncio.create_task(sollecita_firme())
    return {"status": "accepted"}


@router.post("/invia-classifica")
async def invia_classifica_manuale(request: Request):
    await _admin(request)
    return await invia_classifica_whatsapp()


# ---------------- Export ----------------
@router.get("/export")
async def export_excel(mese: str, request: Request):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    await _admin(request)
    c = await calcola(mese, await get_config())
    wb = Workbook(); wb.remove(wb.active)

    def sheet(nome, header, rows):
        ws = wb.create_sheet(nome); ws.append(header)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for r in rows:
            ws.append(r)
        ws.column_dimensions["A"].width = 28
        return ws

    f, k = c["fondo"], c["costi"]
    sheet("Fondo", ["Voce", "Importo €"], [["EOLO gruppo lordo", f["eolo_gruppo_lordo"]], ["Energia gruppo lordo", f["energia_gruppo_lordo"]], ["% EOLO al fondo", f["fondo_pct"]],
                                            ["Fondo disponibile", f["fondo_disponibile"]], ["Premi assegnati", f["premi_assegnati"]], ["Residuo", f["residuo"]],
                                            ["Gettoni n.", k["gettoni_n"]], ["Gettoni lordi", k["gettoni_lordi"]], ["Costo datore totale", k["costo_datore_totale"]],
                                            ["Trattenute esterni", k["trattenute_esterni"]], ["Risultato azienda", k["risultato_azienda"]]])
    sheet("Classifica", ["Pos", "Persona", "Negozio", "Entità", "Valore", "EOLO n", "EOLO €", "Energia n", "Energia €", "Riparazioni n", "Margine rip.", "SIM nuove", "SIM MNP", "Fisso", "Gettoni n", "Gettoni €", "Premio %", "Premio €", "Totale lordo", "Costo azienda"],
          [[x["posizione"], x["nome"], x["negozio"], x["entita"], x["valore"], x["eolo_n"], _r(x["eolo_importo"]), x["energia_n"], _r(x["energia_importo"]), x["riparazioni_n"], _r(x["riparazioni_margine"]),
            x["sim_nuova"], x["sim_mnp"], x["fisso"], x["gettoni_n"], x["gettoni_lordo"], x["premio_pct"], x["premio_lordo"], x["totale_lordo"], x["costo_azienda"]] for x in c["classifica"]])
    sheet("Estratti conto", ["Negozio", "Entità", "Contratti", "EOLO lordo", "Energia lordo", "Trattenuta", "Dare ditta", "Avere ditta", "Avere SRLS", "Saldo ditta", "Saldo SRLS", "Pagato ditta", "Pagato SRLS"],
          [[e["negozio"], e["entita"], e["n_contratti"], e["eolo_lordo"], e["energia_lordo"], e["trattenuta"], e["dare_ditta"], e["avere_ditta"], e["avere_srls"], e["saldo_ditta"], e["saldo_srls"], e["pagato_ditta"], e["pagato_srls"]] for e in c["estratti_conto"]])
    provv = await _d["db"].incentivi_provvigioni.find({"mese": mese}, {"_id": 0}).to_list(10000)
    stores = {s["id"]: s["nome"] async for s in _d["db"].stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["id"]: u["name"] async for u in _d["db"].users.find({}, {"_id": 0, "id": 1, "name": 1})}
    sheet("Provvigioni", ["Fonte", "Negozio", "Persona", "Data contratto", "Descrizione", "Sezione", "Stato", "Origine", "Importo"],
          [[p.get("fonte"), stores.get(p.get("store_id"), p.get("negozio_nome", "—")), users.get(p.get("user_id"), "—"), p.get("data_contratto", ""), p.get("descrizione", ""), p.get("sezione", ""), p.get("stato"), p.get("origine"), p.get("importo")] for p in provv])
    sheet("Anomalie", ["Tipo", "Descrizione", "Importo"], [[a["tipo"], a["descrizione"], a["importo"]] for a in c["anomalie"]])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="incentivi_{mese}.xlsx"'})
