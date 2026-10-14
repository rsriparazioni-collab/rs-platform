"""Corrispettivi telematici AdE: import CSV/XLSX (consultazione) o ZIP/XML (download massivo), abbinati al negozio per matricola RT."""
import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from fatture_ade import _rows, _num, _data

router = APIRouter(prefix="/contabilita/corrispettivi-ade")
_d: dict = {}

KEYS = {
    "matricola": ("matricola", "matricola dispositivo", "id dispositivo", "dispositivo", "identificativo dispositivo", "rt"),
    "data": ("data rilevazione", "data e ora rilevazione", "data chiusura", "data trasmissione", "data e ora trasmissione", "data invio", "data"),
    "imponibile": ("totale imponibile", "imponibile", "ammontare imponibile"),
    "imposta": ("totale imposta", "imposta", "iva"),
    "totale": ("totale corrispettivi", "totale corrispettivo", "totale", "importo totale", "ammontare"),
}


def setup(**deps):
    _d.update(deps)


def _mappa(header: list) -> dict:
    low = [str(h or "").strip().lower() for h in header]
    m = {}
    for key, alias in KEYS.items():
        for a in alias:
            for i, h in enumerate(low):
                if h == a or (a in h and i not in m.values()):
                    m[key] = i
                    break
            if key in m:
                break
    return m


def _parse_tabella(filename: str, content: bytes) -> list:
    rows = _rows(filename, content)
    out = []
    m = {}
    for r in rows:
        if not m:
            cand = _mappa(r)
            if "data" in cand and ("totale" in cand or "imponibile" in cand):
                m = cand
            continue
        get = lambda k: r[m[k]] if k in m and m[k] < len(r) else None  # noqa: E731
        data = _data(get("data"))
        if not data:
            continue
        imp, iva = _num(get("imponibile")), _num(get("imposta"))
        tot = _num(get("totale")) or round(imp + iva, 2)
        out.append({"matricola": str(get("matricola") or "").strip()[:40], "data": data, "imponibile": imp, "imposta": iva, "totale": tot})
    return out


def _tag(el) -> str:
    return el.tag.split("}")[-1]


def _parse_xml(content: bytes) -> list:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    txt = {}
    for el in root.iter():
        t = _tag(el)
        if el.text and el.text.strip() and t not in txt:
            txt[t] = el.text.strip()
    matricola = txt.get("Matricola") or txt.get("IdDispositivo") or ""
    data = _data(txt.get("DataOraRilevazione") or txt.get("DataOraTrasmissione") or txt.get("DataChiusura") or "")
    if not data:
        return []
    imp = iva = 0.0
    for el in root.iter():
        t = _tag(el)
        if t in ("Imponibile", "Ammontare") and _tag_parent_ok(el):
            imp += _num(el.text)
        elif t == "Imposta":
            iva += _num(el.text)
    tot = round(imp + iva, 2)
    return [{"matricola": matricola[:40], "data": data, "imponibile": round(imp, 2), "imposta": round(iva, 2), "totale": tot}]


def _tag_parent_ok(el) -> bool:
    return True


def parse_corrispettivi(filename: str, content: bytes) -> list:
    name = filename.lower()
    if name.endswith(".zip"):
        out = []
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for n in z.namelist():
                if n.lower().endswith(".xml"):
                    out += _parse_xml(z.read(n))
        return out
    if name.endswith(".xml"):
        return _parse_xml(content)
    return _parse_tabella(filename, content)


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


def _is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


@router.get("/matricole")
async def matricole(request: Request):
    await _user(request)
    return await _d["db"].rt_matricole.find({}, {"_id": 0}).to_list(200)


class MatricolaInput(BaseModel):
    matricola: str
    store_id: str


@router.put("/matricole")
async def set_matricola(body: MatricolaInput, request: Request):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    s = await db.stores.find_one({"id": body.store_id}, {"_id": 0, "id": 1, "nome": 1})
    if not s:
        raise HTTPException(status_code=404, detail="Negozio non trovato")
    await db.rt_matricole.update_one({"matricola": body.matricola.strip()}, {"$set": {"matricola": body.matricola.strip(), "store_id": s["id"], "store_nome": s["nome"]}}, upsert=True)
    n = await db.corrispettivi_ade.update_many({"matricola": body.matricola.strip(), "store_id": ""}, {"$set": {"store_id": s["id"]}})
    return {"ok": True, "righe_assegnate": n.modified_count}


@router.post("/importa")
async def importa(request: Request, file: UploadFile = File(...), store_id: Optional[str] = None):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    db = _d["db"]
    content = await file.read()
    righe = parse_corrispettivi(file.filename or "file.csv", content)
    if not righe:
        raise HTTPException(status_code=400, detail="Nessun corrispettivo riconosciuto nel file (servono colonne Data e Totale/Imponibile, oppure XML AdE)")
    mappa = {m["matricola"]: m["store_id"] for m in await db.rt_matricole.find({}, {"_id": 0}).to_list(200)}
    now = datetime.now(timezone.utc).isoformat()
    importate = aggiornate = 0
    senza_negozio: set = set()
    for r in righe:
        sid = mappa.get(r["matricola"]) or (store_id if (store_id and not r["matricola"]) else "") or (store_id or "")
        if not sid:
            senza_negozio.add(r["matricola"] or "(senza matricola)")
        key = {"matricola": r["matricola"], "data": r["data"]}
        prev = await db.corrispettivi_ade.find_one(key, {"_id": 0, "id": 1})
        if prev:
            await db.corrispettivi_ade.update_one(key, {"$set": {**r, "store_id": sid or "", "updated_at": now}})
            aggiornate += 1
        else:
            await db.corrispettivi_ade.insert_one({**r, "id": str(uuid.uuid4()), "store_id": sid or "", "created_at": now, "created_by": user.get("name", "")})
            importate += 1
    return {"importate": importate, "aggiornate": aggiornate, "matricole_da_assegnare": sorted(senza_negozio), "giorni": len({r["data"] for r in righe})}


async def confronto_mese(store_id: str, anno: int, mese: int, righe_manuali: list) -> dict:
    """Per ogni giorno: AdE (somma RT del negozio) vs scontrini inseriti (riparazioni+merce+art74)."""
    db = _d["db"]
    pref = f"{anno:04d}-{mese:02d}"
    ade: dict = {}
    async for r in db.corrispettivi_ade.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "totale": 1}):
        ade[r["data"]] = round(ade.get(r["data"], 0.0) + r["totale"], 2)
    tot_ade = round(sum(ade.values()), 2)
    ade_min, ade_max = (min(ade), max(ade)) if ade else ("", "")
    tot_man = 0.0
    diff_giorni = []
    for r in righe_manuali:
        a = ade.get(r["data"])
        if a is not None:
            r["ade_totale"] = a
        sc = 0.0 if r.get("vuoto") else round(_num(r.get("riparazioni")) + _num(r.get("merce")) + _num(r.get("art74")), 2)
        if not r.get("vuoto"):
            tot_man += sc
        if a is not None or not r.get("vuoto"):
            d = round(sc - (a or 0.0), 2) if a is not None else None
            r["ade_diff"] = d
            if d is not None and abs(d) >= 0.01:
                diff_giorni.append({"data": r["data"], "scontrini": sc, "ade": a, "diff": d})
            elif a is None and not r.get("vuoto") and ade and ade_min <= r["data"] <= ade_max:
                diff_giorni.append({"data": r["data"], "scontrini": sc, "ade": None, "diff": None})
    tot_man_periodo = round(sum(g["scontrini"] for g in diff_giorni if g["ade"] is not None) + sum(a for d, a in ade.items() if any(r["data"] == d and r.get("ade_diff") == 0 for r in righe_manuali)), 2)
    return {"presente": bool(ade), "tot_ade": tot_ade, "tot_scontrini": round(tot_man, 2), "tot_scontrini_periodo": tot_man_periodo, "periodo": [ade_min, ade_max],
            "diff": round(tot_man_periodo - tot_ade, 2), "giorni_ade": len(ade), "giorni_diff": diff_giorni}


@router.delete("")
async def svuota(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    r = await _d["db"].corrispettivi_ade.delete_many({"store_id": store_id, "data": {"$regex": f"^{anno:04d}-{mese:02d}"}})
    return {"eliminate": r.deleted_count}
