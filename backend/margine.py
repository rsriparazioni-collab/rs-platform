"""Conto economico mensile: ogni euro ha una sola fonte (banca / fattura AdE / spesa cassa)."""
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/margine")
_d: dict = {}

CAT_BANCA = {
    "affitto": ("Affitti", "fisso"), "tasse": ("Tasse e contributi (F24)", "fisso"), "stipendi": ("Stipendi", "fisso"),
    "commissioni": ("Commissioni e spese banca/POS", "fisso"), "altro_costo": ("Altri costi da banca", "fisso"),
    "fattura": ("Pagamento fattura (già nelle fatture)", None), "pos": ("Incasso POS (già nei corrispettivi)", None),
    "giroconto": ("Giroconto / versamento contanti / prelievo titolare", None), "ignora": ("Non è un costo", None),
}
CAT_FORNITORE = {"merce": ("Merce e ricambi", "variabile"), "utenze": ("Utenze", "fisso"), "servizi": ("Servizi (commercialista, telefonia, software…)", "fisso"), "passante": ("Passante (bollette rivendute)", None)}

AUTO_BANCA = [
    ("giroconto", ("giroconto", "versamento contant", "versamento di contant", "a favore del c/c", "da c/c", "prelievo", "prelevamento", "anticipo per transato")),
    ("tasse", ("f24", "delega unica", "delega", "tributi", "agenzia entrate", "inps", "inail", "pagamento imposte")),
    ("stipendi", ("stipend", "emolument", "busta paga", "retribuzion", "salario", "tfr")),
    ("commissioni", ("commission", "canone", "imposta di bollo", "spese tenuta", "competenze", "spese operazione", "recupero spese", "costo istantaneo")),
]
STOP = {"srl", "srls", "spa", "snc", "sas", "italia", "spa.", "s.p.a", "s.r.l", "di", "e", "the", "group", "payments", "bonifico", "favore", "a", "pagamento", "sepa", "disposto"}


def setup(**deps):
    _d.update(deps)


def _now():
    return datetime.now(timezone.utc)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    return await _d["get_current_user"](request, creds)


async def _admin(user: dict = Depends(_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _tokens(s: str) -> list:
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 3 and t not in STOP]


def chiave_beneficiario(desc: str) -> str:
    """Chiave stabile del beneficiario da una descrizione banca."""
    d = (desc or "").lower()
    m = re.search(r"a favore di:?\s*(.+)", d)
    if m:
        d = m.group(1)
    elif "pagamento pos" in d or "pagamento su pos" in d:
        return "pagamento pos con carta"
    elif "commissioni transato pos" in d:
        return "commissioni transato pos"
    d = re.sub(r"\d[\d./,:-]*", " ", d)
    d = re.sub(r"\b(bonifico|sepa|disposto|voi|beneficiario|pagamento|addebito|diretto|effettuato|alle|ore|per|del|da|di|a|il|la|le|in|con|ns|vs|rif|cro|trn|favore)\b", " ", d)
    tok = [t for t in re.split(r"[^a-z]+", d) if len(t) >= 2 and t not in STOP]
    return " ".join(tok[:3]) or (desc or "").strip().lower()[:40]


def chiave_fornitore(controparte: str) -> str:
    return " ".join(_tokens(controparte)[:3]) or (controparte or "").strip().lower()[:40]


def _auto_banca(desc: str, beneficiari_affitto: list) -> Optional[str]:
    d = (desc or "").lower()
    if any(_match_benef(d, b) for b in beneficiari_affitto):
        return "affitto"
    for cat, keys in AUTO_BANCA:
        if any(k in d for k in keys):
            return cat
    return None


def _match_benef(desc_lower: str, beneficiario: str) -> bool:
    parole = [p for p in (beneficiario or "").lower().replace(",", " ").split() if len(p) >= 3]
    return bool(parole) and all(p in desc_lower for p in parole)


async def _regole_banca(entita: str) -> dict:
    return {r["chiave"]: r async for r in _d["db"].banca_regole.find({"entita": entita}, {"_id": 0})}


async def _regole_fornitori(centro_id: str) -> dict:
    return {r["chiave"]: r async for r in _d["db"].fornitori_regole.find({"centro_id": centro_id}, {"_id": 0})}


async def _beneficiari_affitto(centro_id: str) -> list:
    out = []
    async for s in _d["db"].scadenze_f24.find({"centro_id": centro_id, "beneficiario": {"$nin": [None, ""]}}, {"_id": 0, "beneficiario": 1}):
        out.append(s["beneficiario"])
    return out


class RegolaBancaInput(BaseModel):
    entita: str
    chiave: str
    categoria: str
    esempio: str = ""


class RegolaFornitoreInput(BaseModel):
    centro_id: str
    chiave: str
    categoria: str
    esempio: str = ""


@router.put("/regola-banca")
async def put_regola_banca(body: RegolaBancaInput, user: dict = Depends(_admin)):
    if body.categoria not in CAT_BANCA:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    doc = {"entita": body.entita, "chiave": body.chiave.strip().lower(), "categoria": body.categoria, "esempio": body.esempio[:120], "by": user["name"], "at": _now().isoformat()}
    await _d["db"].banca_regole.update_one({"entita": doc["entita"], "chiave": doc["chiave"]}, {"$set": doc}, upsert=True)
    return doc


@router.put("/regola-fornitore")
async def put_regola_fornitore(body: RegolaFornitoreInput, user: dict = Depends(_admin)):
    if body.categoria not in CAT_FORNITORE:
        raise HTTPException(status_code=400, detail="Categoria non valida")
    doc = {"centro_id": body.centro_id, "chiave": body.chiave.strip().lower(), "categoria": body.categoria, "esempio": body.esempio[:120], "by": user["name"], "at": _now().isoformat()}
    await _d["db"].fornitori_regole.update_one({"centro_id": doc["centro_id"], "chiave": doc["chiave"]}, {"$set": doc}, upsert=True)
    return doc


@router.get("/categorie")
async def categorie(user: dict = Depends(_admin)):
    return {"banca": [{"id": k, "label": v[0]} for k, v in CAT_BANCA.items()], "fornitore": [{"id": k, "label": v[0]} for k, v in CAT_FORNITORE.items()]}


async def conto_economico(entita: str, anno: int, mese: int) -> dict:
    db = _d["db"]
    ENTITA_CENTRO, CONTI = _d["entita_centro"], _d["conti"]
    if entita not in ENTITA_CENTRO:
        raise HTTPException(status_code=400, detail="Entità non valida")
    centro = next(c for c in await _d["centri_tutti"]() if c["id"] == ENTITA_CENTRO[entita])
    pref = f"{anno:04d}-{mese:02d}"
    stores = {s["id"]: s["nome"] async for s in db.stores.find({"id": {"$in": centro["store_ids"]}}, {"_id": 0, "id": 1, "nome": 1})}

    # 1) ENTRATE: scontrini per negozio + fatture emesse AdE (le fatture scritte nelle chiusure sono le stesse: non si sommano)
    scontrini_negozio = {}
    for sid in centro["store_ids"]:
        t = (await _d["mese_dati"](sid, anno, mese))["totali"]
        scontrini_negozio[sid] = round(t.get("scontrini", t["totale"] - t.get("fatture", 0)), 2)
    scontrini = round(sum(scontrini_negozio.values()), 2)
    emesse = 0.0
    async for f in db.fatture_ade.find({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "emesse"}, {"_id": 0, "totale": 1}):
        emesse += _f(f.get("totale"))
    emesse = round(emesse, 2)
    entrate = round(scontrini + emesse, 2)

    # 2) FATTURE RICEVUTE AdE per fornitore, classificate
    regole_f = await _regole_fornitori(centro["id"])
    fornitori: dict = {}
    fatture_ids = []
    async for f in db.fatture_ade.find({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "ricevute"}, {"_id": 0, "id": 1, "controparte": 1, "totale": 1}):
        k = chiave_fornitore(f.get("controparte"))
        g = fornitori.setdefault(k, {"chiave": k, "nome": (f.get("controparte") or "Sconosciuto").strip(), "totale": 0.0, "n": 0, "categoria": (regole_f.get(k) or {}).get("categoria")})
        g["totale"] = round(g["totale"] + _f(f.get("totale")), 2)
        g["n"] += 1
        fatture_ids.append(f["id"])
    # fatture "non dovute" (note di credito/storni) non sono costi
    non_dovute = {p["fattura_id"] async for p in db.fatture_pagamenti.find({"fattura_id": {"$in": fatture_ids}, "modo": "non_dovuta"}, {"_id": 0, "fattura_id": 1})}
    if non_dovute:
        async for f in db.fatture_ade.find({"id": {"$in": list(non_dovute)}}, {"_id": 0, "controparte": 1, "totale": 1}):
            g = fornitori.get(chiave_fornitore(f.get("controparte")))
            if g:
                g["totale"] = round(g["totale"] - _f(f.get("totale")), 2)
                g["n"] -= 1
    estere = await _d["estere_totale"](centro["id"], anno, mese)
    if estere:
        fornitori["__estere__"] = {"chiave": "__estere__", "nome": "Fatture estere (reverse charge / dogana)", "totale": estere, "n": 0, "categoria": "merce", "fissa": True}

    # 3) BANCA: uscite classificate; quelle che pagano una fattura AdE sono escluse (la fattura è già il costo)
    ric = await _d["riconciliazione"](entita, anno, mese, user={"role": "admin"})
    pagano_fattura = {p["movimento"]["id"] for p in ric.get("fatture_pagate", [])}
    regole_b = await _regole_banca(entita)
    benef_affitto = await _beneficiari_affitto(centro["id"])
    banca_ids = [c["id"] for c in CONTI if c["entita"] == entita and c["tipo"] == "banca"]
    banca: dict = {}
    async for m in db.movimenti_banca.find({"conto_id": {"$in": banca_ids}, "data": {"$regex": f"^{pref}"}, "importo": {"$lt": 0}}, {"_id": 0, "id": 1, "data": 1, "importo": 1, "descrizione": 1}):
        if m["id"] in pagano_fattura:
            continue
        k = chiave_beneficiario(m.get("descrizione"))
        cat = (regole_b.get(k) or {}).get("categoria") or _auto_banca(m.get("descrizione"), benef_affitto)
        g = banca.setdefault(k, {"chiave": k, "nome": (m.get("descrizione") or "")[:70], "totale": 0.0, "n": 0, "categoria": cat, "auto": k not in regole_b and cat is not None, "movimenti": []})
        g["totale"] = round(g["totale"] + abs(m["importo"]), 2)
        g["n"] += 1
        if len(g["movimenti"]) < 6:
            g["movimenti"].append({"data": m["data"], "importo": abs(m["importo"]), "descrizione": (m.get("descrizione") or "")[:90]})

    # 4) SPESE CASSA: solo quelle senza fattura collegata (quelle con fattura sono già nelle fatture ricevute)
    con_fattura = {p["spesa_cassa_id"] async for p in db.fatture_pagamenti.find({"spesa_cassa_id": {"$nin": [None, ""]}}, {"_id": 0, "spesa_cassa_id": 1})}
    spese_cassa, spese_cassa_n, spese_cassa_fatt = 0.0, 0, 0.0
    async for s in db.spese_cassa.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "id": 1, "importo": 1}):
        if s["id"] in con_fattura:
            spese_cassa_fatt += _f(s.get("importo"))
            continue
        spese_cassa += _f(s.get("importo"))
        spese_cassa_n += 1
    spese_cassa = round(spese_cassa, 2)

    # 5) TOTALI
    def somma(gruppi, cats):
        return round(sum(g["totale"] for g in gruppi.values() if g["categoria"] in cats), 2)

    merce = somma(fornitori, {"merce"})
    utenze = somma(fornitori, {"utenze"})
    servizi = somma(fornitori, {"servizi"})
    passante = somma(fornitori, {"passante"})
    forn_da_class = somma(fornitori, {None})
    banca_tot = {c: somma(banca, {c}) for c in ("affitto", "tasse", "stipendi", "commissioni", "altro_costo")}
    banca_da_class = somma(banca, {None})
    costi_fissi = round(utenze + servizi + sum(banca_tot.values()) + spese_cassa, 2)
    margine_lordo = round(entrate - merce, 2)
    risultato = round(margine_lordo - costi_fissi, 2)
    da_classificare = round(forn_da_class + banca_da_class, 2)

    # 6) PER NEGOZIO (ditta: Morbegno/Gravedona): entrate esatte, costi ripartiti in proporzione agli scontrini
    per_negozio = []
    if len(centro["store_ids"]) > 1 and scontrini:
        for sid in centro["store_ids"]:
            q = scontrini_negozio[sid] / scontrini
            e = round(scontrini_negozio[sid] + emesse * q, 2)
            ml = round(e - merce * q, 2)
            per_negozio.append({"store_id": sid, "nome": stores.get(sid, sid), "quota_pct": round(q * 100, 1), "entrate": e, "merce": round(merce * q, 2), "margine_lordo": ml,
                                "costi_fissi": round(costi_fissi * q, 2), "risultato": round(ml - costi_fissi * q, 2)})

    return {"entita": entita, "centro": centro["nome"], "centro_id": centro["id"], "anno": anno, "mese": mese,
            "entrate": {"scontrini": scontrini, "scontrini_per_negozio": [{"nome": stores.get(s, s), "totale": v} for s, v in scontrini_negozio.items()], "fatture_emesse": emesse, "totale": entrate},
            "costi_variabili": {"merce": merce},
            "costi_fissi": {"utenze": utenze, "servizi": servizi, **banca_tot, "spese_cassa": spese_cassa, "totale": costi_fissi},
            "passante": passante, "spese_cassa_n": spese_cassa_n, "spese_cassa_con_fattura": round(spese_cassa_fatt, 2),
            "fatture_pagate_banca": len(pagano_fattura), "fatture_aperte": len(ric.get("fatture_non_trovate_in_banca", [])),
            "margine_lordo": margine_lordo, "margine_lordo_pct": round(margine_lordo / entrate * 100, 1) if entrate else None,
            "risultato": risultato, "da_classificare": da_classificare,
            "fornitori": sorted(fornitori.values(), key=lambda g: (g["categoria"] is not None, -g["totale"])),
            "banca": sorted(banca.values(), key=lambda g: (g["categoria"] is not None, -g["totale"])),
            "per_negozio": per_negozio, "categorie": {"banca": {k: v[0] for k, v in CAT_BANCA.items()}, "fornitore": {k: v[0] for k, v in CAT_FORNITORE.items()}}}


@router.get("/conto-economico")
async def get_conto_economico(entita: str, anno: int, mese: int, user: dict = Depends(_admin)):
    return await conto_economico(entita, anno, mese)
