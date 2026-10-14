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

MAP_VOCI = {"eolo": "entrate|Eolo", "energia": "entrate|Energia / Enel", "telefonia": "entrate|Telefonia", "pacchi": "entrate|Pacchi",
            "stipendi": "spese_fisse|Stipendi", "contributi": "spese_fisse|Contributi", "tfr": "spese_fisse|TFR", "inail": "spese_fisse|INAIL",
            "condominio": "spese_fisse|Condominio", "affitti": "spese_fisse|Affitti", "utenze": "spese_fisse|Utenze",
            "commercialista": "spese_fisse|Commercialista", "finanziamento": "spese_fisse|Finanziamento",
            "ritiri": "spese_semifisse|Ritiri", "publicittà": "spese_semifisse|Pubblicità", "pubblicità": "spese_semifisse|Pubblicità"}


def num(v) -> float:
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
    return {"negozi": negozi, "emesse": emesse, "ricevute": ricevute, "corrispettivi": corr, "mese_rilevato": mesi.most_common(1)[0][0] if mesi else None}


async def importa_pdp_fogli(db, fetch, centri: list, stores: list, user_name: str = "") -> list:
    slug_store = {(s["nome"] or "").strip().lower(): s for s in stores}
    store_centro = {sid: c["id"] for c in centri for sid in c["store_ids"]}
    esito = []
    now = datetime.now(timezone.utc).isoformat()
    for gid, (anno, mese) in GIDS_PDP.items():
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
        esito.append({"anno": anno, "mese": mese, "centri": list(per_centro.keys()), "voci": sum(len(v) for v in per_centro.values()), "corrispettivi_ade_nuovi": n_corr,
                      "fatture_emesse_nuove": n_em, "fatture_ricevute_nuove": n_ric, "tot_emesse_foglio": round(sum(x["totale"] for x in p["emesse"]), 2),
                      "tot_ricevute_foglio": round(sum(x["totale"] for x in p["ricevute"]), 2), "corrispettivi_foglio": round(sum(x["totale"] for x in p["corrispettivi"]), 2),
                      "mese_rilevato": p["mese_rilevato"]})
    return esito
