import io
import re
import uuid
import hashlib
from datetime import datetime, timezone, date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/banche")
_d: dict = {}
CONTI_DEFAULT = [
    {"id": "ditta-intesa-pos", "nome": "Intesa Sanpaolo – conto POS", "entita": "ditta", "tipo": "banca", "pos_di": ["ditta-nexi", "ditta-mypos"]},
    {"id": "ditta-intesa-2", "nome": "Intesa Sanpaolo – conto 2", "entita": "ditta", "tipo": "banca", "pos_di": []},
    {"id": "ditta-mypos", "nome": "myPOS (DHL)", "entita": "ditta", "tipo": "pos", "pos_di": [], "dhl": True},
    {"id": "ditta-nexi", "nome": "Nexi (ditta)", "entita": "ditta", "tipo": "pos", "pos_di": []},
    {"id": "srls-intesa", "nome": "Intesa Sanpaolo – RS Riparazioni SRLS", "entita": "srls", "tipo": "banca", "pos_di": ["srls-nexi"]},
    {"id": "srls-nexi", "nome": "Nexi (SRLS)", "entita": "srls", "tipo": "pos", "pos_di": []},
]
ENTITA_CENTRO = {"ditta": "morbegno+gravedona", "srls": "store:abbe8ad2-8102-4951-b4f7-8db24634a205"}
COL_DATA = ("data contabile", "data operazione", "data valuta", "data transazione", "data", "date", "transaction date")
COL_IMPORTO = ("importo", "amount", "importo transazione", "netto", "importo netto")
COL_DARE = ("uscite", "dare", "addebiti", "debit")
COL_AVERE = ("entrate", "avere", "accrediti", "credit")
COL_DESC = ("descrizione", "descrizione operazione", "causale", "dettagli", "description", "esercente", "merchant", "note")


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


def _num(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("€", "").replace(" ", "")
    if not s or s.lower() == "nan":
        return None
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("()-+")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def _data(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(v).date().isoformat()
    s = str(v).strip()[:19]
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _find_col(cols: list, names: tuple) -> Optional[str]:
    low = {c: str(c).strip().lower() for c in cols}
    for n in names:
        for c, l in low.items():
            if l == n:
                return c
    for n in names:
        for c, l in low.items():
            if n in l:
                return c
    return None


_RE_DATA_IT = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
_RE_DATA_NEXI = re.compile(r"^\d{2}/\d{2}/\d{2}$")
_RE_IMPORTO = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$")


def _pdf_num(s: str) -> Optional[float]:
    s = re.sub(r"[\u2007\s]", "", s).replace("è", "").replace("Û", "")
    s = re.sub(r"[^\d,+\-]", "", s)
    return _num(s)


def _parse_pdf_intesa(doc) -> list:
    """Estratto conto Intesa Sanpaolo PDF: colonne Addebiti/Accrediti distinte dalla posizione X dell'importo."""
    out = []
    for page in doc:
        words = page.get_text("words")
        rows: dict = {}
        for w in words:
            rows.setdefault(round(w[1]), []).append(w)
        ys = sorted(rows)
        x_add = next((w[0] for y in ys for w in rows[y] if w[4] == "Addebiti"), None)
        if x_add is None:
            continue
        for idx, y in enumerate(ys):
            ws = sorted(rows[y], key=lambda w: w[0])
            if not (ws[0][0] < 40 and _RE_DATA_IT.match(ws[0][4])):
                continue
            d = _data(ws[0][4])
            desc_words, amt_words = [], []
            for w in ws:
                if w[0] <= 100 or _RE_DATA_IT.match(w[4]) or w[4] == "*":
                    continue
                if w[0] >= 340:
                    if re.search(r"\d", w[4]):
                        amt_words.append((w[2], w[4]))
                elif "\u2007" in w[4] and re.search(r"\u2007[\d.è]*\d,?$", w[4]):
                    testo, _, num = w[4].partition("\u2007")
                    desc_words.append(testo)
                    amt_words.append((w[2], num))
                else:
                    desc_words.append(w[4])
            if not d or not amt_words:
                continue
            amt = _pdf_num("".join(a[1] for a in amt_words))
            if amt is None or amt == 0:
                continue
            is_addebito = max(a[0] for a in amt_words) < x_add + 60
            if idx + 1 < len(ys):
                nxt = sorted(rows[ys[idx + 1]], key=lambda w: w[0])
                if nxt and nxt[0][0] > 100 and not _RE_DATA_IT.match(nxt[0][4]):
                    desc_words += [re.sub(r"\u2007+", "", w[4]) for w in nxt if w[0] < 340]
            desc = " ".join(x for x in desc_words if x)
            out.append({"data": d, "importo": round(-abs(amt) if is_addebito else abs(amt), 2), "descrizione": desc[:200]})
    return out


def _parse_pdf_nexi(text: str) -> list:
    """Estratto Nexi/Setefi PDF: una riga per gruppo di incassi (lordo) + addebiti commissioni. Gli 'ACCREDITO SU CONTO' si saltano (sono già in banca)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    m = re.search(r"CODICE COMMERCIANTE:\s*(\d+)", text)
    merchant = f"COMM {m.group(1)} " if m else ""
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _RE_DATA_NEXI.match(ln) and i + 4 < len(lines) and lines[i + 1].isdigit() and _RE_IMPORTO.match(lines[i + 2]) and _RE_IMPORTO.match(lines[i + 3]):
            d, n_op, lordo, comm, desc = _data(ln), lines[i + 1], _num(lines[i + 2]), _num(lines[i + 3]), lines[i + 4]
            if d and lordo:
                out.append({"data": d, "importo": round(lordo, 2), "descrizione": f"{merchant}{desc} ({n_op} op., comm. {comm:.2f})"[:200]})
            i += 5
            continue
        if _RE_IMPORTO.match(ln) and i + 2 < len(lines) and _RE_DATA_NEXI.match(lines[i + 1]) and lines[i + 2].startswith("ADDEBITO SU CONTO"):
            d, tot = _data(lines[i + 1]), _num(ln)
            if d and tot:
                out.append({"data": d, "importo": round(-abs(tot), 2), "descrizione": f"{merchant}ADDEBITO COMMISSIONI POS"[:200]})
            i += 3
            continue
        i += 1
    return out


def _parse_pdf_mypos(text: str) -> list:
    """Monthly statement myPOS (POS di DHL): Payment = incasso (+), Fee = commissione (−), 'Request money' = trasferimento a DHL (−)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = []
    i = 0
    while i < len(lines):
        if _RE_DATA_IT.match(lines[i]) and i + 1 < len(lines) and re.match(r"^\d{2}:\d{2}$", lines[i + 1]):
            j = i + 2
            while j < len(lines) and not (_RE_DATA_IT.match(lines[j]) and j + 1 < len(lines) and re.match(r"^\d{2}:\d{2}$", lines[j + 1])) and not lines[j].startswith("myPOS Payments Ltd"):
                j += 1
            blk = lines[i:j]
            nums = [x for x in blk if re.match(r"^\d+\.\d{2}$", x)]
            d = _data(blk[0])
            if d and len(nums) >= 2:
                debit, credit = float(nums[-2]), float(nums[-1])
                testo = " ".join(blk[2:])
                if "Request" in blk[2:6] or "Request money" in testo:
                    out.append({"data": d, "importo": round(-debit, 2), "descrizione": f"myPOS trasferimento a DHL {blk[1]}"[:200]})
                elif credit > 0:
                    m = re.search(r"TID\s*(\d+)", testo)
                    out.append({"data": d, "importo": round(credit, 2), "descrizione": f"myPOS Payment{' TID ' + m.group(1) if m else ''} {blk[1]}"[:200]})
                elif debit > 0 and "Fee" in blk[2:5]:
                    out.append({"data": d, "importo": round(-debit, 2), "descrizione": f"myPOS commissione {blk[1]}"[:200]})
            i = j
            continue
        i += 1
    return out


def _parse_pdf(content: bytes) -> list:
    import pymupdf
    doc = pymupdf.open(stream=content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    if "myPOS" in text and "Monthly statement" in text:
        return _parse_pdf_mypos(text)
    if "SERVIZIO DI INCASSO CARTE" in text or "MOVIMENTI LIQUIDATI" in text:
        return _parse_pdf_nexi(text)
    if "Dettaglio movimenti del conto corrente" in text or "INTESA" in text.upper():
        return _parse_pdf_intesa(doc)
    raise ValueError("PDF non riconosciuto (supportati: estratto Intesa Sanpaolo, Nexi/Setefi, myPOS)")


def parse_estratto(content: bytes, filename: str) -> list:
    """Legge CSV/XLSX/PDF di Intesa, Nexi, myPOS: trova da solo le colonne data/importo/descrizione."""
    name = filename.lower()
    frames = []
    if name.endswith(".pdf") or content[:4] == b"%PDF":
        return _parse_pdf(content)
    if name.endswith((".xlsx", ".xls")):
        xls = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
        frames = list(xls.values())
    else:
        text = content.decode("utf-8-sig", errors="ignore")
        sep = ";" if text.count(";") > text.count(",") else ","
        frames = [pd.read_csv(io.StringIO(text), sep=sep, header=None, dtype=str, engine="python", on_bad_lines="skip")]
    out = []
    for raw in frames:
        header_idx = None
        for i in range(min(len(raw), 40)):
            vals = [str(x).strip().lower() for x in raw.iloc[i].tolist()]
            if any(any(k == v or k in v for k in COL_DATA) for v in vals) and any(any(k in v for k in COL_IMPORTO + COL_DARE + COL_AVERE) for v in vals):
                header_idx = i
                break
        if header_idx is None:
            continue
        df = raw.iloc[header_idx + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[header_idx].tolist()]
        cols = list(df.columns)
        c_data, c_imp, c_dare, c_avere, c_desc = _find_col(cols, COL_DATA), _find_col(cols, COL_IMPORTO), _find_col(cols, COL_DARE), _find_col(cols, COL_AVERE), _find_col(cols, COL_DESC)
        for _, r in df.iterrows():
            d = _data(r.get(c_data))
            if not d:
                continue
            if c_imp is not None:
                imp = _num(r.get(c_imp))
            else:
                imp = (_num(r.get(c_avere)) or 0) - abs(_num(r.get(c_dare)) or 0) if (c_dare or c_avere) else None
            if imp is None or imp == 0:
                continue
            desc = str(r.get(c_desc) or "").strip() if c_desc else ""
            out.append({"data": d, "importo": round(imp, 2), "descrizione": desc[:200]})
    return out


@router.get("/conti")
async def conti(user: dict = Depends(require_admin)):
    db = _d["db"]
    out = []
    for c in CONTI_DEFAULT:
        n = await db.movimenti_banca.count_documents({"conto_id": c["id"]})
        ultimo = await db.movimenti_banca.find_one({"conto_id": c["id"]}, {"_id": 0, "data": 1}, sort=[("data", -1)])
        out.append({**c, "movimenti": n, "ultimo_movimento": (ultimo or {}).get("data")})
    return out


@router.post("/upload")
async def upload(conto_id: str = Form(...), file: UploadFile = File(...), user: dict = Depends(require_admin)):
    if conto_id not in {c["id"] for c in CONTI_DEFAULT}:
        raise HTTPException(status_code=400, detail="Conto non valido")
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 15 MB)")
    try:
        righe = parse_estratto(content, file.filename or "estratto.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File non leggibile: {e}")
    if not righe:
        raise HTTPException(status_code=400, detail="Nessun movimento trovato: controlla che il file abbia colonne data e importo (o entrate/uscite)")
    db = _d["db"]
    nuovi, doppi = 0, 0
    estratto_id = str(uuid.uuid4())
    # Stessa transazione ripetuta nello stesso file (es. due scontrini uguali) è legittima: il progressivo la distingue; il dedup vale solo contro i caricamenti precedenti
    visti: dict = {}
    for r in righe:
        base = f"{conto_id}|{r['data']}|{r['importo']}|{r['descrizione'].lower()}"
        visti[base] = visti.get(base, 0) + 1
        h = hashlib.sha1(f"{base}|{visti[base]}".encode()).hexdigest()
        if await db.movimenti_banca.find_one({"hash": h}):
            doppi += 1
            continue
        await db.movimenti_banca.insert_one({"id": str(uuid.uuid4()), "hash": h, "conto_id": conto_id, **r, "file": file.filename, "estratto_id": estratto_id, "caricato_da": user["name"], "created_at": _now().isoformat()})
        nuovi += 1
    date_ = sorted(r["data"] for r in righe)
    if nuovi:
        await db.estratti_caricati.insert_one({"id": estratto_id, "conto_id": conto_id, "file": file.filename, "righe": len(righe), "nuovi": nuovi, "doppi": doppi,
                                           "dal": date_[0], "al": date_[-1], "da": user["name"], "at": _now().isoformat()})
    return {"righe": len(righe), "nuovi": nuovi, "gia_presenti": doppi, "dal": date_[0], "al": date_[-1]}


@router.get("/movimenti")
async def movimenti(conto_id: str, anno: int, mese: int, user: dict = Depends(require_admin)):
    pref = f"{anno:04d}-{mese:02d}"
    items = await _d["db"].movimenti_banca.find({"conto_id": conto_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "hash": 0}).sort("data", 1).to_list(5000)
    return {"items": items, "entrate": round(sum(i["importo"] for i in items if i["importo"] > 0), 2), "uscite": round(-sum(i["importo"] for i in items if i["importo"] < 0), 2)}


def _is_pos_accredito(desc: str) -> bool:
    d = desc.lower()
    if any(k in d for k in ("anticipo per transato", "giroconto", "a favore del c/c", "da c/c")):
        return False  # trasferimenti tra i propri conti: non sono incassi
    return any(k in d for k in ("nexi", "mypos", "my pos", "pos ", "cartasi", "accredito pos", "incasso pos"))


@router.get("/riconciliazione")
async def riconciliazione(entita: str, anno: int, mese: int, user: dict = Depends(require_admin)):
    """POS: chiusure (dichiarato) vs transazioni Nexi/myPOS vs accrediti in banca. Uscite banca vs fatture AdE ricevute. Solo controllo: nulla viene sommato ai ricavi."""
    db = _d["db"]
    if entita not in ENTITA_CENTRO:
        raise HTTPException(status_code=400, detail="Entità non valida (ditta|srls)")
    pref = f"{anno:04d}-{mese:02d}"
    conti = [c for c in CONTI_DEFAULT if c["entita"] == entita]
    banche = [c for c in conti if c["tipo"] == "banca"]
    pos_ids = [c["id"] for c in conti if c["tipo"] == "pos" and not c.get("dhl")]
    dhl_ids = [c["id"] for c in conti if c.get("dhl")]
    centro = next(c for c in await _d["centri_tutti"]() if c["id"] == ENTITA_CENTRO[entita])
    giorni: dict = {}
    async for c in db.corrispettivi.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "pos": 1}):
        g = giorni.setdefault(c["data"], {"data": c["data"], "pos_chiusure": 0.0, "pos_transazioni": 0.0, "accrediti_banca": 0.0})
        g["pos_chiusure"] = round(g["pos_chiusure"] + float(c.get("pos") or 0), 2)
    async for m in db.movimenti_banca.find({"conto_id": {"$in": pos_ids}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "importo": 1, "conto_id": 1}):
        if m["importo"] > 0:
            g = giorni.setdefault(m["data"], {"data": m["data"], "pos_chiusure": 0.0, "pos_transazioni": 0.0, "accrediti_banca": 0.0})
            g["pos_transazioni"] = round(g["pos_transazioni"] + m["importo"], 2)
            g.setdefault("per_pos", {})
            g["per_pos"][m["conto_id"]] = round(g["per_pos"].get(m["conto_id"], 0) + m["importo"], 2)
    uscite_banca = []
    async for m in db.movimenti_banca.find({"conto_id": {"$in": [b["id"] for b in banche]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "hash": 0}):
        if m["importo"] > 0 and _is_pos_accredito(m.get("descrizione", "")):
            g = giorni.setdefault(m["data"], {"data": m["data"], "pos_chiusure": 0.0, "pos_transazioni": 0.0, "accrediti_banca": 0.0})
            g["accrediti_banca"] = round(g["accrediti_banca"] + m["importo"], 2)
        elif m["importo"] < 0:
            uscite_banca.append(m)
    righe = sorted(giorni.values(), key=lambda g: g["data"])
    for g in righe:
        g["diff_transazioni"] = round(g["pos_transazioni"] - g["pos_chiusure"], 2)
        g["ok"] = abs(g["diff_transazioni"]) < 1.0 if g["pos_transazioni"] else None  # None = transazioni POS non caricate
    tot = {k: round(sum(g[k] for g in righe), 2) for k in ("pos_chiusure", "pos_transazioni", "accrediti_banca")}
    tot["per_pos"] = {p: round(sum((g.get("per_pos") or {}).get(p, 0) for g in righe), 2) for p in pos_ids}
    tot["commissioni_stimate"] = round(tot["pos_transazioni"] - tot["accrediti_banca"], 2) if tot["accrediti_banca"] else None
    # uscite banca ↔ fatture ricevute AdE (stesso importo, tolleranza 1 cent)
    fatture = await db.fatture_ade.find({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "ricevute"}, {"_id": 0, "id": 1, "controparte": 1, "totale": 1, "data": 1}).to_list(2000)
    pagate, non_trovate = [], []
    usate = set()
    for f in fatture:
        tot_f = float(f.get("totale") or 0)
        m = next((u for u in uscite_banca if u["id"] not in usate and abs(abs(u["importo"]) - tot_f) < 0.01), None)
        if m:
            usate.add(m["id"])
            pagate.append({"fattura": f, "movimento": m})
        else:
            non_trovate.append(f)
    altre_uscite = [u for u in uscite_banca if u["id"] not in usate]
    # fatture non in banca: pagamenti segnati a mano (contanti/carta/altro) + suggerimenti dalle spese contanti delle chiusure (stesso importo)
    pag_manuali = {p["fattura_id"]: p async for p in db.fatture_pagamenti.find({"fattura_id": {"$in": [f["id"] for f in non_trovate]}}, {"_id": 0})}
    spese = await db.spese_cassa.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0}).to_list(2000)
    spese_usate = {p["spesa_cassa_id"] for p in pag_manuali.values() if p.get("spesa_cassa_id")}
    pagate_altro, ancora_aperte = [], []
    for f in non_trovate:
        p = pag_manuali.get(f["id"])
        if p:
            pagate_altro.append({"fattura": f, "pagamento": p})
            continue
        sug = next((s for s in spese if s["id"] not in spese_usate and abs(float(s.get("importo") or 0) - float(f.get("totale") or 0)) < 0.01), None)
        if sug:
            spese_usate.add(sug["id"])
        ancora_aperte.append({**f, "suggerimento_contanti": sug})
    non_trovate = ancora_aperte
    # myPOS = POS di proprietà DHL: non sono incassi nostri (fatturiamo a DHL). Controllo: incassi = trasferiti a DHL + commissioni
    dhl = None
    if dhl_ids:
        mv = await db.movimenti_banca.find({"conto_id": {"$in": dhl_ids}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "importo": 1, "descrizione": 1}).to_list(5000)
        inc = round(sum(m["importo"] for m in mv if m["importo"] > 0), 2)
        tra = round(-sum(m["importo"] for m in mv if m["importo"] < 0 and "trasferimento" in m["descrizione"].lower()), 2)
        com = round(-sum(m["importo"] for m in mv if m["importo"] < 0 and "commissione" in m["descrizione"].lower()), 2)
        dhl = {"incassato": inc, "trasferito_dhl": tra, "commissioni": com, "saldo": round(inc - tra - com, 2), "operazioni": sum(1 for m in mv if m["importo"] > 0), "ok": abs(inc - tra - com) < 1.0 if mv else None,
               "nota": "POS DHL: incassi non contabilizzati (si fattura a DHL). Deve tornare: incassato = trasferito a DHL + commissioni."}
    caricati = await db.estratti_caricati.find({"conto_id": {"$in": [c["id"] for c in conti]}, "al": {"$gte": f"{pref}-01"}, "dal": {"$lte": f"{pref}-31"}}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"entita": entita, "centro": centro["nome"], "conti": conti, "giorni": righe, "totali": tot, "fatture_pagate": pagate, "fatture_non_trovate_in_banca": non_trovate, "fatture_pagate_altro": pagate_altro,
            "altre_uscite_banca": sorted(altre_uscite, key=lambda u: u["data"]), "estratti_caricati": caricati, "dhl": dhl,
            "nota": "I POS si contano UNA sola volta (dal dichiarato nelle chiusure); transazioni Nexi/myPOS e accrediti in banca servono solo da controllo."}


@router.delete("/estratti/{estratto_id}")
async def elimina_estratto(estratto_id: str, user: dict = Depends(require_admin)):
    db = _d["db"]
    e = await db.estratti_caricati.find_one({"id": estratto_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Caricamento non trovato")
    res = await db.movimenti_banca.delete_many({"estratto_id": estratto_id})
    await db.estratti_caricati.delete_one({"id": estratto_id})
    return {"eliminati": res.deleted_count}



class PagamentoInput(BaseModel):
    modo: str = "contanti"  # contanti | carta | altro
    spesa_cassa_id: str = ""
    nota: str = ""


@router.post("/fatture/{fattura_id}/pagamento")
async def segna_pagamento(fattura_id: str, body: PagamentoInput, user: dict = Depends(require_admin)):
    """Segna una fattura ricevuta AdE come pagata fuori banca (contanti/carta/altro), opzionalmente agganciata a una spesa contanti delle chiusure."""
    db = _d["db"]
    if body.modo not in ("contanti", "carta", "altro"):
        raise HTTPException(status_code=400, detail="Modo non valido")
    f = await db.fatture_ade.find_one({"id": fattura_id}, {"_id": 0, "controparte": 1, "totale": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    doc = {"fattura_id": fattura_id, "modo": body.modo, "spesa_cassa_id": body.spesa_cassa_id or None, "nota": body.nota, "importo": f.get("totale"), "controparte": f.get("controparte"), "by": user["name"], "at": _now().isoformat()}
    if body.spesa_cassa_id:
        sp = await db.spese_cassa.find_one({"id": body.spesa_cassa_id}, {"_id": 0, "data": 1, "motivo": 1, "importo": 1})
        if not sp:
            raise HTTPException(status_code=404, detail="Spesa contanti non trovata")
        doc["spesa"] = sp
    await db.fatture_pagamenti.update_one({"fattura_id": fattura_id}, {"$set": doc}, upsert=True)
    return {"ok": True, **doc}


@router.delete("/fatture/{fattura_id}/pagamento")
async def annulla_pagamento(fattura_id: str, user: dict = Depends(require_admin)):
    res = await _d["db"].fatture_pagamenti.delete_one({"fattura_id": fattura_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Nessun pagamento segnato")
    return {"ok": True}
