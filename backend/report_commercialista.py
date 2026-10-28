import re
import uuid
from datetime import datetime, timezone, date
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/report-commercialista")
_d: dict = {}
MESI_IT = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def require_admin(user: dict = Depends(_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


def _eur(v) -> str:
    return f"€ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def _cfg() -> dict:
    doc = await _d["db"].settings.find_one({"key": "commercialisti_cfg"}, {"_id": 0})
    return (doc or {}).get("value") or {"destinatari": {}, "invio_automatico": True}


async def costruisci_report(centro: dict, anno: int, mese: int) -> dict:
    """Riepilogo mensile per entità: PDP, corrispettivi, fatture AdE, estere, banca. Nessun valore inventato: dove manca si scrive 'non disponibile'."""
    db = _d["db"]
    pdp = await _d["pdp_calcolo"](centro, anno, mese)
    estere = await db.fatture_estere.find({"centro_id": centro["id"], "anno": anno, "mese": mese}, {"_id": 0}).sort("data", 1).to_list(500)
    entita = "ditta" if "morbegno" in centro["id"] else "srls" if "abbe8ad2" in centro["id"] else None
    banca = None
    if entita:
        try:
            banca = await _d["riconciliazione"](entita, anno, mese)
        except Exception:
            banca = None
    sez = []
    sez.append(("Entrate", [(k, _eur(v)) for k, v in pdp["entrate"].items() if v] + [("TOTALE ENTRATE", _eur(pdp["tot_entrate"]))]))
    for cat, voci in pdp["sezioni"].items():
        righe = [(k, _eur(v)) for k, v in voci.items() if v]
        if righe:
            sez.append((cat.replace("_", " ").capitalize(), righe + [("Totale", _eur(pdp["tot_spese"].get(cat, 0)))]))
    if pdp.get("spese_cassa"):
        sez.append(("Spese contanti (prima nota)", [(k, _eur(v)) for k, v in pdp["spese_cassa"].items()] + [("Totale", _eur(pdp["tot_spese_cassa"]))]))
    sez.append(("Risultato del mese", [("Entrate − uscite", _eur(pdp["risultato"]))]))
    ade = pdp["ade"]
    sez.append(("Fatture elettroniche AdE", [("Emesse (totale)", _eur(ade["emesse"])), ("Ricevute (totale)", _eur(ade["ricevute"])), ("Ricevute non abbinate a voce PDP", str(len(pdp["ade_non_abbinate"])))]))
    if pdp["fatture_manuali"]["non_riconciliate"]:
        sez.append(("Fatture scritte nelle chiusure SENZA documento AdE (da verificare)", [(f"{f.get('data')} {f.get('cliente') or f.get('descrizione') or ''}", _eur(f.get("totale") or f.get("importo") or 0)) for f in pdp["fatture_manuali"]["non_riconciliate"]]))
    if estere:
        sez.append(("Fatture estere (reverse charge / dogana)", [(f"{e['data']} {e['fornitore']} ({e.get('paese') or '-'}) {('✔ inviata' if e.get('inviata_at') else '⏳ da trasmettere')}",
                                                                   f"imponibile {_eur(e['imponibile'])} · IVA {'integrata ' + _eur(e['iva_integrata']) if e['iva_integrata'] else 'dogana ' + _eur(e.get('iva_dogana') or 0)}") for e in estere]))
    if banca and banca["giorni"]:
        t = banca["totali"]
        sez.append(("Riconciliazione POS", [("POS dichiarato nelle chiusure", _eur(t["pos_chiusure"])), ("Transazioni Nexi/myPOS caricate", _eur(t["pos_transazioni"])), ("Accrediti POS in banca", _eur(t["accrediti_banca"])),
                                            ("Giorni con differenza > 1 €", str(sum(1 for g in banca["giorni"] if g["ok"] is False))), ("Giorni senza transazioni POS caricate", str(sum(1 for g in banca["giorni"] if g["ok"] is None))), ("Fatture ricevute trovate pagate in banca", str(len(banca["fatture_pagate"])))]))
    else:
        sez.append(("Riconciliazione POS / banca", [("Estratti conto", "non caricati per questo mese")]))
    gm = pdp["foglio"].get("giorni_mancanti") if isinstance(pdp.get("foglio"), dict) else None
    avvisi = []
    if pdp["break_even"]["giorni_inseriti"] == 0:
        avvisi.append("Nessun corrispettivo inserito nel mese.")
    if gm:
        avvisi.append(f"Giorni corrispettivi mancanti rispetto al foglio: {len(gm)}.")
    if pdp.get("possibili_doppi"):
        avvisi.append("Possibili doppi conteggi fornitori segnalati nel PDP.")
    return {"centro": centro["nome"], "anno": anno, "mese": mese, "sezioni": sez, "avvisi": avvisi, "estere": estere}


def _html(rep: dict) -> str:
    h = [f"<h2>Riepilogo mensile {escape(rep['centro'])} — {MESI_IT[rep['mese']]} {rep['anno']}</h2>",
         "<p style='color:#555'>Generato automaticamente dal gestionale RS. I valori sono quelli registrati: dove un dato manca viene indicato, non stimato.</p>"]
    if rep["avvisi"]:
        h.append("<p style='color:#b45309'><b>Avvisi:</b> " + " ".join(escape(a) for a in rep["avvisi"]) + "</p>")
    for titolo, righe in rep["sezioni"]:
        h.append(f"<h3 style='margin:14px 0 4px'>{escape(titolo)}</h3><table style='border-collapse:collapse;font-size:13px'>")
        for k, v in righe:
            b = "font-weight:bold;" if k.lower().startswith("tot") else ""
            h.append(f"<tr><td style='padding:2px 10px 2px 0;{b}'>{escape(str(k))}</td><td style='padding:2px 0;text-align:right;{b}'>{escape(str(v))}</td></tr>")
        h.append("</table>")
    return "".join(h)


@router.get("")
async def anteprima(centro_id: str, anno: int, mese: int, user: dict = Depends(require_admin)):
    centro = next((c for c in await _d["centri_tutti"]() if c["id"] == centro_id), None)
    if not centro:
        raise HTTPException(status_code=404, detail="Centro non trovato")
    rep = await costruisci_report(centro, anno, mese)
    return {**rep, "html": _html(rep)}


async def _invia(centro: dict, anno: int, mese: int, to: str, da: str) -> dict:
    rep = await costruisci_report(centro, anno, mese)
    html = _html(rep)
    allegati = [e for e in rep["estere"] if e.get("allegato_path")]
    if allegati:
        html += "<h3>Allegati fatture estere</h3><ul>" + "".join(f"<li>{escape(e['fornitore'])} {escape(e['data'])} — {escape(e.get('allegato_nome') or 'file')}</li>" for e in allegati) + "</ul><p style='color:#555'>I PDF delle fatture estere sono scaricabili dal gestionale (Contabilità → Fatture estere) oppure richiedili in risposta a questa mail.</p>"
    subject = f"Riepilogo contabile {centro['nome']} – {MESI_IT[mese]} {anno}"
    msg_id = await _d["send_email"](to=to, subject=subject, html=html)
    log = {"id": str(uuid.uuid4()), "tipo": "report_commercialista", "centro_id": centro["id"], "anno": anno, "mese": mese, "to": to, "da": da, "at": _now().isoformat(), "message_id": msg_id}
    await _d["db"].contabilita_invii.insert_one(log)
    log.pop("_id", None)
    return log


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InviaInput(BaseModel):
    centro_id: str
    anno: int
    mese: int
    to: str = ""


@router.post("/invia")
async def invia(body: InviaInput, user: dict = Depends(require_admin)):
    centro = next((c for c in await _d["centri_tutti"]() if c["id"] == body.centro_id), None)
    if not centro:
        raise HTTPException(status_code=404, detail="Centro non trovato")
    to = body.to.strip() or (await _cfg())["destinatari"].get(body.centro_id, "")
    if not to:
        raise HTTPException(status_code=400, detail="Email del commercialista non impostata per questa entità")
    if not EMAIL_RE.match(to):
        raise HTTPException(status_code=400, detail="Email non valida")
    return await _invia(centro, body.anno, body.mese, to, user["name"])


async def invio_mensile() -> dict:
    """Cron 1° del mese: invia a ogni commercialista il riepilogo del mese precedente."""
    cfg = await _cfg()
    if not cfg.get("invio_automatico"):
        return {"inviati": 0, "motivo": "disattivato"}
    oggi = date.today()
    mese = oggi.month - 1 or 12
    anno = oggi.year if oggi.month > 1 else oggi.year - 1
    inviati, errori = [], []
    for c in await _d["centri_tutti"]():
        to = cfg["destinatari"].get(c["id"])
        if not to:
            continue
        try:
            await _invia(c, anno, mese, to, "automatico")
            inviati.append(c["nome"])
        except Exception as e:
            errori.append({"centro": c["nome"], "error": str(e)})
    return {"inviati": inviati, "errori": errori}


class CfgInput(BaseModel):
    destinatari: dict
    invio_automatico: bool = True


@router.get("/config")
async def get_cfg(user: dict = Depends(require_admin)):
    cfg = await _cfg()
    cfg["centri"] = [{"id": c["id"], "nome": c["nome"]} for c in await _d["centri_tutti"]()]
    cfg["ultimi_invii"] = await _d["db"].contabilita_invii.find({"tipo": "report_commercialista"}, {"_id": 0}).sort("at", -1).to_list(10)
    return cfg


@router.put("/config")
async def put_cfg(body: CfgInput, user: dict = Depends(require_admin)):
    dest = {k: v.strip() for k, v in body.destinatari.items() if v.strip()}
    for v in dest.values():
        if not EMAIL_RE.match(v):
            raise HTTPException(status_code=400, detail=f"Email non valida: {v}")
    await _d["db"].settings.update_one({"key": "commercialisti_cfg"}, {"$set": {"value": {"destinatari": dest, "invio_automatico": body.invio_automatico}}}, upsert=True)
    return await _cfg()
