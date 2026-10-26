"""Import Punto di pareggio dal foglio Google mensile (una scheda per mese): riepilogo per negozio, fatture attive/passive."""
import csv
import hashlib
import io
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

SHEET_PDP = "1aVjFCxg-Gm3zNQNcEE-Jq-WkTaIluLzlLRXFPCd82hw"
GIDS_PDP = {"1793768583": (2026, 10), "139743288": (2026, 9), "1128499380": (2026, 8), "1481012556": (2026, 7), "479326625": (2026, 6),
            "211467724": (2026, 5), "1646965472": (2026, 4), "1240257795": (2026, 3), "2136149709": (2026, 2), "500864334": (2026, 1)}

MESI_ABBR = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}


def scopri_schede(html: str) -> dict:
    """Trova i tab mensili (es. 'ott26', 'NOV26', 'dic 2026') dall'htmlview pubblico del foglio → {gid: (anno, mese)}."""
    found = {}
    for name, gid in re.findall(r'items\.push\(\{name: "([^"]*)",[^}]*?gid: "(\d+)"', html):
        m = re.match(r"^\s*([a-zà]{3})[a-zà]*\s*'?(\d{2}|\d{4})\s*$", name.strip().lower())
        if m and m.group(1) in MESI_ABBR:
            anno = int(m.group(2))
            found[gid] = (anno if anno > 100 else 2000 + anno, MESI_ABBR[m.group(1)])
    return found


MAP_VOCI = {"eolo": "entrate|Eolo", "energia": "entrate|Energia / Enel", "telefonia": "entrate|Telefonia", "pacchi": "entrate|Pacchi",
            "stipendi": "spese_fisse|Stipendi", "contributi": "spese_fisse|Contributi", "tfr": "spese_fisse|TFR", "inail": "spese_fisse|INAIL",
            "condominio": "spese_fisse|Condominio", "affitti": "spese_fisse|Affitti", "utenze": "spese_fisse|Utenze",
            "commercialista": "spese_fisse|Commercialista", "finanziamento": "spese_fisse|Finanziamento",
            "ritiri": "spese_semifisse|Ritiri", "publicittà": "spese_semifisse|Pubblicità", "pubblicità": "spese_semifisse|Pubblicità"}


def num(v) -> float:
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v or "").replace("€", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
    if s in ("", "-"):
        return 0.0
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def _data(s: str):
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", str(s or ""))
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


def parse_pdp_sheet(csv_text: str) -> dict:
    rows = [[c.strip() for c in r] + [""] * 40 for r in csv.reader(io.StringIO(csv_text))]
    # 1) riepilogo per negozio
    hdr_i = next(i for i, r in enumerate(rows) if r[1].lower() == "entrate")
    header = [h.lower() for h in rows[hdr_i]]
    negozi = {}
    for r in rows[hdr_i + 1:hdr_i + 12]:
        nome = r[0].lower()
        if not nome or nome.startswith("fatturato") or nome.startswith("€"):
            if nome.startswith("fatturato"):
                break
            continue
        vals = {}
        for i, h in enumerate(header):
            if h in MAP_VOCI and num(r[i]):
                vals[MAP_VOCI[h]] = vals.get(MAP_VOCI[h], 0.0) + num(r[i])
        negozi[nome] = {"corrispettivi_foglio": num(r[1]), "valori": vals}
    # 2) dettaglio fatture
    det_i = next((i for i, r in enumerate(rows) if r[0].lower().startswith("cori") or r[0].lower().startswith("corri")), None)
    emesse, ricevute, corr = [], [], []
    if det_i is not None:
        for r in rows[det_i + 2:]:
            if _data(r[2]) and num(r[5]):
                corr.append({"matricola": r[0].strip("'"), "negozio": r[1].lower(), "data": _data(r[2]), "imponibile": num(r[3]), "imposta": num(r[4]), "totale": num(r[5])})
            if r[9].strip("'") and num(r[12]):
                numero = r[7] if _data(r[8]) else r[8]
                emesse.append({"tipo": "Fattura", "numero": numero.strip("'")[:40], "data": _data(r[8]) or "",
                               "controparte": r[9].strip("'"), "imponibile": num(r[10]), "imposta": num(r[11]), "totale": num(r[12])})
            if r[19].strip("'") and num(r[22]):
                ricevute.append({"tipo": r[15] or "Fattura", "numero": r[16].strip("'")[:40], "data": "", "controparte": r[19].strip("'"),
                                 "imponibile": num(r[20]), "imposta": num(r[21]), "totale": num(r[22])})
    mesi = Counter((d[:7] for d in (c["data"] for c in corr) if d))
    # 3) cella "IVA" del riepilogo (valore nella riga successiva, stessa colonna)
    iva_foglio = None
    for i, r in enumerate(rows[:det_i or 60]):
        for j, cell in enumerate(r):
            if cell.strip().lower() == "iva" and i + 1 < len(rows):
                for jj in (j, j + 1, j - 1):
                    if 0 <= jj < len(rows[i + 1]) and num(rows[i + 1][jj]):
                        iva_foglio = num(rows[i + 1][jj])
                        break
    return {"negozi": negozi, "emesse": emesse, "ricevute": ricevute, "corrispettivi": corr, "mese_rilevato": mesi.most_common(1)[0][0] if mesi else None, "iva_foglio": iva_foglio}


def _riga(voce, foglio, gest, **extra):
    return {"voce": voce, "foglio": round(foglio, 2), "gestionale": round(gest, 2), "diff": round(gest - foglio, 2), "ok": abs(gest - foglio) < 0.01, **extra}


async def _confronto(db, p, anno, mese, cid_fatt, per_centro, slug_store, store_centro, mese_dati) -> list:
    """Voce per voce: valore nel foglio vs valore nel gestionale dopo l'import."""
    out = []
    for nome, d in p["negozi"].items():
        s = slug_store.get(nome)
        if s and d["corrispettivi_foglio"]:
            md = await mese_dati(s["id"], anno, mese)
            giorni_rt = {c["data"]: c["totale"] for c in p["corrispettivi"] if re.sub(r"\d+", "", c["negozio"]).strip() == nome}
            giorni = []
            for r in md["righe"]:
                sc = 0.0 if r.get("vuoto") else round(num(r.get("riparazioni")) + num(r.get("merce")) + num(r.get("art74")), 2)
                fg = giorni_rt.get(r["data"])
                if fg is None and r.get("vuoto"):
                    continue
                if fg is None or abs(sc - fg) >= 0.01:
                    giorni.append({"data": r["data"], "scontrini": sc, "foglio": fg, "diff": round(sc - fg, 2) if fg is not None else None})
            out.append(_riga(f"Corrispettivi {s['nome']}", d["corrispettivi_foglio"], md["totali"]["totale"], store_id=s["id"], giorni=giorni))
    for cid, valori in per_centro.items():
        doc = await db.pdp.find_one({"centro_id": cid, "anno": anno, "mese": mese}, {"_id": 0, "valori": 1}) or {}
        salvati = doc.get("valori") or {}
        for k, v in sorted(valori.items()):
            out.append(_riga(k.split("|", 1)[1], v, num(salvati.get(k)) if isinstance(salvati.get(k), str) else float(salvati.get(k) or 0)))
    if cid_fatt:
        for direzione, lst in (("emesse", p["emesse"]), ("ricevute", p["ricevute"])):
            tot_db = 0.0
            async for f in db.fatture_ade.find({"centro_id": cid_fatt, "anno": anno, "mese": mese, "direzione": direzione}, {"_id": 0, "totale": 1}):
                tot_db += float(f.get("totale") or 0)
            out.append(_riga(f"Fatture {direzione} (totale)", sum(x["totale"] for x in lst), tot_db))
    return out


async def importa_pdp_fogli(db, fetch, centri: list, stores: list, user_name: str = "", mese_dati=None) -> list:
    slug_store = {(s["nome"] or "").strip().lower(): s for s in stores}
    store_centro = {sid: c["id"] for c in centri for sid in c["store_ids"]}
    esito = []
    now = datetime.now(timezone.utc).isoformat()
    gids = dict(GIDS_PDP)
    try:
        scoperte = scopri_schede(await fetch(f"https://docs.google.com/spreadsheets/d/{SHEET_PDP}/htmlview"))
        gids.update({g: am for g, am in scoperte.items() if am >= (2026, 1)})
    except Exception:  # noqa: BLE001
        pass
    for gid, (anno, mese) in sorted(gids.items(), key=lambda kv: kv[1]):
        try:
            txt = await fetch(f"https://docs.google.com/spreadsheets/d/{SHEET_PDP}/export?format=csv&gid={gid}")
            p = parse_pdp_sheet(txt)
        except Exception as e:  # noqa: BLE001
            esito.append({"anno": anno, "mese": mese, "errore": str(e)[:160]})
            continue
        per_centro: dict = {}
        for nome, d in p["negozi"].items():
            s = slug_store.get(nome)
            cid = store_centro.get(s["id"]) if s else None
            if not cid:
                continue
            acc = per_centro.setdefault(cid, {})
            for k, v in d["valori"].items():
                acc[k] = round(acc.get(k, 0.0) + v, 2)
        for cid, valori in per_centro.items():
            if not valori:
                continue
            doc = await db.pdp.find_one({"centro_id": cid, "anno": anno, "mese": mese}, {"_id": 0, "valori": 1})
            merged = dict((doc or {}).get("valori") or {})
            merged.update(valori)
            await db.pdp.update_one({"centro_id": cid, "anno": anno, "mese": mese},
                                    {"$set": {"valori": merged, "updated_at": now, "updated_by": f"{user_name} (foglio Google)", "fonte_foglio": gid},
                                     "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
        # fatture: il foglio è del centro Morbegno+Gravedona (negozi presenti nel dettaglio corrispettivi)
        negozi_det = {c["negozio"].replace("2", "").strip() for c in p["corrispettivi"]}
        cids = {store_centro.get(slug_store[n]["id"]) for n in negozi_det if n in slug_store} - {None}
        cid_fatt = next(iter(cids)) if len(cids) == 1 else (per_centro and max(per_centro, key=lambda k: len(per_centro[k])))
        if cid_fatt and p.get("iva_foglio") is not None:
            await db.iva_periodi.update_one({"centro_id": cid_fatt, "anno": anno, "mese": mese}, {"$set": {"iva_foglio": p["iva_foglio"]}, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
        n_em = n_ric = 0
        n_corr = 0
        for c in p["corrispettivi"]:
            s = slug_store.get(re.sub(r"\d+", "", c["negozio"]).strip())
            if not s or not c["matricola"]:
                continue
            await db.rt_matricole.update_one({"matricola": c["matricola"]}, {"$setOnInsert": {"matricola": c["matricola"], "store_id": s["id"], "store_nome": s["nome"]}}, upsert=True)
            key = {"matricola": c["matricola"], "data": c["data"]}
            r = await db.corrispettivi_ade.update_one(key, {"$set": {"imponibile": c["imponibile"], "imposta": c["imposta"], "totale": c["totale"], "store_id": s["id"], "updated_at": now, "fonte": "foglio_google"},
                                                            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}}, upsert=True)
            n_corr += 1 if r.upserted_id else 0
        if cid_fatt:
            for direzione, lst in (("emesse", p["emesse"]), ("ricevute", p["ricevute"])):
                for r in lst:
                    h = hashlib.sha1(f"{cid_fatt}|{direzione}|{r['numero']}|{r['data']}|{r['controparte']}|{r['totale']}".lower().encode()).hexdigest()
                    if await db.fatture_ade.find_one({"hash": h}, {"_id": 0, "id": 1}):
                        continue
                    await db.fatture_ade.insert_one({**r, "id": str(uuid.uuid4()), "hash": h, "centro_id": cid_fatt, "anno": anno, "mese": mese, "direzione": direzione,
                                                     "fonte": "foglio_google", "created_at": now})
                    if direzione == "emesse":
                        n_em += 1
                    else:
                        n_ric += 1
        confronto = await _confronto(db, p, anno, mese, cid_fatt, per_centro, slug_store, store_centro, mese_dati) if mese_dati else []
        # Totali del foglio per il confronto mese per mese nel PDP (entrate = corrispettivi + fatture emesse; uscite = spese + fatture ricevute)
        for cid in set(per_centro) | ({cid_fatt} - {None}):
            negozi_cid = [n for n, d in p["negozi"].items() if slug_store.get(n) and store_centro.get(slug_store[n]["id"]) == cid]
            corr_f = round(sum(p["negozi"][n]["corrispettivi_foglio"] or 0 for n in negozi_cid), 2)
            spese_f = round(sum(v for n in negozi_cid for v in p["negozi"][n]["valori"].values()), 2)
            em_f = round(sum(x["totale"] for x in p["emesse"]), 2) if cid == cid_fatt else 0.0
            ric_f = round(sum(x["totale"] for x in p["ricevute"]), 2) if cid == cid_fatt else 0.0
            giorni_diff = [{"negozio": r["voce"].replace("Corrispettivi ", ""), "store_id": r["store_id"], **g} for r in confronto if r.get("store_id") and store_centro.get(r["store_id"]) == cid for g in (r.get("giorni") or []) if g.get("diff") is None or abs(g["diff"]) >= 0.5]
            await db.pdp_foglio_totali.update_one({"centro_id": cid, "anno": anno, "mese": mese},
                                                  {"$set": {"corrispettivi": corr_f, "emesse": em_f, "ricevute": ric_f, "spese": spese_f, "entrate": round(corr_f + em_f, 2), "uscite": round(spese_f + ric_f, 2), "at": now, "gid": gid,
                                                            "giorni_diff": giorni_diff}}, upsert=True)
        esito.append({"anno": anno, "mese": mese, "nuova_scheda": gid not in GIDS_PDP, "centri": list(per_centro.keys()), "voci": sum(len(v) for v in per_centro.values()), "corrispettivi_ade_nuovi": n_corr,
                      "confronto": confronto,
                      "fatture_emesse_nuove": n_em, "fatture_ricevute_nuove": n_ric, "tot_emesse_foglio": round(sum(x["totale"] for x in p["emesse"]), 2),
                      "tot_ricevute_foglio": round(sum(x["totale"] for x in p["ricevute"]), 2), "corrispettivi_foglio": round(sum(x["totale"] for x in p["corrispettivi"]), 2),
                      "mese_rilevato": p["mese_rilevato"]})
    return esito
