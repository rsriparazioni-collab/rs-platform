"""Pianificazione fiscale per centro di costo: regime (ditta individuale IRPEF / SRLS IRES+IRAP), imposte stimate, acconti, scadenze, liquidità, simulazioni.
Tutti i parametri sono modificabili; finché non salvati dall'utente restano 'da_verificare'. Il reddito deriva dal PDP (netto IVA quando determinabile)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/contabilita/fiscale", tags=["fiscale"])
_d: dict = {}

DEFAULT_REGIME = {"morbegno+gravedona": "ditta_individuale"}
PARAMS_DEFAULT = {
    "ditta_individuale": {"irpef_scaglioni": [[28000, 23], [50000, 35], [None, 43]], "addizionale_regionale_pct": 1.23, "addizionale_comunale_pct": 0.8,
                          "inps_gestione_pct": 24.48, "inps_minimale_reddito": 18555.0, "inps_contributo_minimo": 4542.0, "acconto_pct": 100, "acconto_prima_rata_pct": 40},
    "srls": {"ires_pct": 24.0, "irap_pct": 3.9, "acconto_pct": 100, "acconto_prima_rata_pct": 40},
}


def setup(**deps):
    _d.update(deps)


def _r(v):
    return round(float(v or 0), 2)


def irpef(reddito: float, scaglioni: list) -> float:
    tot, prev = 0.0, 0.0
    for lim, pct in scaglioni:
        quota = max(0.0, (reddito if lim is None else min(reddito, lim)) - prev)
        tot += quota * pct / 100
        if lim is None or reddito <= lim:
            break
        prev = lim
    return _r(tot)


def imposte(regime: str, p: dict, reddito: float) -> dict:
    """Imposte annue stimate su un reddito imponibile. Regole dichiarate nel campo 'regole'."""
    r = max(reddito, 0.0)
    if regime == "srls":
        ires, irap = _r(r * p["ires_pct"] / 100), _r(r * p["irap_pct"] / 100)
        return {"voci": {"IRES": ires, "IRAP": irap}, "totale": _r(ires + irap),
                "regole": [f"IRES {p['ires_pct']}% sul reddito imponibile", f"IRAP {p['irap_pct']}% (base IRAP ≈ reddito; deduzioni costo lavoro non applicate)"]}
    inps = _r(max(r, p["inps_minimale_reddito"]) * p["inps_gestione_pct"] / 100) if r > 0 else _r(p["inps_contributo_minimo"])
    imponibile_irpef = max(r - inps, 0.0)
    ir = irpef(imponibile_irpef, p["irpef_scaglioni"])
    add = _r(imponibile_irpef * (p["addizionale_regionale_pct"] + p["addizionale_comunale_pct"]) / 100)
    return {"voci": {"INPS gestione commercianti": inps, "IRPEF": ir, "Addizionali regionale+comunale": add}, "totale": _r(inps + ir + add),
            "regole": [f"INPS {p['inps_gestione_pct']}% sul reddito (minimale € {p['inps_minimale_reddito']:,.0f}, contributo minimo € {p['inps_contributo_minimo']:,.0f})",
                       "IRPEF a scaglioni " + ", ".join(f"{pct}% fino a {lim:,.0f}" if lim else f"{pct}% oltre" for lim, pct in p["irpef_scaglioni"]) + " sul reddito al netto INPS",
                       f"Addizionali {p['addizionale_regionale_pct']}% + {p['addizionale_comunale_pct']}%", "Nessuna detrazione/deduzione personale applicata (da verificare col commercialista)"]}


async def _config(db, centro_id: str) -> dict:
    c = await db.fiscale_config.find_one({"centro_id": centro_id}, {"_id": 0})
    if c:
        return {**c, "da_verificare": False}
    regime = DEFAULT_REGIME.get(centro_id, "srls")
    return {"centro_id": centro_id, "regime": regime, "params": PARAMS_DEFAULT[regime], "imposte_anno_prec": None, "acconti_versati": 0.0, "da_verificare": True}


async def _mesi(centro: dict, anno: int, fino_mese: int) -> list:
    out = []
    for m in range(1, fino_mese + 1):
        p = await _d["pdp_calcolo"](centro, anno, m)
        iva = p["iva"]
        ricavi = iva["ricavi_netti"] if iva["determinabile"] and iva["ricavi_netti"] is not None else p["tot_entrate"]
        out.append({"mese": m, "ricavi": _r(ricavi), "ricavi_netti_iva": iva["determinabile"], "costi": p["tot_uscite"], "risultato": _r(ricavi - p["tot_uscite"]),
                    "incassato": _r(p["incasso"]["incassato"] + p["entrate"].get("Fatture emesse (AdE)", 0)), "iva_saldo": iva["saldo"], "iva_certezza": iva["certezza"]})
    return out


async def piano(centro: dict, anno: int, sim: Optional[dict] = None) -> dict:
    db = _d["db"]
    cfg = await _config(db, centro["id"])
    oggi = datetime.now(timezone.utc)
    fino = 12 if anno < oggi.year else (oggi.month if anno == oggi.year else 0)
    mesi = await _mesi(centro, anno, fino)
    n = len([m for m in mesi if m["ricavi"] or m["costi"]])
    ytd_ric, ytd_cost = _r(sum(m["ricavi"] for m in mesi)), _r(sum(m["costi"] for m in mesi))
    f_ric, f_cost = 1 + (sim or {}).get("ricavi_pct", 0) / 100, 1 + (sim or {}).get("costi_pct", 0) / 100
    prev_ric, prev_cost = (_r(ytd_ric / n * 12 * f_ric), _r(ytd_cost / n * 12 * f_cost)) if n else (0.0, 0.0)
    reddito_prev = _r(prev_ric - prev_cost)
    imp = imposte(cfg["regime"], cfg["params"], reddito_prev)
    p = cfg["params"]
    base_acc = cfg.get("imposte_anno_prec") if cfg.get("imposte_anno_prec") is not None else imp["totale"]
    acconto_tot = _r(base_acc * p["acconto_pct"] / 100)
    acc1, acc2 = _r(acconto_tot * p["acconto_prima_rata_pct"] / 100), _r(acconto_tot * (100 - p["acconto_prima_rata_pct"]) / 100)
    saldo_prossimo = _r(imp["totale"] - _r(cfg.get("acconti_versati")))
    scadenze = [{"data": f"{anno}-06-30", "voce": f"Saldo imposte {anno - 1} + 1º acconto {anno}", "importo": acc1, "certezza": "stima" if cfg.get("imposte_anno_prec") is None else "da parametri"},
                {"data": f"{anno}-11-30", "voce": f"2º acconto {anno}", "importo": acc2, "certezza": "stima" if cfg.get("imposte_anno_prec") is None else "da parametri"},
                {"data": f"{anno + 1}-06-30", "voce": f"Saldo imposte {anno} (stima − acconti versati)", "importo": saldo_prossimo, "certezza": "stima"}]
    if cfg["regime"] == "ditta_individuale":
        q = _r(p["inps_contributo_minimo"] / 4)
        scadenze += [{"data": f"{anno}-{mm}-16", "voce": "INPS quota fissa trimestrale", "importo": q, "certezza": "da parametri"} for mm in ("02", "05", "08", "11")]
    for m in mesi:
        if m["iva_saldo"] > 0:
            mm = m["mese"] + 1
            scadenze.append({"data": f"{anno + (mm > 12)}-{(mm - 1) % 12 + 1:02d}-16", "voce": f"IVA {m['mese']:02d}/{anno}", "importo": m["iva_saldo"], "certezza": m["iva_certezza"]})
    scadenze.sort(key=lambda s: s["data"])
    accantonamento_mese = _r(imp["totale"] / 12)
    liquidita = []
    cum = 0.0
    for m in mesi:
        netto = _r(m["incassato"] - m["costi"] - max(m["iva_saldo"], 0) - accantonamento_mese)
        cum = _r(cum + netto)
        liquidita.append({"mese": m["mese"], "incassato": m["incassato"], "costi": m["costi"], "iva": max(m["iva_saldo"], 0), "accantonamento_imposte": accantonamento_mese, "netto": netto, "cumulato": cum})
    return {"centro": {"id": centro["id"], "nome": centro["nome"]}, "anno": anno, "config": cfg, "mesi": mesi, "mesi_con_dati": n,
            "ytd": {"ricavi": ytd_ric, "costi": ytd_cost, "risultato": _r(ytd_ric - ytd_cost), "netto_iva_tutti_mesi": all(m["ricavi_netti_iva"] for m in mesi) if mesi else False},
            "previsione": {"ricavi": prev_ric, "costi": prev_cost, "reddito": reddito_prev, "simulazione": sim or {}},
            "imposte": imp, "acconti": {"base": base_acc, "totale": acconto_tot, "prima_rata": acc1, "seconda_rata": acc2, "versati": _r(cfg.get("acconti_versati")), "saldo_stimato": saldo_prossimo},
            "scadenze": scadenze, "liquidita": liquidita, "accantonamento_mese": accantonamento_mese,
            "avvertenze": ([f"Parametri fiscali non ancora confermati per {centro['nome']}: valori di default, da verificare col commercialista"] if cfg["da_verificare"] else [])
            + ([] if all(m["ricavi_netti_iva"] for m in mesi) else ["In alcuni mesi i ricavi netti IVA non sono determinabili: usato il fatturato lordo (reddito sovrastimato)"])
            + (["Acconti calcolati sulle imposte stimate dell'anno in corso: inserisci le imposte dell'anno precedente per il metodo storico"] if cfg.get("imposte_anno_prec") is None else [])}


@router.get("")
async def get_piano(centro_id: str, anno: int, request: Request, ricavi_pct: float = 0, costi_pct: float = 0):
    user = await _d["user"](request)
    centro = await _d["centro"](user, centro_id)
    return await piano(centro, anno, {"ricavi_pct": ricavi_pct, "costi_pct": costi_pct} if ricavi_pct or costi_pct else None)


class ConfigInput(BaseModel):
    regime: str
    params: dict
    imposte_anno_prec: Optional[float] = None
    acconti_versati: float = 0.0


@router.put("/config")
async def set_config(centro_id: str, body: ConfigInput, request: Request):
    user = await _d["user"](request)
    await _d["centro"](user, centro_id)
    if body.regime not in PARAMS_DEFAULT:
        raise HTTPException(status_code=400, detail="regime: ditta_individuale|srls")
    params = {**PARAMS_DEFAULT[body.regime], **{k: v for k, v in body.params.items() if k in PARAMS_DEFAULT[body.regime]}}
    await _d["db"].fiscale_config.update_one({"centro_id": centro_id}, {"$set": {"centro_id": centro_id, "regime": body.regime, "params": params, "imposte_anno_prec": body.imposte_anno_prec,
                                                                                 "acconti_versati": body.acconti_versati, "updated_by": user.get("name", ""), "updated_at": datetime.now(timezone.utc).isoformat()},
                                                                        "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return {"ok": True}


@router.get("/negozi")
async def pdp_negozi(anno: int, mese: int, request: Request):
    """PDP per negozio e azienda: ricavi lordi/netti IVA (RT), costi (cassa diretti + fissi/variabili del centro ripartiti pro quota), MDC, BEP, obiettivo, previsione annuale."""
    user = await _d["user"](request)
    db = _d["db"]
    centri = await _d["centri"](user)
    obiettivi = {o["store_id"]: o async for o in db.pdp_obiettivi.find({"anno": anno}, {"_id": 0})}
    negozi, tot = [], {"ricavi_lordi": 0.0, "ricavi_netti": 0.0, "costi_fissi": 0.0, "costi_variabili": 0.0, "risultato": 0.0, "obiettivo": 0.0, "ytd": 0.0, "netti_determinabili": True}
    for c in centri:
        p = await _d["pdp_calcolo"](c, anno, mese)
        iva = await _d["calcolo_iva"](c, anno, mese)
        rt = {v["store_id"]: v for v in iva["vendite"]["corrispettivi"]["negozi"]}
        lordi = {sid: _r(p["corrispettivi_per_negozio"].get(sid, 0)) for sid in c["store_ids"]}
        tot_lordo_c = sum(lordi.values()) or 1.0
        fatture_c = _r(p["tot_entrate"] - sum(lordi.values()))
        fissi_c, var_c = p["break_even"]["costi_fissi"], p["break_even"]["costi_variabili"]
        for sid in c["store_ids"]:
            s = await db.stores.find_one({"id": sid}, {"_id": 0, "nome": 1}) or {}
            quota = lordi[sid] / tot_lordo_c
            v = rt.get(sid, {})
            netti_ok = v.get("certezza") == "certo"
            ricavi_lordi = _r(lordi[sid] + fatture_c * quota)
            ricavi_netti = _r(v.get("imponibile", 0) + (p["ade_dettaglio"]["emesse_imponibile"] * quota)) if netti_ok else None
            fissi, var = _r(fissi_c * quota), _r(var_c * quota)
            mdc = _r((ricavi_netti if ricavi_netti is not None else ricavi_lordi) - var)
            base = ricavi_netti if ricavi_netti is not None else ricavi_lordi
            bep = _r(fissi / (mdc / base)) if base and mdc > 0 and fissi else None
            ytd = 0.0
            for m in range(1, mese + 1):
                ytd += _r((await _d["mese_dati"](sid, anno, m))["totali"]["totale"])
            ob = obiettivi.get(sid, {})
            row = {"store_id": sid, "store_nome": s.get("nome", sid), "centro": c["nome"], "quota_pct": round(quota * 100, 1), "ricavi_lordi": ricavi_lordi, "ricavi_netti": ricavi_netti,
                   "netti_certezza": v.get("certezza", "nessun_dato"), "copertura_rt": f"{v.get('giorni_rt', 0)}/{v.get('giorni_attesi', 0)}", "costi_fissi": fissi, "costi_variabili": var,
                   "mdc": mdc, "mdc_pct": round(mdc / base * 100, 1) if base else None, "bep": bep, "risultato": _r(base - var - fissi),
                   "obiettivo_mese": _r(ob.get("obiettivo_mese")), "obiettivo_anno": _r(ob.get("obiettivo_anno")), "scostamento": _r(ricavi_lordi - _r(ob.get("obiettivo_mese"))) if ob.get("obiettivo_mese") else None,
                   "ytd_lordo": _r(ytd), "previsione_anno": _r(ytd / mese * 12) if mese else 0.0, "fissi_ripartiti": len(c["store_ids"]) > 1}
            negozi.append(row)
            tot["ricavi_lordi"] = _r(tot["ricavi_lordi"] + ricavi_lordi); tot["costi_fissi"] = _r(tot["costi_fissi"] + fissi); tot["costi_variabili"] = _r(tot["costi_variabili"] + var)
            tot["risultato"] = _r(tot["risultato"] + row["risultato"]); tot["obiettivo"] = _r(tot["obiettivo"] + row["obiettivo_mese"]); tot["ytd"] = _r(tot["ytd"] + ytd)
            if ricavi_netti is None:
                tot["netti_determinabili"] = False
            else:
                tot["ricavi_netti"] = _r(tot["ricavi_netti"] + ricavi_netti)
    base = tot["ricavi_netti"] if tot["netti_determinabili"] else tot["ricavi_lordi"]
    mdc = _r(base - tot["costi_variabili"])
    tot.update({"mdc": mdc, "mdc_pct": round(mdc / base * 100, 1) if base else None, "bep": _r(tot["costi_fissi"] / (mdc / base)) if base and mdc > 0 else None,
                "previsione_anno": _r(tot["ytd"] / mese * 12) if mese else 0.0, "ricavi_netti": tot["ricavi_netti"] if tot["netti_determinabili"] else None})
    return {"anno": anno, "mese": mese, "negozi": negozi, "azienda": tot}


class ObiettivoInput(BaseModel):
    store_id: str
    obiettivo_mese: float = 0.0
    obiettivo_anno: float = 0.0


@router.put("/obiettivi")
async def set_obiettivo(anno: int, body: ObiettivoInput, request: Request):
    user = await _d["user"](request)
    await _d["db"].pdp_obiettivi.update_one({"store_id": body.store_id, "anno": anno}, {"$set": {"store_id": body.store_id, "anno": anno, "obiettivo_mese": body.obiettivo_mese, "obiettivo_anno": body.obiettivo_anno, "updated_by": user.get("name", "")},
                                                                                         "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return {"ok": True}
