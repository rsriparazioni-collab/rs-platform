import csv
import hashlib
import io
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/contabilita/pdp/fatture")
_d: dict = {}

KEYS = {
    "tipo": ("tipo documento", "tipo doc", "tipodocumento", "tipo"),
    "numero": ("numero fattura", "numero documento", "numero fattura / documento", "numero", "n. documento", "n° documento"),
    "data": ("data emissione", "data documento", "data ricezione", "data fattura", "data"),
    "controparte": ("denominazione", "cliente", "fornitore", "ragione sociale", "controparte", "cedente", "cessionario", "partita iva"),
    "imponibile": ("imponibile", "importo imponibile", "imponibile/importo", "imponibile / importo", "importo"),
    "imposta": ("imposta", "iva", "importo iva"),
    "totale": ("totale", "importo totale", "totale documento", "totale fattura"),
    "natura": ("natura", "natura iva", "natura operazione", "codice natura"),
}


def setup(**deps):
    _d.update(deps)


def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).replace("€", "").replace(" ", "").strip()
    if not s:
        return 0.0
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _data(v) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    s = str(v or "").strip()
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", s)
    if m:
        a = int(m.group(3))
        return f"{a if a > 100 else 2000 + a:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else ""


def _rows(filename: str, content: bytes) -> list:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        return [["" if c is None else c for c in r] for r in ws.iter_rows(values_only=True)]
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4000]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    if sample.count("\t") > max(sample.count(";"), sample.count(",")):
        delim = "\t"
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def _mappa(header: list) -> dict:
    low = [str(h or "").strip().lower() for h in header]
    idx = {}
    for key, cands in KEYS.items():
        for cand in cands:
            for i, h in enumerate(low):
                if i in idx.values():
                    continue
                if h == cand or (len(cand) > 4 and cand in h):
                    idx[key] = i
                    break
            if key in idx:
                break
    return idx


def parse_fatture(filename: str, content: bytes) -> dict:
    rows = _rows(filename, content)
    hi, idx = None, {}
    for i, r in enumerate(rows[:30]):
        m = _mappa(r)
        if ("numero" in m or "controparte" in m) and ("imponibile" in m or "totale" in m):
            hi, idx = i, m
            break
    if hi is None:
        raise HTTPException(status_code=400, detail="Intestazione non riconosciuta: servono almeno le colonne Numero/Denominazione e Imponibile/Totale")
    out = []
    for r in rows[hi + 1:]:
        r = list(r) + [""] * 20
        get = lambda k: r[idx[k]] if k in idx else ""
        imp, iva = _num(get("imponibile")), _num(get("imposta"))
        tot = _num(get("totale")) or round(imp + iva, 2)
        numero = str(get("numero") or "").strip().strip("'")
        if not numero and not tot:
            continue
        tipo = str(get("tipo") or "").strip()
        if is_nota_credito(tipo) and tot > 0:
            imp, iva, tot = -imp, -iva, -tot
        riga = {"tipo": tipo[:40] or "Fattura", "numero": numero[:40], "data": _data(get("data")), "controparte": str(get("controparte") or "").strip()[:80],
                "imponibile": imp, "imposta": iva, "totale": tot, "natura_raw": str(get("natura") or "").strip()[:20]}
        riga["natura_iva"] = natura_iva(riga)
        out.append(riga)
    return {"colonne": {k: str(rows[hi][i]) for k, i in idx.items()}, "righe": out}


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def totali_mese(centro_id: str, anno: int, mese: int) -> dict:
    """Totali fiscali del mese: lordo, imponibile, imposta per direzione + note di credito separate."""
    out = {"emesse": 0.0, "ricevute": 0.0, "n_emesse": 0, "n_ricevute": 0,
           "emesse_imponibile": 0.0, "emesse_imposta": 0.0, "ricevute_imponibile": 0.0, "ricevute_imposta": 0.0,
           "note_credito_emesse": {"n": 0, "imponibile": 0.0, "imposta": 0.0, "totale": 0.0}, "note_credito_ricevute": {"n": 0, "imponibile": 0.0, "imposta": 0.0, "totale": 0.0}}
    async for f in _d["db"].fatture_ade.find({"centro_id": centro_id, "anno": anno, "mese": mese}, {"_id": 0, "direzione": 1, "totale": 1, "imponibile": 1, "imposta": 1, "tipo": 1}):
        d = f["direzione"]
        out[d] = round(out[d] + (f.get("totale") or 0), 2)
        out[d + "_imponibile"] = round(out[d + "_imponibile"] + (f.get("imponibile") or 0), 2)
        out[d + "_imposta"] = round(out[d + "_imposta"] + (f.get("imposta") or 0), 2)
        out["n_" + d] += 1
        if is_nota_credito(f.get("tipo", "")):
            nc = out["note_credito_" + d]
            nc["n"] += 1
            for k in ("imponibile", "imposta", "totale"):
                nc[k] = round(nc[k] + (f.get(k) or 0), 2)
    return out


def is_nota_credito(tipo: str) -> bool:
    return bool(re.search(r"nota di credito|TD04|TD08", tipo or "", re.I))


NATURE = {"N1": "esclusa", "N2": "non_soggetta", "N3": "non_imponibile", "N4": "esente", "N5": "regime_margine", "N6": "reverse_charge", "N7": "iva_altro_stato"}
NATURE_VALIDE = set(NATURE.values()) | {"forfettario", "da_verificare", "imponibile"}


def natura_iva(r: dict) -> str:
    """Stato della natura IVA: dedotto dal codice N1..N7 se presente, altrimenti 'da_verificare' per IVA zero. Mai assegnato automaticamente."""
    raw = str(r.get("natura_raw") or "").strip().upper()
    m = re.match(r"^(N[1-7])", raw)
    if m:
        return NATURE[m.group(1)]
    if re.search(r"forfett", raw, re.I) or re.search(r"forfett", str(r.get("tipo") or ""), re.I):
        return "forfettario"
    if abs(float(r.get("imposta") or 0)) < 0.005 and abs(float(r.get("imponibile") or 0)) >= 0.005:
        return "da_verificare"
    return "imponibile"


def _norm_num(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def riconcilia_manuali(manuali: list, ade_emesse: list) -> tuple:
    """Fatture scritte nelle chiusure ↔ fatture emesse AdE: match per numero, altrimenti per importo (±0,01). Ritorna (riconciliate, non_riconciliate)."""
    usati: set = set()
    ric, non = [], []
    by_num = {}
    for i, a in enumerate(ade_emesse):
        by_num.setdefault(_norm_num(a.get("numero")), []).append(i)
    for m in manuali:
        idx = None
        for i in by_num.get(_norm_num(m.get("numero")), []):
            if i not in usati and _norm_num(m.get("numero")):
                idx = i
                break
        if idx is None:
            for i, a in enumerate(ade_emesse):
                if i not in usati and abs(float(a.get("totale") or 0) - float(m.get("importo") or 0)) < 0.01:
                    idx = i
                    break
        if idx is None:
            non.append({**m, "fonte": "chiusura_manuale"})
        else:
            usati.add(idx)
            ric.append({**m, "ade_numero": ade_emesse[idx].get("numero"), "ade_totale": ade_emesse[idx].get("totale"), "match": "numero" if _norm_num(m.get("numero")) == _norm_num(ade_emesse[idx].get("numero")) else "importo"})
    return ric, non


class AnteprimaInput(BaseModel):
    righe: list
    colonne: dict = {}


@router.post("/anteprima")
async def anteprima(centro_id: str, anno: int, mese: int, direzione: str, request: Request, file: UploadFile = File(...)):
    """Legge il file AdE e restituisce colonne riconosciute, righe, duplicati e anomalie SENZA salvare."""
    user = await _user(request)
    await _d["centro"](user, centro_id)
    if direzione not in ("emesse", "ricevute"):
        raise HTTPException(status_code=400, detail="direzione: emesse|ricevute")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 10 MB)")
    parsed = parse_fatture(file.filename or "file.csv", content)
    db = _d["db"]
    righe, n_dup, fuori_mese, anomalie = [], 0, 0, 0
    for r in parsed["righe"]:
        h = _hash(centro_id, direzione, r)
        dup = bool(await db.fatture_ade.find_one({"hash": h}, {"_id": 1}))
        n_dup += dup
        note = []
        if r["data"] and r["data"][:7] != f"{anno:04d}-{mese:02d}":
            note.append("data fuori dal mese selezionato"); fuori_mese += 1
        if abs(r["imponibile"] + r["imposta"] - r["totale"]) > 0.05:
            note.append("imponibile+IVA ≠ totale")
        if r["imponibile"] and not r["imposta"]:
            note.append("senza IVA")
        if not r["controparte"]:
            note.append("controparte mancante")
        anomalie += bool(note)
        righe.append({**r, "hash": h, "duplicato": dup, "note": note})
    tot = {"imponibile": round(sum(r["imponibile"] for r in righe if not r["duplicato"]), 2), "imposta": round(sum(r["imposta"] for r in righe if not r["duplicato"]), 2),
           "totale": round(sum(r["totale"] for r in righe if not r["duplicato"]), 2)}
    return {"colonne": parsed["colonne"], "righe": righe, "n": len(righe), "duplicati": n_dup, "fuori_mese": fuori_mese, "con_anomalie": anomalie, "totali_nuove": tot, "file": file.filename}


@router.post("/conferma")
async def conferma(centro_id: str, anno: int, mese: int, direzione: str, body: AnteprimaInput, request: Request):
    """Salva le righe verificate dell'anteprima (solo non duplicate)."""
    user = await _user(request)
    await _d["centro"](user, centro_id)
    if direzione not in ("emesse", "ricevute"):
        raise HTTPException(status_code=400, detail="direzione: emesse|ricevute")
    db = _d["db"]
    now = datetime.now(timezone.utc).isoformat()
    nuove, dup = 0, 0
    for r in body.righe:
        h = _hash(centro_id, direzione, r)
        if await db.fatture_ade.find_one({"hash": h}, {"_id": 1}):
            dup += 1
            continue
        await db.fatture_ade.insert_one({"id": str(uuid.uuid4()), "hash": h, "centro_id": centro_id, "anno": anno, "mese": mese, "direzione": direzione,
                                         "tipo": str(r.get("tipo") or "Fattura")[:40], "numero": str(r.get("numero") or "")[:40], "data": str(r.get("data") or "")[:10],
                                         "controparte": str(r.get("controparte") or "")[:80], "imponibile": float(r.get("imponibile") or 0), "imposta": float(r.get("imposta") or 0),
                                         "totale": float(r.get("totale") or 0), "natura_raw": str(r.get("natura_raw") or "")[:20], "natura_iva": r.get("natura_iva") if r.get("natura_iva") in NATURE_VALIDE else natura_iva(r),
                                         "file": "import verificato", "fonte": "excel_ade", "created_at": now, "created_by": user.get("name", "")})
        nuove += 1
    return {"importate": nuove, "duplicate": dup, "totali": await totali_mese(centro_id, anno, mese)}


class NaturaInput(BaseModel):
    natura_iva: str
    nota: str = ""


@router.patch("/{fid}/natura")
async def set_natura(fid: str, body: NaturaInput, request: Request):
    """Verifica manuale della natura IVA di un documento a IVA zero."""
    user = await _user(request)
    if body.natura_iva not in NATURE_VALIDE:
        raise HTTPException(status_code=400, detail=f"natura_iva: {', '.join(sorted(NATURE_VALIDE))}")
    f = await _d["db"].fatture_ade.find_one({"id": fid}, {"_id": 0, "centro_id": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Documento non trovato")
    await _d["centro"](user, f["centro_id"])
    await _d["db"].fatture_ade.update_one({"id": fid}, {"$set": {"natura_iva": body.natura_iva, "natura_nota": body.nota[:200], "natura_verificata_da": user.get("name", ""), "natura_verificata_at": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}


def _hash(centro_id: str, direzione: str, r: dict) -> str:
    return hashlib.sha1(f"{centro_id}|{direzione}|{r.get('numero', '')}|{r.get('data', '')}|{r.get('controparte', '')}|{float(r.get('totale') or 0)}".lower().encode()).hexdigest()


@router.post("/importa")
async def importa(centro_id: str, anno: int, mese: int, direzione: str, request: Request, file: UploadFile = File(...)):
    user = await _user(request)
    await _d["centro"](user, centro_id)
    if direzione not in ("emesse", "ricevute"):
        raise HTTPException(status_code=400, detail="direzione: emesse|ricevute")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 10 MB)")
    parsed = parse_fatture(file.filename or "file.csv", content)
    db = _d["db"]
    now = datetime.now(timezone.utc).isoformat()
    nuove, dup = 0, 0
    for r in parsed["righe"]:
        h = hashlib.sha1(f"{centro_id}|{direzione}|{r['numero']}|{r['data']}|{r['controparte']}|{r['totale']}".lower().encode()).hexdigest()
        if await db.fatture_ade.find_one({"hash": h}, {"_id": 1}):
            dup += 1
            continue
        await db.fatture_ade.insert_one({**r, "id": str(uuid.uuid4()), "hash": h, "centro_id": centro_id, "anno": anno, "mese": mese, "direzione": direzione,
                                         "file": (file.filename or "")[:80], "created_at": now, "created_by": user.get("name", "")})
        nuove += 1
    return {"importate": nuove, "duplicate": dup, "colonne": parsed["colonne"], "totali": await totali_mese(centro_id, anno, mese)}


@router.get("")
async def lista(centro_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    await _d["centro"](user, centro_id)
    righe = await _d["db"].fatture_ade.find({"centro_id": centro_id, "anno": anno, "mese": mese}, {"_id": 0, "hash": 0}).sort([("direzione", 1), ("data", -1)]).to_list(5000)
    return {"righe": righe, "totali": await totali_mese(centro_id, anno, mese)}


@router.delete("/{fid}")
async def elimina(fid: str, request: Request):
    user = await _user(request)
    f = await _d["db"].fatture_ade.find_one({"id": fid}, {"_id": 0, "centro_id": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    await _d["centro"](user, f["centro_id"])
    await _d["db"].fatture_ade.delete_one({"id": fid})
    return {"ok": True}


@router.delete("")
async def svuota(centro_id: str, anno: int, mese: int, direzione: str, request: Request):
    user = await _user(request)
    await _d["centro"](user, centro_id)
    r = await _d["db"].fatture_ade.delete_many({"centro_id": centro_id, "anno": anno, "mese": mese, "direzione": direzione})
    return {"eliminate": r.deleted_count}
