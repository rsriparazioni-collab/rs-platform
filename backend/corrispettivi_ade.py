"""Corrispettivi telematici AdE: import CSV/XLSX (consultazione) o ZIP/XML (download massivo), abbinati al negozio per matricola RT."""
import io
import logging
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

logger = logging.getLogger("corrispettivi_ade")

from fatture_ade import _rows, _num, _data

router = APIRouter(prefix="/contabilita/corrispettivi-ade")
_d: dict = {}

KEYS = {
    "matricola": ("matricola", "matricola dispositivo", "id dispositivo", "dispositivo", "identificativo dispositivo", "rt"),
    "data": ("data rilevazione", "data e ora rilevazione", "data chiusura", "data trasmissione", "data e ora trasmissione", "data invio", "data"),
    "imponibile": ("totale imponibile", "imponibile vendite", "imponibile", "ammontare imponibile"),
    "imposta": ("totale imposta", "imposta vendite", "imposta", "iva"),
    # AdE: "Ammontare delle vendite" comprende anche gli scontrini annullati → solo informativo, NON è il totale
    "ammontare": ("ammontare delle vendite", "ammontare vendite", "ammontare"),
    "totale": ("totale corrispettivi", "totale corrispettivo", "importo totale", "totale"),
    "inatt_da": ("periodo di inattivita' da", "periodo di inattività da", "inattivita' da", "inattività da"),
    "inatt_a": ("periodo di inattivita' a", "periodo di inattività a", "inattivita' a", "inattività a"),
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
            if "data" in cand and ("totale" in cand or "imponibile" in cand or "ammontare" in cand):
                m = cand
            continue
        get = lambda k: r[m[k]] if k in m and m[k] < len(r) else None  # noqa: E731
        data = _data(get("data"))
        if not data:
            continue
        imp, iva, amm = _num(get("imponibile")), _num(get("imposta")), _num(get("ammontare"))
        # totale giornata = imponibile vendite + imposta vendite ("Ammontare delle vendite" include anche gli scontrini annullati: solo informativo)
        tot = round(imp + iva, 2) if ("imponibile" in m or "imposta" in m) else (_num(get("totale")) if "totale" in m else round(amm, 2))
        out.append({"matricola": str(get("matricola") or "").strip().strip("'\"").strip()[:40], "data": data, "imponibile": round(imp, 2), "imposta": round(iva, 2), "ammontare": round(amm, 2), "totale": tot,
                    "inatt_da": _data(get("inatt_da")) if "inatt_da" in m else None, "inatt_a": _data(get("inatt_a")) if "inatt_a" in m else None})
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
    aliquote = []
    for el in root.iter():
        t = _tag(el)
        if t in ("Imponibile", "Ammontare") and _tag_parent_ok(el):
            imp += _num(el.text)
        elif t == "Imposta":
            iva += _num(el.text)
        elif t in ("Riepilogo", "RiepilogoIVA", "DatiRiepilogo"):
            sub = {_tag(c): (c.text or "").strip() for c in el}
            if any(k in sub for k in ("AliquotaIVA", "Natura", "Ammontare", "Imponibile")):
                aliquote.append({"aliquota": _num(sub["AliquotaIVA"]) if sub.get("AliquotaIVA") else None, "natura": sub.get("Natura") or "",
                                 "imponibile": round(_num(sub.get("Ammontare") or sub.get("Imponibile")), 2), "imposta": round(_num(sub.get("Imposta")), 2)})
    tot = round(imp + iva, 2)
    return [{"matricola": matricola[:40], "data": data, "imponibile": round(imp, 2), "imposta": round(iva, 2), "totale": tot, "aliquote": aliquote}]


def _tag_parent_ok(el) -> bool:
    return True


def parse_corrispettivi(filename: str, content: bytes) -> list:
    return _unisci_doppie_chiusure(_parse_grezzo(filename, content))


def _unisci_doppie_chiusure(righe: list) -> list:
    """Doppia chiusura dello stesso registratore nello stesso giorno (una a 0 e una col totale, o un rinvio): vale UNA sola riga, quella col totale."""
    best: dict = {}
    inattivita: dict = {}
    for r in righe:
        if r.get("inatt_da") and r.get("inatt_a"):
            inattivita.setdefault(r["matricola"], set()).add((r["inatt_da"], r["inatt_a"]))
        k = (r["matricola"], r["data"])
        cur = best.get(k)
        if cur is None or r["totale"] > cur["totale"] or (r["totale"] == cur["totale"] and r.get("ammontare", 0) > cur.get("ammontare", 0)):
            best[k] = {**r, "chiusure_nel_file": (cur or {}).get("chiusure_nel_file", 0) + 1}
        else:
            cur["chiusure_nel_file"] = cur.get("chiusure_nel_file", 1) + 1
    out = sorted(best.values(), key=lambda x: (x["data"], x["matricola"]))
    for r in out:
        r.pop("inatt_da", None)
        r.pop("inatt_a", None)
        r["inattivita"] = sorted(inattivita.get(r["matricola"], set()))
    return out


def _parse_grezzo(filename: str, content: bytes) -> list:
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
    negozi_toccati = sorted({mappa.get(r["matricola"], "") for r in righe} - {""}) or ([store_id] if store_id else [])
    # giorni di inattività dichiarati dal registratore → "negozio chiuso" automatico (solo se non c'è un corrispettivo inserito)
    chiusi = 0
    visti: set = set()
    for r in righe:
        sid = mappa.get(r["matricola"]) or store_id or ""
        for da, a in r.get("inattivita") or []:
            if not sid or (sid, da, a) in visti:
                continue
            visti.add((sid, da, a))
            g = date.fromisoformat(da)
            while g <= date.fromisoformat(a):
                d = g.isoformat()
                if g.weekday() != 6 and not await db.corrispettivi.find_one({"store_id": sid, "data": d}, {"_id": 0, "id": 1}):
                    res = await db.giorni_chiusi.update_one({"store_id": sid, "data": d}, {"$setOnInsert": {"motivo": "inattività registratore (AdE)", "da": "automatico", "at": now}}, upsert=True)
                    chiusi += 1 if res.upserted_id else 0
                g += timedelta(days=1)
    mesi = sorted({(int(r["data"][:4]), int(r["data"][5:7])) for r in righe})
    controllo = await _avvisa_differenze(negozi_toccati, mesi)
    doppie = sum(1 for r in righe if r.get("chiusure_nel_file", 1) > 1)
    return {"importate": importate, "aggiornate": aggiornate, "doppie_chiusure_unificate": doppie, "giorni_chiusi_auto": chiusi, "matricole_da_assegnare": sorted(senza_negozio), "giorni": len({r["data"] for r in righe}),
            "giorni_caricati": sorted({r["data"] for r in righe}), "negozi": negozi_toccati, "controllo": controllo}


async def _avvisa_differenze(store_ids: list, mesi: list) -> dict:
    """Dopo l'import: confronto automatico e, se ci sono differenze, WhatsApp al negozio con l'elenco (max 1 avviso al giorno per negozio/mese)."""
    db = _d["db"]
    problemi, avvisi = [], 0
    for sid in store_ids:
        store = await db.stores.find_one({"id": sid}, {"_id": 0, "id": 1, "nome": 1})
        if not store:
            continue
        for anno, mese in mesi:
            try:
                items = [p for p in await _d["problemi_negozio"](store, anno, mese, False) if p["tipo"] in ("ade_differenza", "corrispettivo_mancante", "ade_assente") and p.get("data", "")[:7] == f"{anno:04d}-{mese:02d}"]
            except Exception as e:
                logger.warning(f"controllo AdE {sid}: {e}")
                continue
            problemi.extend(items)
            if not items:
                continue
            key = f"ade-diff-{sid}-{anno}-{mese:02d}-{date.today().isoformat()}"
            if await db.scadenze_alert_log.find_one({"key": key}):
                continue
            cfg = await db.contabilita_config.find_one({"store_id": sid}, {"_id": 0, "wa_numero": 1}) or {}
            numero = cfg.get("wa_numero")
            if not numero:
                continue
            testo = f"⚠️ *Controllo corrispettivi AdE – {store['nome']} {mese:02d}/{anno}*\n" + "\n".join(f"• {p['testo']}" for p in items[:12]) + (f"\n… e altri {len(items) - 12}" if len(items) > 12 else "") + "\n\nCorreggi nel gestionale → Contabilità → Cassa & Corrispettivi."
            try:
                await _d["wa_send"](numero, testo, session=sid, tipo="ade_differenze")
                await db.scadenze_alert_log.insert_one({"key": key, "at": datetime.now(timezone.utc).isoformat(), "n": len(items)})
                avvisi += 1
            except Exception as e:
                logger.warning(f"avviso AdE {sid}: {e}")
    return {"problemi": len(problemi), "avvisi_whatsapp": avvisi, "dettaglio": [p["testo"] for p in problemi[:20]]}


async def confronto_mese(store_id: str, anno: int, mese: int, righe_manuali: list) -> dict:
    """Per ogni giorno: AdE (somma RT del negozio) vs scontrini inseriti (riparazioni+merce+art74)."""
    db = _d["db"]
    pref = f"{anno:04d}-{mese:02d}"
    ade: dict = {}
    annulli: dict = {}
    dettaglio: dict = {}
    async for r in db.corrispettivi_ade.find({"store_id": store_id, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "totale": 1, "ammontare": 1, "imponibile": 1, "imposta": 1, "matricola": 1}):
        ade[r["data"]] = round(ade.get(r["data"], 0.0) + r["totale"], 2)
        dt = dettaglio.setdefault(r["data"], {"imponibile": 0.0, "imposta": 0.0, "chiusure": 0, "matricole": set()})
        dt["imponibile"] = round(dt["imponibile"] + _num(r.get("imponibile")), 2)
        dt["imposta"] = round(dt["imposta"] + _num(r.get("imposta")), 2)
        dt["chiusure"] += 1
        dt["matricole"].add(r.get("matricola") or "")
        # scontrini annullati/resi (netto IVA) = ammontare delle vendite − imponibile (es. 29/10: 209,18 − 194,26 = 14,92 → 18,20 lordo)
        if r.get("ammontare"):
            annulli[r["data"]] = round(annulli.get(r["data"], 0.0) + max(0.0, r["ammontare"] - _num(r.get("imponibile"))), 2)
    tot_ade = round(sum(ade.values()), 2)
    tot_annulli = round(sum(annulli.values()), 2)
    ade_min, ade_max = (min(ade), max(ade)) if ade else ("", "")
    tot_man = 0.0
    diff_giorni = []
    for r in righe_manuali:
        a = ade.get(r["data"])
        if a is not None:
            r["ade_totale"] = a
            if annulli.get(r["data"]):
                r["ade_annulli"] = annulli[r["data"]]
        # confronto con l'AdE: solo riparazioni + merce (le ricariche art. 74 non passano dal registratore telematico)
        sc = 0.0 if r.get("vuoto") else round(_num(r.get("riparazioni")) + _num(r.get("merce")), 2)
        if not r.get("vuoto"):
            tot_man += sc
        if a is not None or not r.get("vuoto"):
            d = round(sc - (a or 0.0), 2) if a is not None else None
            # scontrino annullato: l'RT lo conta nell'ammontare, l'AdE no → se la differenza è proprio l'annullo (lordo 22 %) non è un errore
            ann_lordo = round(annulli.get(r["data"], 0.0) * 1.22, 2)
            if d is not None and ann_lordo and abs(d - ann_lordo) < 0.05:
                r["ade_annullo_spiega"] = ann_lordo
                d = 0.0
            r["ade_diff"] = d
            if d is not None and abs(d) >= 0.01:
                dt = dettaglio.get(r["data"]) or {}
                diff_giorni.append({"data": r["data"], "scontrini": sc, "ade": a, "diff": d, "annulli": annulli.get(r["data"], 0.0), "art74": _num(r.get("art74")), "imponibile": dt.get("imponibile", 0.0), "imposta": dt.get("imposta", 0.0),
                                    "chiusure": dt.get("chiusure", 0), "matricole": sorted(dt.get("matricole") or [])})
            elif a is None and not r.get("vuoto") and ade and ade_min <= r["data"] <= ade_max:
                diff_giorni.append({"data": r["data"], "scontrini": sc, "ade": None, "diff": None})
    tot_man_periodo = round(sum(g["scontrini"] for g in diff_giorni if g["ade"] is not None) + sum(a for d, a in ade.items() if any(r["data"] == d and r.get("ade_diff") == 0 for r in righe_manuali)), 2)
    return {"presente": bool(ade), "tot_ade": tot_ade, "tot_scontrini": round(tot_man, 2), "tot_scontrini_periodo": tot_man_periodo, "periodo": [ade_min, ade_max],
            "diff": round(tot_man_periodo - tot_ade, 2), "giorni_ade": len(ade), "giorni_diff": diff_giorni, "tot_annulli": tot_annulli, "giorni_annulli": sorted([{"data": d, "annulli": v} for d, v in annulli.items() if v], key=lambda x: x["data"])}


@router.delete("")
async def svuota(store_id: str, anno: int, mese: int, request: Request):
    user = await _user(request)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Solo amministratore")
    r = await _d["db"].corrispettivi_ade.delete_many({"store_id": store_id, "data": {"$regex": f"^{anno:04d}-{mese:02d}"}})
    return {"eliminate": r.deleted_count}


async def ricalcola_totali_importati() -> int:
    """All'avvio (idempotente): le righe AdE importate con la vecchia lettura (totale = 'Ammontare delle vendite', che include gli annulli)
    vengono riallineate a imponibile + imposta."""
    db = _d["db"]
    n = 0
    async for r in db.corrispettivi_ade.find({"$or": [{"imponibile": {"$gt": 0}}, {"imposta": {"$gt": 0}}]}, {"_id": 0, "id": 1, "imponibile": 1, "imposta": 1, "totale": 1, "ammontare": 1}):
        giusto = round(_num(r.get("imponibile")) + _num(r.get("imposta")), 2)
        if abs(giusto - _num(r.get("totale"))) >= 0.01:
            upd = {"totale": giusto}
            if not r.get("ammontare") and _num(r.get("totale")) > giusto:
                upd["ammontare"] = _num(r.get("totale"))
            await db.corrispettivi_ade.update_one({"id": r["id"]}, {"$set": upd})
            n += 1
    # matricole salvate con gli apici del CSV AdE ('1BENI099492') → senza apici, così corrispondono ai negozi assegnati
    for coll in (db.corrispettivi_ade, db.rt_matricole):
        async for r in coll.find({"matricola": {"$regex": "^['\"]|['\"]$"}}, {"_id": 1, "matricola": 1}):
            await coll.update_one({"_id": r["_id"]}, {"$set": {"matricola": r["matricola"].strip().strip("'\"").strip()}})
            n += 1
    # doppie chiusure già salvate (stesso negozio/giorno, una a 0): si tiene solo quella col totale
    tolte = 0
    async for g in db.corrispettivi_ade.aggregate([{"$match": {"totale": {"$lte": 0}}}, {"$group": {"_id": {"s": "$store_id", "d": "$data"}, "ids": {"$push": "$id"}}}]):
        if await db.corrispettivi_ade.find_one({"store_id": g["_id"]["s"], "data": g["_id"]["d"], "totale": {"$gt": 0}}, {"_id": 0, "id": 1}):
            r = await db.corrispettivi_ade.delete_many({"id": {"$in": g["ids"]}})
            tolte += r.deleted_count
    if n or tolte:
        logger.info(f"corrispettivi AdE: {n} totali riallineati a imponibile+imposta, {tolte} chiusure a zero doppie rimosse")
    return n + tolte
