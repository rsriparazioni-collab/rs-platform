"""Specchio del foglio Google PDP: una scheda per mese, riprodotta tale e quale (riepilogo negozi, totali AdE, fornitori, dettagli)."""
import csv
import io
import re
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request

from pdp_import import GIDS_PDP, SHEET_PDP, num, parse_pdp_sheet, scopri_schede

router = APIRouter(prefix="/contabilita/pdp-specchio")
_d: dict = {}


def parse_specchio(csv_text: str) -> dict:
    rows = [[c.strip() for c in r] + [""] * 40 for r in csv.reader(io.StringIO(csv_text))]
    hdr_i = next(i for i, r in enumerate(rows) if r[1].lower() == "entrate")
    header = rows[hdr_i]
    gruppi_row = rows[hdr_i - 1] if hdr_i > 0 else [""] * 40
    colonne, gruppo = [], "entrate"
    for j in range(1, 40):
        g = gruppi_row[j].lower()
        if "fisse" in g and "semi" not in g:
            gruppo = "spese_fisse"
        elif "semi" in g:
            gruppo = "spese_semifisse"
        h = header[j].strip()
        if not h:
            continue
        if h.lower().startswith("totale"):
            break
        colonne.append({"key": h.lower(), "label": h, "gruppo": gruppo})
    negozi = []
    i = hdr_i + 1
    while i < len(rows) and not rows[i][0].lower().startswith("fatturato"):
        r = rows[i]
        nome = r[0].strip()
        if nome and not nome.startswith("€"):
            vals = {}
            for j in range(1, 40):
                h = header[j].strip().lower()
                if h and not h.startswith("totale"):
                    vals[h] = num(r[j])
            entrate = sum(v for k, v in vals.items() if any(c["key"] == k and c["gruppo"] == "entrate" for c in colonne))
            spese = sum(v for k, v in vals.items() if any(c["key"] == k and c["gruppo"] != "entrate" for c in colonne))
            negozi.append({"nome": nome, "valori": vals, "tot_entrate": round(entrate, 2), "tot_spese": round(spese, 2), "risultato": round(entrate - spese, 2)})
        i += 1
    tot = {c["key"]: round(sum(n["valori"].get(c["key"], 0) for n in negozi), 2) for c in colonne}
    ade = {}
    if i + 1 < len(rows):
        r = rows[i + 1]
        # riga sotto "fatturato": [totale (RT + emesse), corrispettivi RT, fatture emesse]
        ade = {"totale": num(r[0]), "corrispettivi": num(r[1]), "fatture_emesse": num(r[2])}
    # fornitori: riga con >=5 nomi nelle colonne >=6, valori nella prima riga successiva con >=3 importi in quelle colonne
    fornitori, guadagno, iva = [], None, None
    for k in range(i + 1, min(i + 40, len(rows))):
        r = rows[k]
        nomi = [(j, r[j]) for j in range(6, 40) if r[j] and not re.search(r"\d", r[j])]
        if len(nomi) >= 5 and not fornitori:
            best = []
            for kk in range(k + 1, min(k + 20, len(rows))):
                vals = [(j, num(rows[kk][j])) for j, _ in nomi if re.search(r"\d", rows[kk][j] or "")]
                if len(vals) > len(best):
                    best = vals
            if len(best) >= 3:
                dd = dict(best)
                fornitori = [{"nome": n, "importo": dd.get(j, 0.0)} for j, n in nomi]
        for j, cell in enumerate(r):
            if cell.lower() == "guadagno" and j + 1 < len(r):
                guadagno = num(r[j + 1])
            if cell.strip().upper() == "IVA" and k + 1 < len(rows):
                iva = next((num(rows[k + 1][jj]) for jj in (j, j + 1, j - 1) if 0 <= jj < len(rows[k + 1]) and re.search(r"\d", rows[k + 1][jj] or "")), iva)
        if r[0].lower().startswith("cori"):
            break
    det = parse_pdp_sheet(csv_text)
    ade["fatture_ricevute"] = round(sum(x["totale"] for x in det["ricevute"]), 2)
    return {"colonne": colonne, "negozi": negozi, "totali": tot, "tot_entrate": round(sum(n["tot_entrate"] for n in negozi), 2), "tot_spese": round(sum(n["tot_spese"] for n in negozi), 2),
            "ade": ade, "fornitori": fornitori, "tot_fornitori": round(sum(f["importo"] for f in fornitori), 2), "guadagno": guadagno, "iva": iva,
            "corrispettivi": det["corrispettivi"], "emesse": det["emesse"], "ricevute": det["ricevute"]}


async def _admin(request: Request) -> dict:
    user = await _d["user"](request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


async def carica_tutti(user_name: str = "") -> list:
    db = _d["db"]
    esito = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as cl:
        gids = dict(GIDS_PDP)
        try:
            html = (await cl.get(f"https://docs.google.com/spreadsheets/d/{SHEET_PDP}/htmlview")).text
            gids.update({g: am for g, am in scopri_schede(html).items() if am >= (2026, 1)})
        except Exception:  # noqa: BLE001
            pass
        for gid, (anno, mese) in sorted(gids.items(), key=lambda kv: kv[1]):
            try:
                r = await cl.get(f"https://docs.google.com/spreadsheets/d/{SHEET_PDP}/export?format=csv&gid={gid}")
                r.raise_for_status()
                p = parse_specchio(r.text)
            except Exception as e:  # noqa: BLE001
                esito.append({"anno": anno, "mese": mese, "errore": str(e)[:160]})
                continue
            await db.pdp_specchio.update_one({"anno": anno, "mese": mese}, {"$set": {**p, "gid": gid, "at": datetime.now(timezone.utc).isoformat(), "by": user_name}, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
            esito.append({"anno": anno, "mese": mese, "negozi": len(p["negozi"]), "entrate": p["tot_entrate"], "spese": p["tot_spese"]})
    return esito


@router.get("")
async def get_specchio(anno: int, mese: int, request: Request):
    await _admin(request)
    db = _d["db"]
    doc = await db.pdp_specchio.find_one({"anno": anno, "mese": mese}, {"_id": 0})
    mesi = [f"{m['anno']:04d}-{m['mese']:02d}" async for m in db.pdp_specchio.find({}, {"_id": 0, "anno": 1, "mese": 1}).sort([("anno", -1), ("mese", -1)])]
    # corrispettivi del gestionale per negozio (stesso mese) per il confronto con la colonna ENTRATE
    gest = {}
    async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1}):
        md = await _d["mese_dati"](s["id"], anno, mese)
        if md["totali"]["giorni_inseriti"]:
            gest[(s["nome"] or "").strip().lower()] = md["totali"]["totale"]
    return {"anno": anno, "mese": mese, "dati": doc, "mesi_disponibili": mesi, "gestionale_corrispettivi": gest}


@router.post("/carica")
async def carica(request: Request):
    user = await _admin(request)
    return {"esito": await carica_tutti(user.get("name", ""))}
