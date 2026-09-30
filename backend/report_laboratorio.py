from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter()
_d: dict = {}
STATI_LAVORATE = ["pronto", "pronto_ritiro", "consegnato"]


def setup(**deps):
    _d.update(deps)


async def _user(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    user = await _d["get_current_user"](request, creds)
    if user["role"] not in ("admin", "tecnico") and not user.get("can_view_all"):
        raise HTTPException(status_code=403, detail="Riservato ad amministratore e laboratorio")
    return user


def _mese_lavorazione(s: dict) -> str:
    for e in s.get("stato_log") or []:
        if e.get("stato") == "pronto":
            return e["at"][:7]
    return (s.get("lavorato_at") or s.get("data_lavorazione") or s.get("updated_at") or "")[:7]


TARIFFA_MINUTO = 0.22775


def _acquistato_da(s: dict, lab_store_id: str) -> str:
    """Chi ha comprato il ricambio: campo esplicito, altrimenti dedotto dal magazzino di provenienza (Morbegno = laboratorio)."""
    if s.get("ricambio_acquistato_da") in ("negozio", "laboratorio"):
        return s["ricambio_acquistato_da"]
    usati = s.get("ricambi_usati") or []
    if usati:
        return "laboratorio" if any((u.get("da_store_id") or s.get("venditore_id")) == lab_store_id for u in usati) else "negozio"
    return "laboratorio" if s.get("con_ricambio") else ""


async def calcola(anno: int, mese: int, tecnico_id: str, includi_non_attribuite: bool, min_manodopera: float, minuti_minimi: int = 10) -> dict:
    db = _d["db"]
    m = f"{anno:04d}-{mese:02d}"
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    lab_store_id = next((k for k, v in stores.items() if v.strip().lower() == "morbegno"), "")
    tecnici = await db.users.find({"role": "tecnico", "active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1}).to_list(20)
    if not tecnico_id and tecnici:
        tecnico_id = tecnici[0]["id"]
    q = {"tipo": "riparazione", "stato": {"$in": STATI_LAVORATE}}
    righe, non_attribuite = [], 0
    async for s in db.servizi.find(q, {"_id": 0}):
        if _mese_lavorazione(s) != m:
            continue
        attribuita = s.get("lavorato_da_id") == tecnico_id
        if not attribuita:
            if s.get("lavorato_da_id") or not includi_non_attribuite:
                if not s.get("lavorato_da_id"):
                    non_attribuite += 1
                continue
        con_ricambio = bool(s.get("con_ricambio"))
        ricambi_mag = round(sum(float(r.get("prezzo_vendita") or 0) * int(r.get("quantita") or 1) for r in s.get("ricambi_usati") or []), 2)
        ha_ricambio = con_ricambio or ricambi_mag > 0
        acquistato_da = _acquistato_da(s, lab_store_id) if ha_ricambio else ""
        costo_ricambio = round((float(s.get("costo_componente") or 0) + _d["spese_spedizione"]) if con_ricambio else ricambi_mag, 2)
        ricambio = costo_ricambio if acquistato_da == "laboratorio" else 0.0
        minuti = int(s.get("minuti_lavoro") or 0)
        minuti_calc = max(minuti, minuti_minimi)
        lavoro = round(minuti_calc * TARIFFA_MINUTO, 2)
        manodopera = lavoro if ha_ricambio else max(lavoro, min_manodopera)
        cli = await db.clients.find_one({"id": s["client_id"]}, {"_id": 0, "nome": 1, "cognome": 1})
        righe.append({"id": s["id"], "numero": s.get("numero_riparazione", "-"), "store_id": s.get("venditore_id", ""), "negozio": stores.get(s.get("venditore_id", ""), "-"),
                      "cliente": f"{(cli or {}).get('cognome', '')} {(cli or {}).get('nome', '')}".strip(), "dispositivo": s.get("dispositivo", ""), "guasto": s.get("guasto", ""),
                      "tipo": "ricambio" if ha_ricambio else "manodopera", "tipo_ricambio": s.get("tipo_ricambio", "") if con_ricambio else ("magazzino" if ricambi_mag else ""),
                      "acquistato_da": acquistato_da, "costo_ricambio": costo_ricambio,
                      "minuti": minuti, "minuti_calcolati": minuti_calc, "ricambio": round(ricambio, 2), "manodopera": round(manodopera, 2), "totale": round(ricambio + manodopera, 2),
                      "prezzo_cliente": s.get("prezzo_finale") or s.get("importo"), "stato": s.get("stato"), "data": (s.get("lavorato_at") or s.get("data_lavorazione") or "")[:10],
                      "attribuita": attribuita, "lavorato_da": s.get("lavorato_da", "")})
    negozi = defaultdict(lambda: {"n": 0, "n_ricambio": 0, "n_manodopera": 0, "ricambio": 0.0, "manodopera": 0.0, "totale": 0.0, "righe": []})
    for r in righe:
        g = negozi[r["store_id"]]
        g["negozio"], g["store_id"] = r["negozio"], r["store_id"]
        g["n"] += 1
        g["n_ricambio" if r["tipo"] == "ricambio" else "n_manodopera"] += 1
        for k in ("ricambio", "manodopera", "totale"):
            g[k] = round(g[k] + r[k], 2)
        g["righe"].append(r)
    out = sorted(negozi.values(), key=lambda g: g["negozio"])
    return {"mese": m, "tecnico_id": tecnico_id, "tecnici": tecnici, "min_manodopera": min_manodopera, "non_attribuite": non_attribuite, "negozi": out,
            "minuti_minimi": minuti_minimi, "totali": {"n": len(righe), "ricambio": round(sum(r["ricambio"] for r in righe), 2), "manodopera": round(sum(r["manodopera"] for r in righe), 2),
                       "totale": round(sum(r["totale"] for r in righe), 2)}}


@router.get("/riparazioni/report-laboratorio")
async def report_laboratorio(anno: int, mese: int, tecnico_id: str = "", includi_non_attribuite: bool = False, min_manodopera: float = 15, minuti_minimi: int = 10, user: dict = Depends(_user)):
    return await calcola(anno, mese, tecnico_id, includi_non_attribuite, min_manodopera, minuti_minimi)


async def addebiti_negozi(mese: str) -> dict:
    """{store_id: totale €} da addebitare ai negozi per il lavoro del laboratorio nel mese (escluso il negozio del laboratorio)."""
    anno, m = int(mese[:4]), int(mese[5:7])
    data = await calcola(anno, m, "", False, 15, 10)
    lab = next((g["store_id"] for g in data["negozi"] if g["negozio"].strip().lower() == "morbegno"), "")
    return {g["store_id"]: g["totale"] for g in data["negozi"] if g["store_id"] != lab and g["totale"]}


@router.get("/riparazioni/report-laboratorio/export")
async def report_laboratorio_export(anno: int, mese: int, tecnico_id: str = "", includi_non_attribuite: bool = False, min_manodopera: float = 15, minuti_minimi: int = 10, user: dict = Depends(_user)):
    data = await calcola(anno, mese, tecnico_id, includi_non_attribuite, min_manodopera, minuti_minimi)
    rows = []
    for g in data["negozi"]:
        for r in g["righe"]:
            rows.append([r["data"], g["negozio"], r["numero"], r["cliente"], r["dispositivo"], r["guasto"], "Ricambio" if r["tipo"] == "ricambio" else "Solo manodopera",
                         r["tipo_ricambio"], {"negozio": "Negozio", "laboratorio": "Laboratorio (Morbegno)"}.get(r["acquistato_da"], ""), r["costo_ricambio"], r["minuti"], r["minuti_calcolati"],
                         r["ricambio"], r["manodopera"], r["totale"], r["prezzo_cliente"] or "", r["stato"], r["lavorato_da"]])
        rows.append(["TOTALE", g["negozio"], f"{g['n']} riparazioni ({g['n_ricambio']} ricambio / {g['n_manodopera']} manodopera)", "", "", "", "", "", "", "", "", "", g["ricambio"], g["manodopera"], g["totale"], "", "", ""])
    rows.append(["TOTALE GENERALE", "", f"{data['totali']['n']} riparazioni", "", "", "", "", "", "", "", "", "", data["totali"]["ricambio"], data["totali"]["manodopera"], data["totali"]["totale"], "", "", ""])
    return _d["xlsx_response"]("Laboratorio", ["Data", "Negozio", "N. rip.", "Cliente", "Dispositivo", "Guasto", "Tipo", "Ricambio", "Ricambio acquistato da", "Costo ricambio €", "Minuti", "Minuti calcolati",
                                               "Addebito ricambio €", "Manodopera €", "Totale €", "Prezzo cliente €", "Stato", "Lavorato da"], rows, f"report_laboratorio_{data['mese']}.xlsx")
