"""Liquidazione IVA per centro di costo, SOLO da dati fiscali: corrispettivi RT AdE, fatture emesse/ricevute AdE.
Nessuna stima: dove il dato manca il valore non è determinabile e viene segnalato. certezza: certo | incompleto | mancante."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/contabilita/iva", tags=["iva"])
_d: dict = {}

ALIQUOTE = (22.0, 10.0, 5.0, 4.0)
# Art. 19-bis1 DPR 633/72: limiti di detraibilità. Applicati solo se il fornitore corrisponde e SEMPRE segnalati come da verificare.
REGOLE_DETRAIBILITA = [
    (r"\b(tim|telecom|vodafone|wind|windtre|iliad|fastweb|ho\.|very|kena|postemobile)\b", 50, "Telefonia: detraibile 50% (art. 19-bis1 lett. g) salvo uso esclusivo aziendale documentato"),
    (r"carburant|benzin|gasolio|\beni\b|\bq8\b|\besso\b|\bip\b|tamoil|shell", 40, "Carburanti veicoli uso promiscuo: 40% (art. 19-bis1 lett. c)"),
    (r"autostrad|telepass|parcheggio", 40, "Pedaggi/parcheggi veicoli uso promiscuo: 40%"),
]
NATURA_LABEL = {"esclusa": "Esclusa (N1, art. 15)", "non_soggetta": "Non soggetta (N2)", "non_imponibile": "Non imponibile (N3)", "esente": "Esente (N4, art. 10)",
                "regime_margine": "Regime del margine (N5)", "reverse_charge": "Inversione contabile (N6)", "iva_altro_stato": "IVA assolta in altro Stato UE (N7)",
                "forfettario": "Fornitore in regime forfettario", "da_verificare": "Natura IVA da verificare", "imponibile": "Imponibile"}


def setup(**deps):
    _d.update(deps)


def _r(v) -> float:
    return round(float(v or 0), 2)


def _e(v) -> str:
    return "€ " + f"{_r(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def classifica_aliquota(imponibile: float, imposta: float) -> Optional[float]:
    """Aliquota implicita del documento; None = mista/non standard."""
    if abs(imponibile) < 0.005:
        return 0.0 if abs(imposta) < 0.005 else None
    a = imposta / imponibile * 100
    if abs(a) < 0.05:
        return 0.0
    return next((s for s in ALIQUOTE if abs(a - s) <= 0.6), None)


def detraibilita(controparte: str) -> tuple:
    c = (controparte or "").lower()
    for pat, pct, motivo in REGOLE_DETRAIBILITA:
        if re.search(pat, c):
            return pct, motivo
    return 100, ""


def _doc(f: dict) -> str:
    return f"{f.get('tipo', '')} {f.get('numero', '')} {f.get('controparte', '')}".strip()


async def _fatture(db, centro_id: str, anno: int, mese: int, direzione: str) -> dict:
    import fatture_ade
    per_aliq: dict = {}
    nature: dict = {}
    anomalie, imp_tot, iva_tot, detraibile = [], 0.0, 0.0, 0.0
    nc = {"n": 0, "imponibile": 0.0, "imposta": 0.0, "totale": 0.0}
    n = 0
    async for f in db.fatture_ade.find({"centro_id": centro_id, "anno": anno, "mese": mese, "direzione": direzione}, {"_id": 0}):
        n += 1
        imp, iva = _r(f.get("imponibile")), _r(f.get("imposta"))
        natura = f.get("natura_iva") or fatture_ade.natura_iva(f)
        if fatture_ade.is_nota_credito(f.get("tipo", "")):
            nc["n"] += 1; nc["imponibile"] = _r(nc["imponibile"] + imp); nc["imposta"] = _r(nc["imposta"] + iva); nc["totale"] = _r(nc["totale"] + _r(f.get("totale")))
        aliq = classifica_aliquota(imp, iva)
        if aliq == 0.0:
            key = natura
            slot = per_aliq.setdefault(key, {"aliquota": 0.0, "natura": natura, "label": NATURA_LABEL.get(natura, natura), "imponibile": 0.0, "imposta": 0.0, "n": 0})
        else:
            key = "mista" if aliq is None else f"{aliq:g}"
            slot = per_aliq.setdefault(key, {"aliquota": aliq, "natura": "imponibile", "label": "Mista / non standard" if aliq is None else f"{aliq:g}%", "imponibile": 0.0, "imposta": 0.0, "n": 0})
        slot["imponibile"] = _r(slot["imponibile"] + imp); slot["imposta"] = _r(slot["imposta"] + iva); slot["n"] += 1
        imp_tot += imp; iva_tot += iva
        if aliq == 0.0 and imp:
            nature[natura] = nature.get(natura, 0) + 1
            if natura == "da_verificare":
                anomalie.append({"tipo": "natura_da_verificare", "id": f.get("id"), "doc": _doc(f), "imponibile": imp, "imposta": 0.0, "natura_iva": natura,
                                 "msg": "IVA zero senza codice natura (N1–N7): indicare se esente, non imponibile, esclusa, forfettario o reverse charge. Trattamento non assegnato."})
            elif natura == "reverse_charge" and direzione == "ricevute":
                anomalie.append({"tipo": "reverse_charge", "id": f.get("id"), "doc": _doc(f), "imponibile": imp, "imposta": 0.0, "natura_iva": natura,
                                 "msg": "Inversione contabile: obbligo di integrazione (IVA a debito e a credito sullo stesso imponibile) e doppia registrazione. Non calcolata automaticamente."})
        elif aliq is None:
            anomalie.append({"tipo": "aliquota_non_standard", "id": f.get("id"), "doc": _doc(f), "imponibile": imp, "imposta": iva, "natura_iva": natura,
                             "msg": "IVA non riconducibile a una sola aliquota: documento con più aliquote (riepilogo per aliquota non disponibile nell'export)."})
        if direzione == "ricevute":
            pct, motivo = detraibilita(f.get("controparte", ""))
            quota = _r(iva * pct / 100)
            detraibile += quota
            if pct < 100 and iva:
                anomalie.append({"tipo": "detraibilita_limitata", "id": f.get("id"), "doc": _doc(f), "imponibile": imp, "imposta": iva, "detraibile": quota, "natura_iva": natura, "msg": motivo})
    return {"n": n, "imponibile": _r(imp_tot), "imposta": _r(iva_tot), "detraibile": _r(detraibile) if direzione == "ricevute" else None,
            "note_credito": nc, "nature_iva_zero": {k: {"n": v, "label": NATURA_LABEL.get(k, k)} for k, v in nature.items()},
            "per_aliquota": sorted(per_aliq.values(), key=lambda x: (-(x["aliquota"] if x["aliquota"] is not None else -1), x["label"])), "anomalie": anomalie}


async def _vendite_negozio(db, store: dict, anno: int, mese: int, mese_dati) -> dict:
    """Corrispettivi del negozio SOLO da RT AdE. I giorni senza RT non vengono stimati: restano 'IVA non determinabile'."""
    pref = f"{anno:04d}-{mese:02d}"
    rt: dict = {}
    async for c in db.corrispettivi_ade.find({"store_id": store["id"], "data": {"$regex": f"^{pref}"}}, {"_id": 0}):
        slot = rt.setdefault(c["data"], {"imponibile": 0.0, "imposta": 0.0, "totale": 0.0, "aliquote": []})
        for k in ("imponibile", "imposta", "totale"):
            slot[k] = _r(slot[k] + _r(c.get(k)))
        slot["aliquote"] += c.get("aliquote") or []
    md = await mese_dati(store["id"], anno, mese)
    manuali = {r["data"]: r for r in md["righe"] if not r.get("vuoto")}
    f = _d["f"]
    per_aliq: dict = {}
    for d, c in rt.items():
        if c["aliquote"]:
            for a in c["aliquote"]:
                k = f"{_r(a.get('aliquota')):g}" if a.get("aliquota") is not None else (a.get("natura") or "mista")
                s = per_aliq.setdefault(k, {"aliquota": a.get("aliquota"), "label": f"{_r(a.get('aliquota')):g}%" if a.get("aliquota") is not None else k, "imponibile": 0.0, "imposta": 0.0})
                s["imponibile"] = _r(s["imponibile"] + _r(a.get("imponibile"))); s["imposta"] = _r(s["imposta"] + _r(a.get("imposta")))
        else:
            al = classifica_aliquota(c["imponibile"], c["imposta"])
            k = "mista" if al is None else f"{al:g}"
            s = per_aliq.setdefault(k, {"aliquota": al, "label": "Mista (dettaglio aliquote non nell'export RT)" if al is None else f"{al:g}%", "imponibile": 0.0, "imposta": 0.0})
            s["imponibile"] = _r(s["imponibile"] + c["imponibile"]); s["imposta"] = _r(s["imposta"] + c["imposta"])
    giorni_mancanti = [{"data": d, "scontrini": _r(f(r.get("riparazioni")) + f(r.get("merce")) + f(r.get("art74")))} for d, r in sorted(manuali.items())
                       if d not in rt and (f(r.get("riparazioni")) + f(r.get("merce")) + f(r.get("art74"))) > 0]
    discordanti = [{"data": d, "scontrini": _r(f(r.get("riparazioni")) + f(r.get("merce")) + f(r.get("art74"))), "rt": rt[d]["totale"]} for d, r in sorted(manuali.items())
                   if d in rt and abs(_r(f(r.get("riparazioni")) + f(r.get("merce")) + f(r.get("art74"))) - rt[d]["totale"]) >= 0.01]
    solo_rt = [{"data": d, "rt": c["totale"]} for d, c in sorted(rt.items()) if d not in manuali]
    giorni_attesi = len(set(manuali) | set(rt))
    out = {"store_id": store["id"], "store_nome": store["nome"], "giorni_rt": len(rt), "giorni_manuali": len(manuali), "giorni_attesi": giorni_attesi,
           "copertura_pct": round(len(rt) / giorni_attesi * 100, 1) if giorni_attesi else None,
           "imponibile": _r(sum(c["imponibile"] for c in rt.values())), "imposta": _r(sum(c["imposta"] for c in rt.values())), "totale_rt": _r(sum(c["totale"] for c in rt.values())),
           "scontrini_manuali_lordi": _r(md["totali"].get("scontrini") or 0), "art74_manuale": _r(md["totali"].get("art74")),
           "non_determinabile_lordo": _r(sum(g["scontrini"] for g in giorni_mancanti)),
           "per_aliquota": sorted(per_aliq.values(), key=lambda x: -(x["aliquota"] if x["aliquota"] is not None else -1)),
           "giorni_mancanti_rt": giorni_mancanti, "giorni_discordanti": discordanti, "giorni_solo_rt": solo_rt}
    out["certezza"] = "mancante" if not rt and manuali else ("certo" if rt and not giorni_mancanti else ("incompleto" if rt else "nessun_dato"))
    return out


async def calcolo_iva(centro: dict, anno: int, mese: int) -> dict:
    db = _d["db"]
    import fatture_ade
    stores = {s["id"]: s async for s in db.stores.find({"id": {"$in": centro["store_ids"]}}, {"_id": 0, "id": 1, "nome": 1})}
    vendite = [await _vendite_negozio(db, stores[sid], anno, mese, _d["mese_dati"]) for sid in centro["store_ids"] if sid in stores]
    emesse = await _fatture(db, centro["id"], anno, mese, "emesse")
    ricevute = await _fatture(db, centro["id"], anno, mese, "ricevute")
    # Fatture scritte nelle chiusure manuali ↔ fatture AdE (no doppio conteggio)
    manuali = []
    for sid in centro["store_ids"]:
        for r in (await _d["mese_dati"](sid, anno, mese))["righe"]:
            for x in r.get("fatture_dettaglio") or []:
                manuali.append({"store_id": sid, "store_nome": stores.get(sid, {}).get("nome", ""), "data": r["data"], **x})
    ade_em = await db.fatture_ade.find({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "emesse"}, {"_id": 0, "numero": 1, "totale": 1}).to_list(2000)
    riconciliate, non_riconciliate = fatture_ade.riconcilia_manuali(manuali, ade_em)

    cfg = await db.iva_periodi.find_one({"centro_id": centro["id"], "anno": anno, "mese": mese}, {"_id": 0}) or {}
    conf = await db.iva_config.find_one({"centro_id": centro["id"]}, {"_id": 0}) or {}
    periodicita = conf.get("periodicita")

    corr_imp = _r(sum(v["imponibile"] for v in vendite)); corr_iva = _r(sum(v["imposta"] for v in vendite))
    non_det = _r(sum(v["non_determinabile_lordo"] for v in vendite))
    determinabile = all(v["certezza"] in ("certo", "nessun_dato") for v in vendite) and not non_riconciliate
    debito = _r(corr_iva + emesse["imposta"])
    detraibile = _r(ricevute["detraibile"] or 0)
    rettifiche = _r(cfg.get("rettifiche"))
    credito_prec, credito_fonte = 0.0, "nessuno"
    if cfg.get("credito_precedente") is not None:
        credito_prec, credito_fonte = _r(cfg["credito_precedente"]), "manuale"
    else:
        pa, pm = (anno, mese - 1) if mese > 1 else (anno - 1, 12)
        prev = await db.iva_periodi.find_one({"centro_id": centro["id"], "anno": pa, "mese": pm}, {"_id": 0, "saldo_calcolato": 1, "certezza": 1})
        if prev and prev.get("saldo_calcolato") is not None and prev["saldo_calcolato"] < 0:
            credito_prec, credito_fonte = _r(-prev["saldo_calcolato"]), "riporto_automatico" if prev.get("certezza") == "certo" else "riporto_automatico_incompleto"
    saldo = _r(debito - detraibile - credito_prec + rettifiche)

    mancanti = []
    for v in vendite:
        if v["certezza"] == "mancante":
            mancanti.append(f"{v['store_nome']}: nessun corrispettivo telematico AdE nel mese → IVA su {_e(v['scontrini_manuali_lordi'])} di scontrini NON determinabile")
        elif v["certezza"] == "incompleto":
            mancanti.append(f"{v['store_nome']}: RT AdE presente per {v['giorni_rt']}/{v['giorni_attesi']} giorni; {len(v['giorni_mancanti_rt'])} giorni con scontrini manuali ({_e(v['non_determinabile_lordo'])}) senza RT → IVA non conteggiata, non stimata")
        if v["giorni_discordanti"]:
            mancanti.append(f"{v['store_nome']}: {len(v['giorni_discordanti'])} giorni con scontrini manuali ≠ RT AdE")
        if v["giorni_solo_rt"]:
            mancanti.append(f"{v['store_nome']}: {len(v['giorni_solo_rt'])} giorni nell'RT AdE senza chiusura manuale")
    if non_riconciliate:
        mancanti.append(f"{len(non_riconciliate)} fatture scritte nelle chiusure ({_e(sum(x['importo'] for x in non_riconciliate))}) senza documento AdE corrispondente: IVA non determinabile, da importare dall'AdE")
    if emesse["n"] == 0:
        mancanti.append("Nessuna fattura emessa importata dall'AdE per il mese")
    if ricevute["n"] == 0:
        mancanti.append("Nessuna fattura ricevuta importata dall'AdE: IVA detraibile = 0 (non stimata)")
    n_dv = sum(1 for a in emesse["anomalie"] + ricevute["anomalie"] if a["tipo"] == "natura_da_verificare")
    if n_dv:
        mancanti.append(f"{n_dv} documenti a IVA zero con natura da verificare")
    if credito_fonte == "riporto_automatico_incompleto":
        mancanti.append("Credito precedente riportato da un mese con dati incompleti")
    if not periodicita:
        mancanti.append("Periodicità IVA (mensile/trimestrale) non impostata: scadenza non calcolata")
    if cfg.get("iva_foglio") is not None:
        mancanti.append(f"Foglio Google: IVA {_e(cfg['iva_foglio'])} vs saldo calcolato {_e(saldo)} (diff {_e(saldo - cfg['iva_foglio'])})")

    certezza = "certo" if determinabile and emesse["n"] + ricevute["n"] > 0 and not any(a["tipo"] in ("natura_da_verificare", "aliquota_non_standard") for a in emesse["anomalie"]) and credito_fonte != "riporto_automatico_incompleto" \
        else ("mancante" if any(v["certezza"] == "mancante" for v in vendite) and emesse["n"] == 0 else "incompleto")
    await db.iva_periodi.update_one({"centro_id": centro["id"], "anno": anno, "mese": mese}, {"$set": {"saldo_calcolato": saldo, "certezza": certezza, "calcolato_at": datetime.now(timezone.utc).isoformat()}, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)

    scadenza, nota_scad, interessi = None, "", 0.0
    if periodicita == "trimestrale":
        qe = ((mese - 1) // 3 + 1) * 3
        scadenza = f"{anno + 1:04d}-03-16" if qe == 12 else (f"{anno:04d}-{qe + 2:02d}-16" if qe + 2 <= 12 else f"{anno + 1:04d}-{qe + 2 - 12:02d}-16")
        nota_scad = "Trimestrale: 16 del secondo mese successivo al trimestre, interessi 1%"
        interessi = _r(saldo * 0.01) if saldo > 0 else 0.0
    elif periodicita == "mensile":
        scadenza = f"{anno:04d}-{mese + 1:02d}-16" if mese < 12 else f"{anno + 1:04d}-01-16"
        nota_scad = "Mensile: entro il 16 del mese successivo"
    return {"centro": {"id": centro["id"], "nome": centro["nome"]}, "anno": anno, "mese": mese, "periodicita": periodicita, "certezza": certezza,
            "vendite": {"determinabile": determinabile, "corrispettivi": {"imponibile": corr_imp, "imposta": corr_iva, "non_determinabile_lordo": non_det, "negozi": vendite},
                        "fatture_emesse": emesse, "fatture_manuali": {"riconciliate": riconciliate, "non_riconciliate": non_riconciliate},
                        "imponibile_totale": _r(corr_imp + emesse["imponibile"]), "iva_debito": debito, "per_aliquota": _per_aliquota_vendite(vendite, emesse)},
            "acquisti": {"fatture_ricevute": ricevute, "imponibile_totale": ricevute["imponibile"], "iva_totale": ricevute["imposta"], "iva_detraibile": detraibile,
                         "iva_indetraibile": _r(ricevute["imposta"] - detraibile)},
            "rettifiche": rettifiche, "credito_precedente": credito_prec, "credito_fonte": credito_fonte, "saldo": saldo,
            "saldo_tipo": "da_versare" if saldo > 0 else ("a_credito" if saldo < 0 else "zero"), "scadenza": scadenza, "scadenza_nota": nota_scad, "interessi_trimestrale": interessi,
            "mancanti": mancanti, "anomalie": emesse["anomalie"] + ricevute["anomalie"], "note": cfg.get("note", ""), "iva_foglio": cfg.get("iva_foglio"), "nature_label": NATURA_LABEL}


def _per_aliquota_vendite(vendite: list, emesse: dict) -> list:
    rows: dict = {}
    for v in vendite:
        for a in v["per_aliquota"]:
            key = a["label"]
            slot = rows.setdefault(key, {"aliquota": a["aliquota"], "label": a["label"], "imponibile": 0.0, "imposta": 0.0, "fonte": set()})
            slot["imponibile"] = _r(slot["imponibile"] + a["imponibile"]); slot["imposta"] = _r(slot["imposta"] + a["imposta"]); slot["fonte"].add("RT AdE")
    for a in emesse["per_aliquota"]:
        slot = rows.setdefault(a["label"], {"aliquota": a["aliquota"], "label": a["label"], "imponibile": 0.0, "imposta": 0.0, "fonte": set()})
        slot["imponibile"] = _r(slot["imponibile"] + a["imponibile"]); slot["imposta"] = _r(slot["imposta"] + a["imposta"]); slot["fonte"].add("fatture AdE"); slot["n"] = a["n"]
    return [{**r, "fonte": sorted(r["fonte"])} for r in sorted(rows.values(), key=lambda x: (-(x["aliquota"] if x["aliquota"] is not None else -1), x["label"]))]


@router.get("")
async def get_iva(centro_id: str, anno: int, mese: int, request: Request):
    user = await _d["user"](request)
    centro = await _d["centro"](user, centro_id)
    if not 1 <= mese <= 12:
        raise HTTPException(status_code=400, detail="Mese non valido")
    return await calcolo_iva(centro, anno, mese)


class PeriodoInput(BaseModel):
    credito_precedente: Optional[float] = None
    rettifiche: Optional[float] = None
    note: str = ""


@router.put("")
async def set_periodo(centro_id: str, anno: int, mese: int, body: PeriodoInput, request: Request):
    user = await _d["user"](request)
    centro = await _d["centro"](user, centro_id)
    upd = {"note": body.note[:500], "updated_by": user.get("name", ""), "updated_at": datetime.now(timezone.utc).isoformat()}
    unset = {}
    for k in ("credito_precedente", "rettifiche"):
        v = getattr(body, k)
        if v is None:
            unset[k] = ""
        else:
            upd[k] = v
    op = {"$set": upd, "$setOnInsert": {"id": str(uuid.uuid4())}}
    if unset:
        op["$unset"] = unset
    await _d["db"].iva_periodi.update_one({"centro_id": centro_id, "anno": anno, "mese": mese}, op, upsert=True)
    return await calcolo_iva(centro, anno, mese)


class ConfigInput(BaseModel):
    periodicita: str


@router.put("/config")
async def set_config(centro_id: str, body: ConfigInput, request: Request):
    user = await _d["user"](request)
    await _d["centro"](user, centro_id)
    if body.periodicita not in ("mensile", "trimestrale"):
        raise HTTPException(status_code=400, detail="periodicita: mensile|trimestrale")
    await _d["db"].iva_config.update_one({"centro_id": centro_id}, {"$set": {"periodicita": body.periodicita, "updated_by": user.get("name", "")}, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return {"ok": True, "periodicita": body.periodicita}


@router.get("/anno")
async def iva_anno(centro_id: str, anno: int, request: Request):
    user = await _d["user"](request)
    centro = await _d["centro"](user, centro_id)
    oggi = datetime.now(timezone.utc)
    mesi = []
    for m in range(1, 13):
        if (anno, m) > (oggi.year, oggi.month):
            break
        r = await calcolo_iva(centro, anno, m)
        mesi.append({"mese": m, "iva_debito": r["vendite"]["iva_debito"], "iva_detraibile": r["acquisti"]["iva_detraibile"], "credito_precedente": r["credito_precedente"], "rettifiche": r["rettifiche"],
                     "saldo": r["saldo"], "certezza": r["certezza"], "scadenza": r["scadenza"], "n_mancanti": len(r["mancanti"]), "n_anomalie": len(r["anomalie"]),
                     "non_determinabile_lordo": r["vendite"]["corrispettivi"]["non_determinabile_lordo"]})
    return {"anno": anno, "mesi": mesi}
