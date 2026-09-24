import calendar
import io
import os
import re
import uuid
import zipfile
from datetime import date, datetime, timezone, timedelta
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Response
from pydantic import BaseModel

RITIRO_STATI = ["ritirato", "in_vendita", "venduto", "pezzi_ricambio", "uso_interno"]
RITIRO_STATO_LABEL = {"ritirato": "Ritirato", "in_vendita": "In vendita", "venduto": "Venduto",
                      "pezzi_ricambio": "Pezzi di ricambio", "uso_interno": "Uso interno"}
MESI_IT = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

router = APIRouter()
_d: dict = {}


def setup(**deps):
    _d.update(deps)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = None
    if auth.lower().startswith("bearer "):
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
    return await _d["get_current_user"](request, creds)


def _user():
    return Depends(_current_user)


def _fmt_it(iso: Optional[str]) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _eur(v) -> str:
    return "-" if v is None else f"{float(v):.2f} EUR"


async def aggiorna_stato_ritiro(ritiro_id: str, stato: str, numero_fattura: str = "", user_name: str = "sistema") -> None:
    """Chiamato da vendite / magazzino / ricambi: aggiorna lo stato del ritiro collegato."""
    if not ritiro_id or stato not in RITIRO_STATI:
        return
    now = datetime.now(timezone.utc).isoformat()
    upd = {"stato": stato, "updated_at": now}
    if numero_fattura:
        upd["numero_fattura"] = numero_fattura
    if stato == "venduto":
        upd["venduto_at"] = now
    await _d["db"].ritiri.update_one({"id": ritiro_id}, {"$set": upd, "$push": {"stato_log": {"stato": stato, "at": now, "by": user_name}}})


class StatoRitiroInput(BaseModel):
    stato: str
    numero_fattura: str = ""


@router.patch("/ritiri/{ritiro_id}/stato")
async def set_stato_ritiro(ritiro_id: str, input: StatoRitiroInput, user: dict = _user()):
    db = _d["db"]
    scope = _d["ritiri_scope"](user)
    scope["id"] = ritiro_id
    if not await db.ritiri.find_one(scope, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Ritiro non trovato")
    if input.stato not in RITIRO_STATI:
        raise HTTPException(status_code=400, detail="Stato non valido")
    if input.stato == "venduto" and not input.numero_fattura.strip():
        raise HTTPException(status_code=400, detail="Per 'Venduto' indica il numero di fattura")
    await aggiorna_stato_ritiro(ritiro_id, input.stato, input.numero_fattura.strip(), user["name"])
    return await db.ritiri.find_one({"id": ritiro_id}, {"_id": 0})


# ---------------- Report mensile ----------------
async def _ritiri_mese(store_id: str, anno: int, mese: int) -> list:
    db = _d["db"]
    da = f"{anno:04d}-{mese:02d}-01"
    a = f"{anno:04d}-{mese:02d}-{calendar.monthrange(anno, mese)[1]:02d}"
    return await db.ritiri.find({"store_id": store_id, "data_ritiro": {"$gte": da, "$lte": a + "T23:59:59"}},
                                {"_id": 0}).sort("data_ritiro", 1).to_list(2000)


def _stato_testo(r: dict) -> str:
    st = r.get("stato") or ("in_vendita" if r.get("crea_rigenerato", True) else "ritirato")
    txt = RITIRO_STATO_LABEL.get(st, st)
    if st == "venduto" and r.get("numero_fattura"):
        txt += f" - Fatt. {r['numero_fattura']}"
    return txt


def _report_pdf(store: dict, anno: int, mese: int, ritiri: list) -> bytes:
    from fpdf import FPDF
    pdf = FPDF(orientation="L", format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, f"Registro ritiri usato - {store.get('nome', '')} - {MESI_IT[mese]} {anno}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generato il {date.today().strftime('%d/%m/%Y')} - RS Riparazioni / CambiaOra. Numerazione annuale per negozio (riparte da 01 ogni anno).", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    cols = [("N. ritiro", 24), ("Data", 20), ("Cliente", 48), ("Cod. fiscale", 34), ("Articolo / IMEI", 62), ("Valore ritiro", 24), ("Stato / N. fattura", 40), ("Doc.", 16)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(226, 232, 240)
    for t, w in cols:
        pdf.cell(w, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    tot_val, n_vend, tot_vend = 0.0, 0, 0.0
    for r in ritiri:
        art = f"{r.get('articolo', '')}"
        if r.get("imei"):
            art += f" / {r['imei']}"
        vals = [r.get("numero", ""), _fmt_it(r.get("data_ritiro")), f"{r.get('cognome', '')} {r.get('nome', '')}".strip(),
                r.get("codice_fiscale", ""), art[:48], _eur(r.get("prezzo_ritiro")), _stato_testo(r)[:34], str(len(r.get("documenti") or []) + 1)]
        for (t, w), v in zip(cols, vals):
            pdf.cell(w, 6.5, str(v), border=1)
        pdf.ln()
        tot_val += float(r.get("prezzo_ritiro") or 0)
        if (r.get("stato") or "") == "venduto":
            n_vend += 1
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    conteggi = {}
    for r in ritiri:
        st = r.get("stato") or ("in_vendita" if r.get("crea_rigenerato", True) else "ritirato")
        conteggi[st] = conteggi.get(st, 0) + 1
    riepilogo = " - ".join(f"{RITIRO_STATO_LABEL[k]}: {v}" for k, v in conteggi.items())
    pdf.cell(0, 6, f"Totale ritiri: {len(ritiri)} - Valore complessivo ritiri: {_eur(tot_val)} - {riepilogo}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 6, "Allegati: bolla di ritiro con numero ritiro e documenti del cliente per ogni riga (vedi ZIP).", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


async def _genera_report(store_id: str, anno: int, mese: int) -> dict:
    db = _d["db"]
    store = await db.stores.find_one({"id": store_id}, {"_id": 0})
    if not store:
        raise HTTPException(status_code=404, detail="Negozio non trovato")
    ritiri = await _ritiri_mese(store_id, anno, mese)
    pdf = _report_pdf(store, anno, mese, ritiri)
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"Report_ritiri_{store['nome']}_{anno}-{mese:02d}.pdf", pdf)
        for r in ritiri:
            try:
                data, _ = _d["get_object"](r["storage_path"])
                z.writestr(f"bolle/{r['numero'].replace('/', '-')}_{r.get('cognome', '')}.pdf", data)
            except Exception:
                continue
    return {"store": store, "ritiri": ritiri, "pdf": pdf, "zip": zbuf.getvalue()}


def _token_path(kind: str, store_nome: str, anno: int, mese: int, ext: str) -> str:
    return f"{_d['app_name']}/report_ritiri/{store_nome}_{anno}-{mese:02d}_{kind}_{uuid.uuid4().hex[:8]}.{ext}"


async def _pubblica_file(data: bytes, path: str, content_type: str, filename: str) -> str:
    db = _d["db"]
    res = _d["put_object"](path, data, content_type)
    token = uuid.uuid4().hex
    await db.report_download.insert_one({"token": token, "path": res["path"], "content_type": content_type, "filename": filename,
                                         "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                                         "created_at": datetime.now(timezone.utc).isoformat()})
    return f"{os.environ.get('FRONTEND_URL', '').rstrip('/')}/api/public/report/{token}"


@router.get("/public/report/{token}")
async def public_report_download(token: str):
    db = _d["db"]
    doc = await db.report_download.find_one({"token": token}, {"_id": 0})
    if not doc or doc["expires_at"] < datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=404, detail="Link scaduto o non valido")
    data, _ = _d["get_object"](doc["path"])
    return Response(content=data, media_type=doc["content_type"],
                    headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'})


def _destinatari(store: dict) -> list:
    raw = store.get("email_commercialista") or ""
    return [e.strip() for e in re.split(r"[;,\s]+", raw) if "@" in e]


async def invia_report_mensile(store_id: str, anno: int, mese: int, extra_to: Optional[list] = None, forza: bool = False) -> dict:
    db = _d["db"]
    rep = await _genera_report(store_id, anno, mese)
    store = rep["store"]
    to = _destinatari(store) + (extra_to or [])
    if not to:
        return {"inviato": False, "motivo": "Nessuna email commercialista impostata per il negozio", "ritiri": len(rep["ritiri"])}
    if not rep["ritiri"] and not forza:
        return {"inviato": False, "motivo": "Nessun ritiro nel mese", "ritiri": 0}
    nome = store["nome"]
    link_pdf = await _pubblica_file(rep["pdf"], _token_path("report", nome, anno, mese, "pdf"), "application/pdf", f"Report_ritiri_{nome}_{anno}-{mese:02d}.pdf")
    link_zip = await _pubblica_file(rep["zip"], _token_path("allegati", nome, anno, mese, "zip"), "application/zip", f"Ritiri_{nome}_{anno}-{mese:02d}_bolle_documenti.zip")
    righe = "".join(
        f"<tr><td style='padding:5px 8px;border-bottom:1px solid #e2e8f0'>{escape(r.get('numero', ''))}</td>"
        f"<td style='padding:5px 8px;border-bottom:1px solid #e2e8f0'>{_fmt_it(r.get('data_ritiro'))}</td>"
        f"<td style='padding:5px 8px;border-bottom:1px solid #e2e8f0'>{escape(r.get('cognome', ''))} {escape(r.get('nome', ''))}</td>"
        f"<td style='padding:5px 8px;border-bottom:1px solid #e2e8f0'>{escape(r.get('articolo', ''))}{(' / ' + escape(r['imei'])) if r.get('imei') else ''}</td>"
        f"<td style='padding:5px 8px;border-bottom:1px solid #e2e8f0;text-align:right'>{_eur(r.get('prezzo_ritiro'))}</td>"
        f"<td style='padding:5px 8px;border-bottom:1px solid #e2e8f0'>{escape(_stato_testo(r))}</td></tr>"
        for r in rep["ritiri"])
    html = (f"<div style='font-family:Arial,sans-serif;color:#0f172a'><h2>Registro ritiri usato - {escape(nome)} - {MESI_IT[mese]} {anno}</h2>"
            f"<p>Buongiorno, in allegato (tramite link sicuro, valido 30 giorni) il registro mensile dei ritiri di telefoni usati del negozio <b>{escape(nome)}</b>.</p>"
            f"<p><a href='{link_pdf}' style='display:inline-block;padding:10px 16px;background:#0f172a;color:#fff;border-radius:8px;text-decoration:none'>Scarica il report PDF</a> &nbsp; "
            f"<a href='{link_zip}' style='display:inline-block;padding:10px 16px;background:#334155;color:#fff;border-radius:8px;text-decoration:none'>Scarica bolle + documenti clienti (ZIP)</a></p>"
            f"<table style='border-collapse:collapse;font-size:13px;width:100%'><thead><tr style='background:#e2e8f0'><th style='padding:6px 8px;text-align:left'>N. ritiro</th><th style='padding:6px 8px;text-align:left'>Data</th>"
            f"<th style='padding:6px 8px;text-align:left'>Cliente</th><th style='padding:6px 8px;text-align:left'>Articolo / IMEI</th><th style='padding:6px 8px;text-align:right'>Valore ritiro</th><th style='padding:6px 8px;text-align:left'>Stato / Fattura</th></tr></thead>"
            f"<tbody>{righe or '<tr><td colspan=6 style=padding:8px>Nessun ritiro nel mese</td></tr>'}</tbody></table>"
            f"<p style='font-size:12px;color:#64748b'>Totale ritiri: {len(rep['ritiri'])}. Ogni bolla riporta il numero di ritiro e i documenti del cliente. Report generato automaticamente dal gestionale RS Riparazioni / CambiaOra.</p></div>")
    subject = f"Registro ritiri usato {escape(nome)} - {MESI_IT[mese]} {anno}"
    ids = []
    for dest in to:
        ids.append(await _d["send_email"](to=dest, subject=subject, html=html))
    await db.report_ritiri_log.insert_one({"id": str(uuid.uuid4()), "store_id": store_id, "anno": anno, "mese": mese, "to": to,
                                           "ritiri": len(rep["ritiri"]), "link_pdf": link_pdf, "link_zip": link_zip,
                                           "at": datetime.now(timezone.utc).isoformat()})
    return {"inviato": True, "to": to, "ritiri": len(rep["ritiri"]), "link_pdf": link_pdf, "link_zip": link_zip}


def _mese_precedente(oggi: date) -> tuple:
    primo = oggi.replace(day=1) - timedelta(days=1)
    return primo.year, primo.month


async def invia_report_tutti_negozi() -> list:
    db = _d["db"]
    anno, mese = _mese_precedente(date.today())
    out = []
    async for s in db.stores.find({"email_commercialista": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "nome": 1}):
        if await db.report_ritiri_log.find_one({"store_id": s["id"], "anno": anno, "mese": mese}):
            continue
        try:
            r = await invia_report_mensile(s["id"], anno, mese)
        except Exception as e:
            r = {"inviato": False, "motivo": str(e)}
        out.append({"negozio": s["nome"], **r})
    return out


class ReportInput(BaseModel):
    store_id: str
    anno: int
    mese: int
    email_extra: str = ""


def _solo_ufficio(user: dict) -> None:
    if not (user["role"] in ("admin", "operatore") or user.get("can_view_all")):
        raise HTTPException(status_code=403, detail="Solo admin/ufficio")


@router.get("/ritiri/report-mensile")
async def scarica_report(store_id: str, anno: int, mese: int, formato: str = "pdf", user: dict = _user()):
    _solo_ufficio(user)
    rep = await _genera_report(store_id, anno, mese)
    nome = rep["store"]["nome"]
    if formato == "zip":
        return Response(content=rep["zip"], media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="Ritiri_{nome}_{anno}-{mese:02d}.zip"'})
    return Response(content=rep["pdf"], media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Report_ritiri_{nome}_{anno}-{mese:02d}.pdf"'})


@router.post("/ritiri/report-mensile/invia")
async def invia_report(input: ReportInput, user: dict = _user()):
    _solo_ufficio(user)
    extra = [e.strip() for e in re.split(r"[;,\s]+", input.email_extra) if "@" in e]
    return await invia_report_mensile(input.store_id, input.anno, input.mese, extra_to=extra, forza=True)


@router.get("/ritiri/report-mensile/log")
async def report_log(user: dict = _user()):
    _solo_ufficio(user)
    return await _d["db"].report_ritiri_log.find({}, {"_id": 0}).sort("at", -1).to_list(100)


@router.post("/cron/report-ritiri-mensile")
async def cron_report_ritiri(request: Request, background_tasks: BackgroundTasks):
    import hmac
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not token or not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Non autorizzato")
    background_tasks.add_task(invia_report_tutti_negozi)
    return {"status": "accepted"}
