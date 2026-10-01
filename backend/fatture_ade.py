import csv
import hashlib
import io
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

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
        if re.search(r"nota di credito|TD04|TD08", tipo, re.I) and tot > 0:
            imp, iva, tot = -imp, -iva, -tot
        out.append({"tipo": tipo[:40] or "Fattura", "numero": numero[:40], "data": _data(get("data")), "controparte": str(get("controparte") or "").strip()[:80],
                    "imponibile": imp, "imposta": iva, "totale": tot})
    return {"colonne": {k: str(rows[hi][i]) for k, i in idx.items()}, "righe": out}


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def totali_mese(centro_id: str, anno: int, mese: int) -> dict:
    out = {"emesse": 0.0, "ricevute": 0.0, "n_emesse": 0, "n_ricevute": 0}
    async for f in _d["db"].fatture_ade.find({"centro_id": centro_id, "anno": anno, "mese": mese}, {"_id": 0, "direzione": 1, "totale": 1}):
        out[f["direzione"]] = round(out[f["direzione"]] + f["totale"], 2)
        out["n_" + f["direzione"]] += 1
    return out


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
