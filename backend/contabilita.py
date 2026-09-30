import logging
import os
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger("contabilita")
router = APIRouter(prefix="/contabilita")
_d: dict = {}

MESI_IT = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
NUMERO_AMMINISTRAZIONE = "3792773557"
CONFIG_DEFAULT = {
    "morbegno": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "info@paghesas.it", "email_from": "rscontabilita@gmail.com"},
    "gravedona": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "info@paghesas.it", "email_from": "rscontabilita@gmail.com"},
    "sondrio": {"condividi_admin": True, "wa_numero": NUMERO_AMMINISTRAZIONE, "email_to": "marisa@ncservizi.it", "email_from": "amministrazioners.gruppo@gmail.com"},
}
VOCI_DEFAULT = {
    "entrate": ["Eolo", "Energia / Enel", "Telefonia", "Pacchi"],
    "spese_fisse": ["Stipendi", "Contributi", "TFR", "INAIL", "Condominio", "Affitti", "Utenze", "Commercialista", "Finanziamento"],
    "spese_semifisse": ["Ritiri", "Pubblicità"],
    "fornitori": ["Sifar", "Enel", "Eolo", "Fastweb", "Wind", "KMD", "Iliad", "DHL", "UPS", "Kolme", "GLS", "Prontopacco", "Fermopoint", "Mooney", "Nexi", "Pixartprinting", "Miwo", "Raffaella", "CDR", "Parking"],
}
VOCI_DEFAULT_SONDRIO = {
    "entrate": ["Eolo", "Enel mese precedente", "Telefonia", "Pacchi"],
    "spese_fisse": ["Stipendi", "Affitti", "Utenze", "Condominio", "Finanziamento", "Commercialista", "Elena", "Enrico", "INPS Enrico"],
    "spese_semifisse": ["Ritiri", "Pubblicità"],
    "fornitori": ["Nexi", "Fastweb", "Master Group", "KMD", "Iliad", "DHL", "Mooney", "Compass", "Benzina", "Antonino", "W3", "Sifar", "Enel", "Eolo", "Teknozone", "Kolme", "Miwo", "Raffaella", "CDR", "Parking"],
}
CATEGORIE = ["entrate", "spese_fisse", "spese_semifisse", "fornitori"]


def setup(**deps):
    _d.update(deps)


def _slug(nome: str) -> str:
    return (nome or "").strip().lower()


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _is_admin(user: dict) -> bool:
    return user["role"] == "admin" or bool(user.get("can_view_all"))


async def _config(store: dict) -> dict:
    cfg = await _d["db"].contabilita_config.find_one({"store_id": store["id"]}, {"_id": 0}) or {}
    base = {"store_id": store["id"], "condividi_admin": False, "wa_numero": "", "email_to": "", "email_from": "", "wa_attivo": True, "email_attivo": True}
    base.update(CONFIG_DEFAULT.get(_slug(store["nome"]), {}))
    base.update({k: v for k, v in cfg.items() if v is not None})
    return base


async def _stores_visibili(user: dict) -> list:
    """Ritorna [(store, config, completo)]: completo=False → admin vede solo attivo/ultimo inserimento."""
    db = _d["db"]
    q = {} if _is_admin(user) else {"id": {"$in": user.get("store_ids") or []}}
    out = []
    async for s in db.stores.find(q, {"_id": 0, "id": 1, "nome": 1, "telefono_avvisi": 1}).sort("nome", 1):
        cfg = await _config(s)
        completo = (s["id"] in (user.get("store_ids") or [])) or (_is_admin(user) and cfg["condividi_admin"])
        out.append((s, cfg, completo))
    return out


async def _store_completo(user: dict, store_id: str) -> tuple:
    for s, cfg, completo in await _stores_visibili(user):
        if s["id"] == store_id:
            if not completo:
                raise HTTPException(status_code=403, detail="Il negozio non condivide i corrispettivi con l'amministrazione")
            return s, cfg
    raise HTTPException(status_code=403, detail="Negozio non accessibile")


def _f(v) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _eur(v) -> str:
    s = f"{_f(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


def _norm(c: dict) -> dict:
    fatt = [{"numero": (x.get("numero") or "")[:30], "importo": _f(x.get("importo")), "pagamento": (x.get("pagamento") or "")[:20]} for x in (c.get("fatture_dettaglio") or []) if x.get("numero") or x.get("importo")]
    c["fatture_dettaglio"] = fatt
    c["fatture"] = _f(c.get("fatture")) or round(sum(x["importo"] for x in fatt), 2)
    for k in ("riparazioni", "merce", "art74", "contanti", "pos", "versati"):
        c[k] = _f(c.get(k))
    c["totale"] = round(c["riparazioni"] + c["merce"] + c["art74"] + c["fatture"], 2)
    c["incassato"] = round(c["contanti"] + c["pos"], 2)
    c["iva"] = round((c["riparazioni"] + c["merce"] + c["fatture"]) * 22 / 122, 2)
    return c


# ---------------- Meta / config ----------------
@router.get("/meta")
async def meta(request: Request):
    user = await _user(request)
    db = _d["db"]
    out = []
    for s, cfg, completo in await _stores_visibili(user):
        ultimo = await db.corrispettivi.find_one({"store_id": s["id"]}, {"_id": 0, "data": 1, "updated_at": 1}, sort=[("data", -1)])
        item = {"id": s["id"], "nome": s["nome"], "completo": completo, "attivo": bool(ultimo), "ultimo_inserimento": (ultimo or {}).get("data")}
        if completo:
            item["config"] = cfg
        out.append(item)
    return {"stores": out, "is_admin": _is_admin(user), "categorie": CATEGORIE, "numero_amministrazione": NUMERO_AMMINISTRAZIONE}


class ConfigInput(BaseModel):
    condividi_admin: Optional[bool] = None
    wa_numero: Optional[str] = None
    wa_attivo: Optional[bool] = None
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    email_attivo: Optional[bool] = None


@router.patch("/config/{store_id}")
async def patch_config(store_id: str, body: ConfigInput, request: Request):
    user = await _user(request)
    mio = store_id in (user.get("store_ids") or [])
    if not mio and not _is_admin(user):
        raise HTTPException(status_code=403, detail="Negozio non accessibile")
    if not mio and body.condividi_admin is not None and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo il negozio decide cosa condividere")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "wa_numero" in upd:
        upd["wa_numero"] = re.sub(r"\D", "", upd["wa_numero"])
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _d["db"].contabilita_config.update_one({"store_id": store_id}, {"$set": upd, "$setOnInsert": {"store_id": store_id}}, upsert=True)
    store = await _d["db"].stores.find_one({"id": store_id}, {"_id": 0, "id": 1, "nome": 1})
    return await _config(store)


# ---------------- Corrispettivi ----------------
async def _mese_dati(store_id: str, anno: int, mese: int) -> dict:
    db = _d["db"]
    pref = f"{anno:04d}-{mese:02d}"
    giorni = {c["data"]: _norm(c) async for c in db.corrispettivi.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0})}
    spese = await db.spese_cassa.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0}).sort("data", 1).to_list(500)
    n = monthrange(anno, mese)[1]
    righe = []
    for g in range(1, n + 1):
        d = f"{pref}-{g:02d}"
        righe.append(giorni.get(d) or {"data": d, "vuoto": True})
    keys = ("riparazioni", "merce", "art74", "fatture", "totale", "contanti", "pos", "incassato", "versati", "iva")
    tot = {k: round(sum(_f(c.get(k)) for c in giorni.values()), 2) for k in keys}
    tot["spese_contanti"] = round(sum(_f(s.get("importo")) for s in spese), 2)
    tot["cassa_netta"] = round(tot["contanti"] - tot["spese_contanti"], 2)
    tot["giorni_inseriti"] = len(giorni)
    return {"anno": anno, "mese": mese, "righe": righe, "spese": spese, "totali": tot}


@router.get("/corrispettivi")
async def get_corrispettivi(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    store, cfg = await _store_completo(user, store_id)
    out = await _mese_dati(store_id, anno, mese)
    out["store"] = {"id": store["id"], "nome": store["nome"]}
    return out


class CorrispettivoInput(BaseModel):
    riparazioni: float = 0
    merce: float = 0
    art74: float = 0
    fatture: float = 0
    fatture_dettaglio: list = []
    contanti: float = 0
    pos: float = 0
    versati: float = 0
    note: str = ""


@router.put("/corrispettivi/{store_id}/{data}")
async def put_corrispettivo(store_id: str, data: str, body: CorrispettivoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    try:
        date.fromisoformat(data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data non valida")
    doc = _norm(body.model_dump())
    doc.update({"store_id": store_id, "data": data, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name", "")})
    await _d["db"].corrispettivi.update_one({"store_id": store_id, "data": data}, {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return await _d["db"].corrispettivi.find_one({"store_id": store_id, "data": data}, {"_id": 0})


@router.delete("/corrispettivi/{store_id}/{data}")
async def del_corrispettivo(store_id: str, data: str, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].corrispettivi.delete_one({"store_id": store_id, "data": data})
    return {"ok": True}


class SpesaInput(BaseModel):
    store_id: str
    data: str
    motivo: str
    importo: float
    riferimento: str = ""


@router.post("/spese")
async def add_spesa(body: SpesaInput, request: Request):
    user = await _user(request)
    await _store_completo(user, body.store_id)
    doc = body.model_dump()
    doc.update({"id": str(uuid.uuid4()), "importo": _f(body.importo), "created_at": datetime.now(timezone.utc).isoformat(), "created_by": user.get("name", "")})
    await _d["db"].spese_cassa.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/spese/{spesa_id}")
async def del_spesa(spesa_id: str, request: Request):
    user = await _user(request)
    sp = await _d["db"].spese_cassa.find_one({"id": spesa_id}, {"_id": 0})
    if not sp:
        raise HTTPException(status_code=404, detail="Spesa non trovata")
    await _store_completo(user, sp["store_id"])
    await _d["db"].spese_cassa.delete_one({"id": spesa_id})
    return {"ok": True}


# ---------------- PDF mensile ----------------
def _pdf_txt(s) -> str:
    return str(s).replace("–", "-").replace("—", "-").replace("€", "EUR").encode("latin-1", "replace").decode("latin-1")


def _pdf_mese(store: dict, dati: dict) -> bytes:
    from fpdf import FPDF
    anno, mese, tot = dati["anno"], dati["mese"], dati["totali"]
    pdf = FPDF(orientation="L", format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _pdf_txt(f"Corrispettivi giornalieri - {store['nome']} - {MESI_IT[mese]} {anno}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, _pdf_txt(f"Generato il {date.today().strftime('%d/%m/%Y')} - RS Riparazioni / CambiaOra"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    cols = [("Giorno", 16), ("Riparazioni", 26), ("Merce", 24), ("Art. 74", 24), ("Fatture", 24), ("N. fattura / pag.", 48), ("TOTALE", 26), ("Contanti", 24), ("POS", 24), ("Versati", 24), ("IVA 22%", 22)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(226, 232, 240)
    for t, w in cols:
        pdf.cell(w, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in dati["righe"]:
        g = r["data"][8:]
        if r.get("vuoto"):
            vals = [g, "", "", "", "", "", "-", "", "", "", ""]
        else:
            fd = ", ".join(f"{x['numero']} {x['pagamento']}".strip() for x in r["fatture_dettaglio"])[:34]
            vals = [g, _eur(r["riparazioni"]), _eur(r["merce"]), _eur(r["art74"]), _eur(r["fatture"]), fd, _eur(r["totale"]), _eur(r["contanti"]), _eur(r["pos"]), _eur(r["versati"]) if r["versati"] else "", _eur(r["iva"])]
        for (t, w), v in zip(cols, vals):
            pdf.cell(w, 6, _pdf_txt(v), border=1, align="R" if t not in ("Giorno", "N. fattura / pag.") else "L")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 8)
    vals = ["TOT", _eur(tot["riparazioni"]), _eur(tot["merce"]), _eur(tot["art74"]), _eur(tot["fatture"]), "", _eur(tot["totale"]), _eur(tot["contanti"]), _eur(tot["pos"]), _eur(tot["versati"]), _eur(tot["iva"])]
    for (t, w), v in zip(cols, vals):
        pdf.cell(w, 7, _pdf_txt(v), border=1, fill=True, align="R" if t != "Giorno" else "L")
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Spese per contanti / cassa [PRIMA NOTA]", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 8)
    for t, w in [("Data", 24), ("Motivo", 110), ("Importo", 30), ("N. fattura / ritiro", 50)]:
        pdf.cell(w, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for s in dati["spese"]:
        for v, w in [(s["data"][8:] + "/" + s["data"][5:7], 24), (s.get("motivo", "")[:70], 110), (_eur(s["importo"]), 30), (s.get("riferimento", "")[:30], 50)]:
            pdf.cell(w, 6, _pdf_txt(v), border=1)
        pdf.ln()
    if not dati["spese"]:
        pdf.cell(214, 6, "Nessuna spesa registrata", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, _pdf_txt(f"Totale spese contanti: {_eur(tot['spese_contanti'])}  -  Contanti incassati: {_eur(tot['contanti'])}  -  Cassa netta: {_eur(tot['cassa_netta'])}  -  Giorni inseriti: {tot['giorni_inseriti']}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


@router.get("/corrispettivi/pdf")
async def pdf_corrispettivi(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    data = _pdf_mese(store, await _mese_dati(store_id, anno, mese))
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Corrispettivi_{store["nome"]}_{anno}-{mese:02d}.pdf"'})


# ---------------- Invii ----------------
def _testo_wa_store(nome: str, c: Optional[dict], spese: list, data: str) -> str:
    d = f"{data[8:]}/{data[5:7]}/{data[:4]}"
    if not c:
        return f"*{nome}* - {d}\nNessun corrispettivo inserito oggi."
    righe = [f"*{nome}* - {d}",
             f"Riparazioni: {_eur(c['riparazioni'])}", f"Merce: {_eur(c['merce'])}", f"Art. 74: {_eur(c['art74'])}"]
    if c["fatture"]:
        det = ", ".join(f"{x['numero']} {x['pagamento']}".strip() for x in c["fatture_dettaglio"])
        righe.append(f"Fatture: {_eur(c['fatture'])}" + (f" ({det})" if det else ""))
    righe += [f"*TOTALE: {_eur(c['totale'])}*", f"Contanti: {_eur(c['contanti'])} | POS: {_eur(c['pos'])}"]
    if c["versati"]:
        righe.append(f"Versati: {_eur(c['versati'])}")
    if spese:
        righe.append("Spese contanti: " + "; ".join(f"{s['motivo']} {_eur(s['importo'])}" for s in spese))
        righe.append(f"Totale spese: {_eur(sum(s['importo'] for s in spese))}")
    if c.get("note"):
        righe.append(f"Note: {c['note']}")
    return "\n".join(righe)


async def invia_wa_giornaliero(giorno: Optional[str] = None, solo_store: Optional[str] = None) -> list:
    """Alle 20:30: un messaggio per numero destinatario con tutti i negozi che lo hanno impostato, dal numero del primo negozio."""
    db = _d["db"]
    giorno = giorno or date.today().isoformat()
    gruppi: dict = {}
    async for s in db.stores.find({} if not solo_store else {"id": solo_store}, {"_id": 0, "id": 1, "nome": 1}):
        cfg = await _config(s)
        if not cfg["wa_numero"] or not cfg.get("wa_attivo", True):
            continue
        c = await db.corrispettivi.find_one({"store_id": s["id"], "data": giorno}, {"_id": 0})
        spese = await db.spese_cassa.find({"store_id": s["id"], "data": giorno}, {"_id": 0}).to_list(100)
        gruppi.setdefault(cfg["wa_numero"], []).append((s, _norm(c) if c else None, spese))
    esiti = []
    for numero, items in gruppi.items():
        testo = f"📊 *Corrispettivi del giorno*\n\n" + "\n\n".join(_testo_wa_store(s["nome"], c, sp, giorno) for s, c, sp in items)
        session = items[0][0]["id"]
        for s, c, sp in items:
            if await _d["wa_sessione_connessa"](s["id"]):
                session = s["id"]
                break
        try:
            await _d["wa_send"](numero, testo, session=session, tipo="corrispettivi_giornalieri")
            esiti.append({"numero": numero, "negozi": [s["nome"] for s, _, _ in items], "ok": True})
        except Exception as e:
            esiti.append({"numero": numero, "negozi": [s["nome"] for s, _, _ in items], "ok": False, "error": str(getattr(e, "detail", e))})
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "wa_giornaliero", "giorno": giorno, "esiti": esiti, "at": datetime.now(timezone.utc).isoformat()})
    return esiti


@router.post("/corrispettivi/invia-whatsapp")
async def invia_whatsapp_manuale(store_id: str, data: str, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    return await invia_wa_giornaliero(data, solo_store=store_id)


async def invia_email_mensile(store_id: str, anno: int, mese: int, extra_to: Optional[str] = None) -> dict:
    db = _d["db"]
    store = await db.stores.find_one({"id": store_id}, {"_id": 0, "id": 1, "nome": 1})
    cfg = await _config(store)
    to = extra_to or cfg["email_to"]
    if not to or "@" not in to:
        return {"inviato": False, "motivo": "Email destinatario non impostata"}
    dati = await _mese_dati(store_id, anno, mese)
    if not dati["totali"]["giorni_inseriti"]:
        return {"inviato": False, "motivo": "Nessun corrispettivo nel mese"}
    pdf = _pdf_mese(store, dati)
    path = f"{_d['app_name']}/contabilita/{store['nome']}_{anno}-{mese:02d}_{uuid.uuid4().hex[:8]}.pdf"
    res = _d["put_object"](path, pdf, "application/pdf")
    token = uuid.uuid4().hex
    fname = f"Corrispettivi_{store['nome']}_{anno}-{mese:02d}.pdf"
    await db.report_download.insert_one({"token": token, "path": res["path"], "content_type": "application/pdf", "filename": fname,
                                         "expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
                                         "created_at": datetime.now(timezone.utc).isoformat()})
    link = f"{os.environ.get('FRONTEND_URL', '').rstrip('/')}/api/public/report/{token}"
    t = dati["totali"]
    html = (f"<div style='font-family:Arial,sans-serif;color:#0f172a'><h2>Corrispettivi {escape(store['nome'])} - {MESI_IT[mese]} {anno}</h2>"
            f"<p>Buongiorno, in allegato (link sicuro, valido 60 giorni) il riepilogo dei corrispettivi giornalieri e delle spese di cassa del mese.</p>"
            f"<p><a href='{link}' style='display:inline-block;padding:10px 16px;background:#0f172a;color:#fff;border-radius:8px;text-decoration:none'>Scarica il PDF completo</a></p>"
            f"<table style='border-collapse:collapse;font-size:13px'>"
            + "".join(f"<tr><td style='padding:4px 10px;border-bottom:1px solid #e2e8f0'>{k}</td><td style='padding:4px 10px;border-bottom:1px solid #e2e8f0;text-align:right'><b>{escape(_eur(v))}</b></td></tr>"
                      for k, v in [("Riparazioni", t["riparazioni"]), ("Merce", t["merce"]), ("Art. 74", t["art74"]), ("Fatture", t["fatture"]), ("TOTALE corrispettivi", t["totale"]),
                                   ("Contanti", t["contanti"]), ("POS", t["pos"]), ("Versati", t["versati"]), ("IVA 22% scorporata", t["iva"]), ("Spese contanti (prima nota)", t["spese_contanti"])])
            + f"</table><p style='font-size:12px;color:#64748b'>Giorni inseriti: {t['giorni_inseriti']}. Inviato da {escape(cfg['email_from'] or 'gestionale')} - RS Riparazioni / CambiaOra.</p></div>")
    email_id = await _d["send_email"](to=to, subject=f"Corrispettivi {store['nome']} - {MESI_IT[mese]} {anno}", html=html,
                                      reply_to=cfg["email_from"] or None, from_name=cfg["email_from"] or None)
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "email_mensile", "store_id": store_id, "anno": anno, "mese": mese, "to": to,
                                         "from": cfg["email_from"], "link": link, "email_id": email_id, "at": datetime.now(timezone.utc).isoformat()})
    return {"inviato": True, "to": to, "from": cfg["email_from"], "link": link}


async def invia_email_mensile_tutti() -> list:
    oggi = date.today()
    prev = (oggi.replace(day=1) - timedelta(days=1))
    out = []
    async for s in _d["db"].stores.find({}, {"_id": 0, "id": 1, "nome": 1}):
        cfg = await _config(s)
        if not cfg["email_to"] or not cfg.get("email_attivo", True):
            continue
        try:
            out.append({"negozio": s["nome"], **(await invia_email_mensile(s["id"], prev.year, prev.month))})
        except Exception as e:
            out.append({"negozio": s["nome"], "inviato": False, "motivo": str(getattr(e, "detail", e))})
    logger.info(f"Email corrispettivi mensili: {out}")
    return out


@router.post("/corrispettivi/invia-email")
async def invia_email_manuale(store_id: str, anno: int, mese: int, request: Request, to: Optional[str] = None):
    user = await _user(request)
    await _store_completo(user, store_id)
    return await invia_email_mensile(store_id, anno, mese, extra_to=to)


@router.get("/log")
async def log_invii(request: Request):
    user = await _user(request)
    ids = [s["id"] for s, _, completo in await _stores_visibili(user) if completo]
    q = {"$or": [{"store_id": {"$in": ids}}, {"tipo": "wa_giornaliero"}]} if not _is_admin(user) else {}
    return await _d["db"].contabilita_log.find(q, {"_id": 0}).sort("at", -1).to_list(60)


# ---------------- Punto di pareggio ----------------
async def _voci(store: dict) -> dict:
    doc = await _d["db"].pdp_voci.find_one({"store_id": store["id"]}, {"_id": 0})
    if doc:
        return {k: doc.get(k, []) for k in CATEGORIE}
    base = VOCI_DEFAULT_SONDRIO if _slug(store["nome"]) == "sondrio" else VOCI_DEFAULT
    return {k: list(v) for k, v in base.items()}


class VociInput(BaseModel):
    entrate: list = []
    spese_fisse: list = []
    spese_semifisse: list = []
    fornitori: list = []


@router.get("/pdp/voci/{store_id}")
async def get_voci(store_id: str, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    return await _voci(store)


@router.put("/pdp/voci/{store_id}")
async def put_voci(store_id: str, body: VociInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    doc = {k: [str(x).strip()[:60] for x in getattr(body, k) if str(x).strip()] for k in CATEGORIE}
    await _d["db"].pdp_voci.update_one({"store_id": store_id}, {"$set": doc}, upsert=True)
    return doc


async def _pdp_calcolo(store: dict, anno: int, mese: int) -> dict:
    db = _d["db"]
    voci = await _voci(store)
    doc = await db.pdp.find_one({"store_id": store["id"], "anno": anno, "mese": mese}, {"_id": 0}) or {}
    valori = dict(doc.get("valori") or {})
    ereditato_da = None
    if not doc:
        prev = await db.pdp.find({"store_id": store["id"], "$or": [{"anno": {"$lt": anno}}, {"anno": anno, "mese": {"$lt": mese}}]},
                                 {"_id": 0, "anno": 1, "mese": 1, "valori": 1}).sort([("anno", -1), ("mese", -1)]).limit(1).to_list(1)
        if prev:
            fisse = {k: v for k, v in (prev[0].get("valori") or {}).items() if k.startswith("spese_fisse|") and _f(v)}
            if fisse:
                valori.update(fisse)
                ereditato_da = f"{MESI_IT[prev[0]['mese']]} {prev[0]['anno']}"
    corr = (await _mese_dati(store["id"], anno, mese))["totali"]
    entrate = {"Corrispettivi negozio": corr["totale"]}
    for v in voci["entrate"]:
        entrate[v] = _f(valori.get(f"entrate|{v}"))
    sezioni = {}
    for cat in ("spese_fisse", "spese_semifisse", "fornitori"):
        sezioni[cat] = {v: _f(valori.get(f"{cat}|{v}")) for v in voci[cat]}
    tot_entrate = round(sum(entrate.values()), 2)
    tot_spese = {cat: round(sum(d.values()), 2) for cat, d in sezioni.items()}
    tot_uscite = round(sum(tot_spese.values()), 2)
    return {"store": {"id": store["id"], "nome": store["nome"]}, "anno": anno, "mese": mese, "voci": voci, "valori": valori,
            "entrate": entrate, "sezioni": sezioni, "tot_entrate": tot_entrate, "tot_spese": tot_spese, "tot_uscite": tot_uscite,
            "punto_pareggio": tot_uscite, "risultato": round(tot_entrate - tot_uscite, 2),
            "copertura_pct": round(tot_entrate / tot_uscite * 100, 1) if tot_uscite else None, "note": doc.get("note", ""), "ereditato_da": ereditato_da}


@router.get("/pdp")
async def get_pdp(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    return await _pdp_calcolo(store, anno, mese)


class PdpInput(BaseModel):
    valori: dict = {}
    note: str = ""


@router.put("/pdp/{store_id}/{anno}/{mese}")
async def put_pdp(store_id: str, anno: int, mese: int, body: PdpInput, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    valori = {k: _f(v) for k, v in body.valori.items() if "|" in k}
    await _d["db"].pdp.update_one({"store_id": store_id, "anno": anno, "mese": mese},
                                  {"$set": {"valori": valori, "note": body.note[:500], "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user.get("name", "")},
                                   "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return await _pdp_calcolo(store, anno, mese)


# ---------------- Report annuale ----------------
async def _fatturato_mese(store: dict, anno: int, mese: int) -> dict:
    db = _d["db"]
    storico = await db.fatturato_storico.find_one({"store_id": store["id"], "anno": anno, "mese": mese}, {"_id": 0})
    corr = (await _mese_dati(store["id"], anno, mese))["totali"]["totale"]
    doc = await db.pdp.find_one({"store_id": store["id"], "anno": anno, "mese": mese}, {"_id": 0, "valori": 1}) or {}
    enel = sum(_f(v) for k, v in (doc.get("valori") or {}).items() if k.startswith("entrate|") and "enel" in k.lower() or k.startswith("entrate|") and "energia" in k.lower())
    altro_pdp = sum(_f(v) for k, v in (doc.get("valori") or {}).items() if k.startswith("entrate|")) - enel
    live = {"enel": round(enel, 2), "altro": round(corr + altro_pdp, 2)}
    if storico:
        st = {"enel": _f(storico.get("enel")), "altro": _f(storico.get("altro")), "storico": True}
        if live["enel"] + live["altro"] <= st["enel"] + st["altro"]:
            return st
    return live


@router.get("/report/annuale")
async def report_annuale(store_id: str, anno: int, request: Request):
    user = await _user(request)
    store, _ = await _store_completo(user, store_id)
    mesi = []
    tot = {"enel": 0.0, "altro": 0.0, "tot": 0.0, "enel_ap": 0.0, "altro_ap": 0.0, "tot_ap": 0.0}
    for m in range(1, 13):
        cur = await _fatturato_mese(store, anno, m)
        ap = await _fatturato_mese(store, anno - 1, m)
        cur_t, ap_t = round(cur["enel"] + cur["altro"], 2), round(ap["enel"] + ap["altro"], 2)
        pct = round((cur_t - ap_t) / ap_t * 100, 2) if ap_t and cur_t else None
        pct_enel = round((cur["enel"] - ap["enel"]) / ap["enel"] * 100, 2) if ap["enel"] and cur["enel"] else None
        pct_altro = round((cur["altro"] - ap["altro"]) / ap["altro"] * 100, 2) if ap["altro"] and cur["altro"] else None
        mesi.append({"mese": m, "nome": MESI_IT[m], "enel": cur["enel"], "altro": cur["altro"], "tot": cur_t, "storico": cur.get("storico", False),
                     "enel_ap": ap["enel"], "altro_ap": ap["altro"], "tot_ap": ap_t, "pct": pct, "pct_enel": pct_enel, "pct_altro": pct_altro})
        for k in ("enel", "altro"):
            tot[k] += cur[k]
            tot[k + "_ap"] += ap[k]
        tot["tot"] += cur_t
        tot["tot_ap"] += ap_t
    tot = {k: round(v, 2) for k, v in tot.items()}
    tot["pct"] = round((tot["tot"] - tot["tot_ap"]) / tot["tot_ap"] * 100, 2) if tot["tot_ap"] and tot["tot"] else None
    return {"store": {"id": store["id"], "nome": store["nome"]}, "anno": anno, "mesi": mesi, "totali": tot}


FOGLI_STORICO = {"sondrio": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "0", "tot"),
                 "morbegno": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "1406738088", "split"),
                 "gravedona": ("1CkU75t1-IR4qibi_Elst24LJJzVhGlLZK4yoAYqNOMc", "1680449865", "tot")}
MESI_UP = [m.upper() for m in MESI_IT]


def _num_it(v: str) -> float:
    s = (v or "").strip().replace("€", "").replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _parse_storico(csv_text: str, modo: str) -> list:
    import csv
    import io
    rows = list(csv.reader(io.StringIO(csv_text)))
    header = next((r for r in rows if r and r[0].strip().lower() == "fatturato"), None)
    if not header:
        return []
    anni = []
    for i, h in enumerate(header):
        m = re.match(r"^\s*(20\d\d)\s*(ENEL|ALTRO|tot)?\s*$", h.strip(), re.I)
        if m and (modo == "tot" and not m.group(2) or modo == "split" and m.group(2) and m.group(2).lower() != "tot"):
            anni.append((int(m.group(1)), (m.group(2) or "").lower(), i))
    out = []
    for r in rows:
        nome = (r[0] if r else "").strip().upper()
        if nome not in MESI_UP or nome == "":
            continue
        mese = MESI_UP.index(nome)
        per_anno: dict = {}
        for anno, tipo, i in anni:
            v = _num_it(r[i]) if i < len(r) else 0.0
            d = per_anno.setdefault(anno, {"enel": 0.0, "altro": 0.0})
            d["enel" if tipo == "enel" else "altro"] += v
        for anno, d in per_anno.items():
            if d["enel"] or d["altro"]:
                out.append({"anno": anno, "mese": mese, **d})
    return out


@router.post("/report/importa-fogli")
async def importa_storico_fogli(request: Request):
    import httpx
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    stores = {_slug(s["nome"]): s async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    esito = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for slug, (sheet_id, gid, modo) in FOGLI_STORICO.items():
            store = stores.get(slug)
            if not store:
                esito.append({"negozio": slug, "errore": "negozio non trovato"})
                continue
            resp = await client.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}")
            if resp.status_code != 200:
                esito.append({"negozio": store["nome"], "errore": f"foglio non leggibile ({resp.status_code})"})
                continue
            righe = _parse_storico(resp.text, modo)
            for r in righe:
                await db.fatturato_storico.update_one({"store_id": store["id"], "anno": r["anno"], "mese": r["mese"]},
                                                      {"$set": {"enel": round(r["enel"], 2), "altro": round(r["altro"], 2), "fonte": "foglio_google",
                                                                "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            esito.append({"negozio": store["nome"], "mesi_importati": len(righe), "anni": sorted({r["anno"] for r in righe})})
    await db.contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "import_storico", "esito": esito, "by": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()})
    return {"esito": esito}


@router.post("/corrispettivi/importa-fogli")
async def importa_corrispettivi_fogli(request: Request):
    import httpx
    import contabilita_import
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async def fetch(url):
            r = await client.get(url)
            r.raise_for_status()
            return r.text
        esito = await contabilita_import.importa_tutti(_d["db"], fetch)
    await _d["db"].contabilita_log.insert_one({"id": str(uuid.uuid4()), "tipo": "import_corrispettivi", "esito": esito, "by": user.get("name", ""), "at": datetime.now(timezone.utc).isoformat()})
    return {"esito": esito, "giorni": sum(e.get("giorni", 0) for e in esito), "spese": sum(e.get("spese", 0) for e in esito), "errori": [e for e in esito if e.get("errore")]}


class NuovoNegozioInput(BaseModel):
    nome: str
    referente: str = ""
    telefono_avvisi: str = ""
    wa_numero: str = ""
    email_to: str = ""
    email_from: str = ""
    condividi_admin: bool = True


@router.post("/negozi")
async def nuovo_negozio(body: NuovoNegozioInput, request: Request):
    user = await _user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    nome = body.nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome negozio obbligatorio")
    if await db.stores.find_one({"nome": {"$regex": f"^{re.escape(nome)}$", "$options": "i"}}):
        raise HTTPException(status_code=400, detail="Esiste già un negozio con questo nome")
    now = datetime.now(timezone.utc).isoformat()
    store = {"id": str(uuid.uuid4()), "nome": nome, "referente": body.referente.strip(), "tipo": "negozio", "note": "", "review_link": "",
             "telefono_avvisi": re.sub(r"\D", "", body.telefono_avvisi), "email_commercialista": body.email_to.strip(), "msg_privacy": "", "msg_pronto": "",
             "msg_recensione": "", "msg_promemoria": "", "pagato": False, "last_payment_date": None, "created_at": now}
    await db.stores.insert_one(store)
    await db.contabilita_config.update_one({"store_id": store["id"]}, {"$set": {
        "store_id": store["id"], "condividi_admin": body.condividi_admin, "wa_numero": re.sub(r"\D", "", body.wa_numero), "wa_attivo": bool(body.wa_numero),
        "email_to": body.email_to.strip(), "email_from": body.email_from.strip(), "email_attivo": bool(body.email_to), "updated_at": now}}, upsert=True)
    return {"id": store["id"], "nome": nome}


@router.get("/report/confronto")
async def report_confronto(anno: int, request: Request):
    user = await _user(request)
    negozi = []
    for store, cfg, completo in await _stores_visibili(user):
        if not completo:
            continue
        mesi = []
        for m in range(1, 13):
            cur = await _fatturato_mese(store, anno, m)
            ap = await _fatturato_mese(store, anno - 1, m)
            pdp = await _pdp_calcolo(store, anno, m)
            ha_pdp = pdp["tot_uscite"] > 0
            mesi.append({"mese": m, "tot": round(cur["enel"] + cur["altro"], 2), "tot_ap": round(ap["enel"] + ap["altro"], 2),
                         "pdp_risultato": pdp["risultato"] if ha_pdp else None, "pdp_uscite": pdp["tot_uscite"] if ha_pdp else None})
        tot, tot_ap = round(sum(x["tot"] for x in mesi), 2), round(sum(x["tot_ap"] for x in mesi), 2)
        pdp_tot = round(sum(x["pdp_risultato"] for x in mesi if x["pdp_risultato"] is not None), 2) if any(x["pdp_risultato"] is not None for x in mesi) else None
        negozi.append({"id": store["id"], "nome": store["nome"], "mesi": mesi, "tot": tot, "tot_ap": tot_ap, "pdp_tot": pdp_tot,
                       "pct": round((tot - tot_ap) / tot_ap * 100, 2) if tot_ap and tot else None})
    return {"anno": anno, "mesi": [MESI_IT[m] for m in range(1, 13)], "negozi": negozi}


class StoricoInput(BaseModel):
    enel: float = 0
    altro: float = 0


@router.put("/report/storico/{store_id}/{anno}/{mese}")
async def put_storico(store_id: str, anno: int, mese: int, body: StoricoInput, request: Request):
    user = await _user(request)
    await _store_completo(user, store_id)
    await _d["db"].fatturato_storico.update_one({"store_id": store_id, "anno": anno, "mese": mese},
                                                {"$set": {"enel": _f(body.enel), "altro": _f(body.altro), "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True}
