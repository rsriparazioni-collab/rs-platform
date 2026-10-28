import io
import uuid
import hashlib
from datetime import datetime, timezone, date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix="/banche")
_d: dict = {}
CONTI_DEFAULT = [
    {"id": "ditta-intesa-pos", "nome": "Intesa Sanpaolo – conto POS", "entita": "ditta", "tipo": "banca", "pos_di": ["ditta-nexi", "ditta-mypos"]},
    {"id": "ditta-intesa-2", "nome": "Intesa Sanpaolo – conto 2", "entita": "ditta", "tipo": "banca", "pos_di": []},
    {"id": "ditta-mypos", "nome": "myPOS (ditta)", "entita": "ditta", "tipo": "pos", "pos_di": []},
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


def parse_estratto(content: bytes, filename: str) -> list:
    """Legge CSV/XLSX di Intesa, Nexi, myPOS: trova da solo le colonne data/importo/descrizione."""
    name = filename.lower()
    frames = []
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
    pos_ids = [c["id"] for c in conti if c["tipo"] == "pos"]
    centro = next(c for c in await _d["centri_tutti"]() if c["id"] == ENTITA_CENTRO[entita])
    giorni: dict = {}
    async for c in db.corrispettivi.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "pos": 1}):
        g = giorni.setdefault(c["data"], {"data": c["data"], "pos_chiusure": 0.0, "pos_transazioni": 0.0, "accrediti_banca": 0.0})
        g["pos_chiusure"] = round(g["pos_chiusure"] + float(c.get("pos") or 0), 2)
    async for m in db.movimenti_banca.find({"conto_id": {"$in": pos_ids}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "importo": 1}):
        if m["importo"] > 0:
            g = giorni.setdefault(m["data"], {"data": m["data"], "pos_chiusure": 0.0, "pos_transazioni": 0.0, "accrediti_banca": 0.0})
            g["pos_transazioni"] = round(g["pos_transazioni"] + m["importo"], 2)
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
    caricati = await db.estratti_caricati.find({"conto_id": {"$in": [c["id"] for c in conti]}, "al": {"$gte": f"{pref}-01"}, "dal": {"$lte": f"{pref}-31"}}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"entita": entita, "centro": centro["nome"], "conti": conti, "giorni": righe, "totali": tot, "fatture_pagate": pagate, "fatture_non_trovate_in_banca": non_trovate,
            "altre_uscite_banca": sorted(altre_uscite, key=lambda u: u["data"]), "estratti_caricati": caricati,
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
