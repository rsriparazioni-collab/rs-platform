import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request

load_dotenv()
router = APIRouter(prefix="/contabilita/pdp/analisi")
_d: dict = {}

SYSTEM = (
    "Sei un consulente di direzione e fiscale per piccole imprese italiane del retail (negozi di riparazione smartphone, telefonia, energia, "
    "spedizioni). Analizzi il punto di pareggio mensile di un centro di costo e la sua storia. Rispondi SEMPRE in italiano, in Markdown, "
    "con numeri concreti in euro presi dai dati forniti. Struttura: 1) Fotografia del mese (2-3 righe), 2) Cosa è cambiato rispetto ai mesi "
    "precedenti (trend entrate, spese, fornitori), 3) Tre azioni strategiche prioritarie e misurabili (cosa, quanto vale in euro/mese, come), "
    "4) Ottimizzazione fiscale (IVA su fatture emesse/ricevute, deducibilità costi, timing acquisti, regime, ammortamenti, compensi): "
    "spunti generali da verificare col commercialista, 5) Obiettivo per il prossimo mese (una cifra di pareggio e di guadagno). "
    "Sii diretto, pratico, massimo 450 parole. Non inventare dati assenti: se un dato manca dillo."
)


def setup(**deps):
    _d.update(deps)


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _eur(v) -> str:
    return f"{float(v or 0):,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")


async def _dati(centro: dict, anno: int, mese: int) -> str:
    calc = _d["pdp_calcolo"]
    cur = await calc(centro, anno, mese)
    righe = [f"CENTRO DI COSTO: {centro['nome']} ({', '.join(centro['negozi'])}) - MESE ANALIZZATO: {mese:02d}/{anno}", "",
             "ENTRATE DEL MESE:"] + [f"- {k}: {_eur(v)}" for k, v in cur["entrate"].items() if v] + [f"TOTALE ENTRATE: {_eur(cur['tot_entrate'])}", ""]
    for cat, label in (("spese_fisse", "SPESE FISSE"), ("spese_semifisse", "SPESE SEMI-FISSE"), ("fornitori", "FORNITORI / ACQUISTI")):
        righe.append(f"{label} (totale {_eur(cur['tot_spese'][cat])}):")
        righe += [f"- {k}: {_eur(v)}" for k, v in cur["sezioni"][cat].items() if v]
        righe.append("")
    righe += [f"PUNTO DI PAREGGIO (uscite totali): {_eur(cur['tot_uscite'])}", f"RISULTATO MESE: {_eur(cur['risultato'])} (copertura {cur['copertura_pct']}%)",
              f"Fatture emesse AdE: {_eur(cur['ade']['emesse'])} ({cur['ade']['n_emesse']} doc) - Fatture ricevute AdE: {_eur(cur['ade']['ricevute'])} ({cur['ade']['n_ricevute']} doc)"]
    if cur["ade_non_abbinate"]:
        righe.append("Fornitori da fatture ricevute non abbinati a voci PDP: " + "; ".join(f"{x['controparte']} {_eur(x['totale'])}" for x in cur["ade_non_abbinate"][:15]))
    righe += ["", "STORICO MESI PRECEDENTI (compilati):"]
    a, m = anno, mese
    trovati = 0
    for _ in range(12):
        m -= 1
        if m == 0:
            a, m = a - 1, 12
        p = await calc(centro, a, m)
        if p["compilato"]:
            trovati += 1
            righe.append(f"- {m:02d}/{a}: entrate {_eur(p['tot_entrate'])}, uscite {_eur(p['tot_uscite'])}, risultato {_eur(p['risultato'])}, fisse {_eur(p['tot_spese']['spese_fisse'])}, fornitori {_eur(p['tot_spese']['fornitori'])}")
    if not trovati:
        righe.append("- nessun mese precedente compilato")
    righe += ["", "FATTURATO MENSILE PER NEGOZIO (anno corrente vs precedente, da corrispettivi/storico):"]
    for sid in centro["store_ids"]:
        store = await _d["db"].stores.find_one({"id": sid}, {"_id": 0, "id": 1, "nome": 1})
        for mm in range(1, 13):
            c = await _d["fatturato_mese"](store, anno, mm)
            ap = await _d["fatturato_mese"](store, anno - 1, mm)
            tc, ta = c["enel"] + c["altro"], ap["enel"] + ap["altro"]
            if tc or ta:
                righe.append(f"- {store['nome']} {mm:02d}: {anno} {_eur(tc)} | {anno - 1} {_eur(ta)}")
    return "\n".join(righe)


@router.get("")
async def get_analisi(centro_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    await _d["centro"](user, centro_id)
    doc = await _d["db"].pdp_analisi.find_one({"centro_id": centro_id, "anno": anno, "mese": mese}, {"_id": 0})
    return doc or {"testo": None}


@router.post("")
async def genera_analisi(centro_id: str, anno: int, mese: int, request: Request):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    user = await _user(request)
    centro = await _d["centro"](user, centro_id)
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY mancante")
    dati = await _dati(centro, anno, mese)
    chat = LlmChat(api_key=key, session_id=f"pdp-{centro_id}-{anno}-{mese}-{uuid.uuid4().hex[:6]}", system_message=SYSTEM).with_model("openai", "gpt-5.4")
    try:
        testo = await chat.send_message(UserMessage(text=f"Analizza questi dati e proponi la strategia migliorativa.\n\n{dati}"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Analisi non disponibile: {e}")
    doc = {"centro_id": centro_id, "anno": anno, "mese": mese, "testo": str(testo), "dati": dati, "modello": "gpt-5.4",
           "generato_da": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()}
    await _d["db"].pdp_analisi.update_one({"centro_id": centro_id, "anno": anno, "mese": mese}, {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    doc.pop("dati", None)
    return doc
