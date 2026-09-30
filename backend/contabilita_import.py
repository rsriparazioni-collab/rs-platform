import csv
import io
import re
import uuid
from datetime import date, datetime, timezone

MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
        "settembre": 9, "ottobre": 10, "novembre": 11, "november": 11, "dicembre": 12}
FOGLI_CORRISPETTIVI = [
    ("1lOiXbYGiyAsNgxEzsMZAXVeWOfAQdblADruPiIxf8zk", ["1166370567", "298466080", "84131654", "904324188", "1316940315", "1932362341", "1412915582", "932024866", "1698249546", "1702221537", "840066917"]),
    ("1gMi8pMOR1q07C_RSS1pnHvr7oRfyrWSmCd69DDaKCP0", ["1358116208", "1422384141", "1851357316", "796649175", "1636806261", "70591718", "2101125075", "1800496541", "1104526796", "765755928", "426358957", "1982598833", "1128909990", "181332126", "648358209", "361473756", "591109909", "857648392", "1472903678", "836401755"]),
]


def num(v: str) -> float:
    s = (v or "").replace("€", "").replace(" ", "").strip()
    if not s or s.upper() == "X":
        return 0.0
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    elif "." in s and not re.search(r"\.\d{1,2}$", s):
        s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _mese_anno(rows: list):
    for r in rows[:3]:
        for c in r:
            m = re.match(r"^\s*([a-z]+)\s*(\d{2,4})\s*$", c.strip().lower())
            if m and m.group(1) in MESI:
                a = int(m.group(2))
                return MESI[m.group(1)], a if a > 100 else 2000 + a
    return None, None


def _blocchi(header: list, rows: list) -> list:
    """Per ogni blocco (colonna RIP.) ritorna indici colonne e nome negozio (cercato nelle prime 2 righe sopra il blocco)."""
    out = []
    starts = [i for i, h in enumerate(header) if h.strip().upper().startswith("RIP")]
    for n, st in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(header)
        idx = {}
        for i in range(st, end):
            h = header[i].strip().lower()
            if h.startswith("rip"): idx["riparazioni"] = i
            elif h.startswith("merce"): idx["merce"] = i
            elif h.startswith("art"): idx["art74"] = i
            elif h.startswith("fatt"): idx["fatture"] = i
            elif h.startswith("pos/cont"): idx["pagamento"] = i
            elif h.startswith("n°") or h.startswith("n.") or "fattura" in h: idx["numero"] = i
            elif h.startswith("totale") and "totale" not in idx: idx["totale"] = i
            elif h.startswith("contanti"): idx["contanti"] = i
            elif h == "pos": idx["pos"] = i
            elif h.startswith("versati"): idx["versati"] = i
        nome = ""
        for r in rows[:2]:
            for i in range(max(0, st - 1), end):
                c = r[i].strip().lower() if i < len(r) else ""
                if c and c not in MESI and not re.match(r"^[a-z]+\s*\d{2,4}$", c) and c not in ("fatture", "x", "0", "fc") and not re.match(r"^\d", c):
                    nome = c
        out.append({"idx": idx, "nome": nome, "start": st, "end": end})
    return out


def _data_spesa(s: str, anno: int, mese: int):
    m = re.match(r"^\s*(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", s or "")
    if not m:
        return None
    g, mm = int(m.group(1)), int(m.group(2))
    a = int(m.group(3)) if m.group(3) else anno
    a = a if a > 100 else 2000 + a
    if mm == 12 and mese == 1:
        a -= 1
    try:
        return date(a, mm, g).isoformat()
    except ValueError:
        return None


def parse_foglio(csv_text: str) -> dict:
    rows = [r + [""] * 30 for r in csv.reader(io.StringIO(csv_text))]
    mese, anno = _mese_anno(rows)
    if not mese:
        return {"errore": "mese non riconosciuto", "negozi": {}}
    hi = next((i for i, r in enumerate(rows) if r[0].strip().upper() == "X"), None)
    if hi is None:
        return {"errore": "intestazione non trovata", "negozi": {}}
    blocchi = _blocchi(rows[hi], rows)
    negozi = {b["nome"]: {"giorni": [], "spese": []} for b in blocchi}
    i = hi + 1
    while i < len(rows) and rows[i][0].strip().isdigit():
        g = int(rows[i][0])
        if 1 <= g <= 31:
            try:
                d = date(anno, mese, g).isoformat()
            except ValueError:
                i += 1
                continue
            for b in blocchi:
                r, ix = rows[i], b["idx"]
                val = {k: num(r[ix[k]]) for k in ("riparazioni", "merce", "art74", "fatture", "contanti", "pos", "versati") if k in ix}
                if not any(val.values()):
                    continue
                fd = []
                if val.get("fatture"):
                    fd = [{"numero": r[ix["numero"]].strip() if "numero" in ix else "", "importo": val["fatture"], "pagamento": r[ix["pagamento"]].strip().lower() if "pagamento" in ix else ""}]
                negozi[b["nome"]]["giorni"].append({"data": d, **val, "fatture_dettaglio": fd})
        i += 1
    si = next((k for k in range(i, len(rows)) if "spese per contanti" in rows[k][0].lower() or any("spese per contanti" in c.lower() for c in rows[k])), None)
    if si is not None and si + 1 < len(rows):
        hdr = rows[si + 1]
        for b in blocchi:
            cols = [k for k in range(max(0, b["start"] - 1), b["end"]) if hdr[k].strip().upper() == "DATA"]
            if not cols:
                continue
            dc = cols[0]
            mc = next((k for k in range(dc + 1, b["end"]) if "motivo" in hdr[k].lower()), dc + 1)
            ec = next((k for k in range(mc + 1, b["end"]) if hdr[k].strip() in ("€", "EUR", "euro")), mc + 2)
            nc = next((k for k in range(ec + 1, b["end"]) if "fattura" in hdr[k].lower() or "ritiro" in hdr[k].lower()), ec + 1)
            for r in rows[si + 2:]:
                d = _data_spesa(r[dc], anno, mese)
                imp = num(r[ec])
                if not d or not imp:
                    continue
                negozi[b["nome"]]["spese"].append({"data": d, "motivo": r[mc].strip()[:120], "importo": imp, "riferimento": r[nc].strip()[:60]})
    return {"mese": mese, "anno": anno, "negozi": negozi}


async def importa_tutti(db, fetch) -> list:
    stores = {s["nome"].strip().lower(): s async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    now = datetime.now(timezone.utc).isoformat()
    esito = []
    for sheet_id, gids in FOGLI_CORRISPETTIVI:
        for gid in gids:
            try:
                txt = await fetch(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}")
                p = parse_foglio(txt)
            except Exception as e:
                esito.append({"gid": gid, "errore": str(e)})
                continue
            if p.get("errore"):
                esito.append({"gid": gid, "errore": p["errore"]})
                continue
            for nome, dati in p["negozi"].items():
                store = stores.get(nome)
                if not store:
                    esito.append({"gid": gid, "mese": f"{p['anno']}-{p['mese']:02d}", "errore": f"negozio '{nome}' non trovato"})
                    continue
                ng, ns = 0, 0
                for g in dati["giorni"]:
                    ex = await db.corrispettivi.find_one({"store_id": store["id"], "data": g["data"]}, {"_id": 0, "fonte": 1})
                    if ex and ex.get("fonte") != "foglio_google":
                        continue
                    tot = round(g["riparazioni"] + g["merce"] + g["art74"] + g["fatture"], 2)
                    doc = {**g, "store_id": store["id"], "totale": tot, "incassato": round(g["contanti"] + g["pos"], 2),
                           "iva": round((g["riparazioni"] + g["merce"] + g["fatture"]) * 22 / 122, 2), "note": "", "fonte": "foglio_google", "updated_at": now, "updated_by": "import fogli"}
                    await db.corrispettivi.update_one({"store_id": store["id"], "data": g["data"]}, {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
                    ng += 1
                pref = f"{p['anno']}-{p['mese']:02d}"
                await db.spese_cassa.delete_many({"store_id": store["id"], "fonte": "foglio_google", "foglio_mese": pref})
                for s in dati["spese"]:
                    await db.spese_cassa.insert_one({**s, "id": str(uuid.uuid4()), "store_id": store["id"], "fonte": "foglio_google", "foglio_mese": pref, "created_at": now, "created_by": "import fogli"})
                    ns += 1
                esito.append({"negozio": store["nome"], "mese": pref, "giorni": ng, "spese": ns})
    return esito
