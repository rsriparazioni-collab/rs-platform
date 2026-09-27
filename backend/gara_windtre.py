import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
_d: dict = {}

WT_OPS = {"windtre", "wind tre", "wind3", "w3"}
VERY_OPS = {"very", "very mobile"}
CATEGORIE_FISSO = ["FWA Outdoor", "FTTH", "FWA Indoor 2P", "Voce Casa", "FTTC", "Seconda Linea P.IVA"]
ESITI = ["riconosciuta", "in_attesa", "annullata", "respinta", "non_riconosciuta", "stornata"]

TARIFFE_DEFAULT = {
    "fisso_soglie": [1, 3, 8, 17],
    "fisso_consumer": {"FWA Outdoor": [136, 147, 169, 191], "FTTH": [115, 126, 148, 170], "FWA Indoor 2P": [136, 147, 169, 191], "Voce Casa": [72, 77, 85, 98]},
    "fisso_consumer_fttc_meno": 22,
    "fisso_piva": {"FWA Outdoor": [170, 181, 203, 225], "FTTH": [159, 170, 192, 214], "FTTC": [137, 148, 170, 192], "Seconda Linea P.IVA": [92, 97, 107, 117]},
    "convergente_extra": 30,
    "wt_soglie": [5, 18, 38],
    "wt_canone_basso": [24, 30, 36],
    "wt_canone_alto": [26, 34, 42],
    "wt_canone_limite": 9.99,
    "wt_tied": [12, 14, 19],
    "wt_piva_extra": 15,
    "very_soglie": [5, 10, 15, 35],
    "very_offerta_bassa": [8, 17, 20, 23],
    "very_offerta_alta": [12, 27, 31, 38],
    "very_offerta_limite": 6.99,
    "extra_mnp_soglia_rete": 15,
    "extra_mnp_provenienze_top": ["Iliad", "CoopVoce", "Poste", "Tiscali"],
    "extra_mnp_top": 35,
    "extra_mnp_altri": 20,
    "no_mnp_conta_soglia": False,
}


def setup(**deps):
    _d.update(deps)


async def _admin(request: Request):
    from fastapi.security import HTTPAuthorizationCredentials
    auth = request.headers.get("authorization", "")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:]) if auth.lower().startswith("bearer ") else None
    user = await _d["get_current_user"](request, creds)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo amministratore")
    return user


class PremioInput(BaseModel):
    mese: str
    premio_totale: float


class TariffeInput(BaseModel):
    tariffe: dict


async def tariffe() -> dict:
    doc = await _d["db"].settings.find_one({"_id": "gara_windtre_tariffe"}, {"_id": 0})
    return {**TARIFFE_DEFAULT, **(doc or {})}


@router.get("/gara-windtre/tariffe")
async def get_tariffe(admin: dict = Depends(_admin)):
    return await tariffe()


@router.put("/gara-windtre/tariffe")
async def put_tariffe(input: TariffeInput, admin: dict = Depends(_admin)):
    dati = {k: v for k, v in input.tariffe.items() if k in TARIFFE_DEFAULT}
    await _d["db"].settings.update_one({"_id": "gara_windtre_tariffe"}, {"$set": dati}, upsert=True)
    return await tariffe()


@router.post("/gara-windtre/premio")
async def set_premio(input: PremioInput, admin: dict = Depends(_admin)):
    await _d["db"].gara_windtre_premi.update_one({"mese": input.mese}, {"$set": {"premio_totale": input.premio_totale, "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True}


def _soglia_idx(n: int, soglie: list) -> int:
    idx = -1
    for i, s in enumerate(soglie):
        if n >= s:
            idx = i
    return idx


def _op(s: dict) -> str:
    o = (s.get("operatore_tel") or "").strip().lower()
    if o in WT_OPS:
        return "windtre"
    if o in VERY_OPS:
        return "very"
    return ""


async def calcola(mese: str) -> dict:
    db = _d["db"]
    t = await tariffe()
    servizi = [s for s in await db.servizi.find({"tipo": {"$in": ["sim", "internet", "fisso"]}}, {"_id": 0}).to_list(50000)
               if ((s.get("data_attivazione") or s.get("created_at") or "")[:7]) == mese and _op(s)]
    clienti = {c["id"]: c async for c in db.clients.find({"id": {"$in": list({s["client_id"] for s in servizi})}}, {"_id": 0, "id": 1, "nome": 1, "cognome": 1, "tipo_cliente": 1})}
    stores = {s["id"]: s["nome"] async for s in db.stores.find({}, {"_id": 0, "id": 1, "nome": 1})}
    users = {u["id"]: u["name"] async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1})}
    premio_doc = await db.gara_windtre_premi.find_one({"mese": mese}, {"_id": 0})
    premio_totale = float(premio_doc["premio_totale"]) if premio_doc else 0.0

    righe = []
    for s in servizi:
        cli = clienti.get(s["client_id"], {})
        esito = s.get("esito_attivazione") or "riconosciuta"
        op = _op(s)
        mobile = s["tipo"] == "sim"
        mnp = s.get("tipo_attivazione") == "mnp"
        piva = bool(cli.get("tipo_cliente")) and cli["tipo_cliente"] != "privato"
        cat = s.get("categoria_prodotto") or ("FTTH" if not mobile else "")
        if mobile:
            categoria = "Mobile WindTre" if op == "windtre" else "Mobile Very"
        else:
            categoria = cat
        righe.append({"id": s["id"], "cliente": f"{cli.get('cognome', '')} {cli.get('nome', '')}".strip(), "store_id": s.get("venditore_id", ""), "negozio": stores.get(s.get("venditore_id", ""), "-"),
                      "inseritore_id": s.get("operatore_id") or s.get("created_by") or "", "inseritore": users.get(s.get("operatore_id") or s.get("created_by") or "", "-"),
                      "data": (s.get("data_attivazione") or s.get("created_at") or "")[:10], "prodotto": s.get("operatore_tel", ""), "tipo": s["tipo"], "op": op, "mobile": mobile,
                      "categoria": categoria, "piva": piva, "mnp": mnp, "tipo_attivazione": s.get("tipo_attivazione", ""), "provenienza": s.get("provenienza_operatore") or "",
                      "canone": float(s.get("importo") or 0), "convergente": bool(s.get("convergente")), "tied": bool(s.get("tied")), "esito": esito,
                      "riconosciuta": esito in ("riconosciuta", "in_attesa"), "compenso_base": 0.0, "extra": [], "compenso_finale": 0.0, "conta_soglia": False})

    # conteggi di rete per soglia
    conteggi = defaultdict(int)
    mnp_rete = 0
    for r in righe:
        if not r["riconosciuta"]:
            continue
        if r["mobile"]:
            if r["mnp"]:
                mnp_rete += 1
            if r["mnp"] or t["no_mnp_conta_soglia"]:
                conteggi[r["categoria"]] += 1
                r["conta_soglia"] = True
        else:
            conteggi[r["categoria"]] += 1
            r["conta_soglia"] = True
    extra_attivo = mnp_rete >= int(t["extra_mnp_soglia_rete"])
    top = [p.lower() for p in t["extra_mnp_provenienze_top"]]

    for r in righe:
        if not r["riconosciuta"]:
            r["nota"] = "Esclusa: " + r["esito"]
            continue
        n = conteggi[r["categoria"]]
        if r["mobile"]:
            if not r["mnp"]:
                r["nota"] = "NO MNP: compenso 0 €"
                continue
            if r["op"] == "windtre":
                idx = _soglia_idx(n, t["wt_soglie"])
                if idx < 0:
                    r["nota"] = f"Soglia non raggiunta ({n}/{t['wt_soglie'][0]})"
                    continue
                r["soglia"] = t["wt_soglie"][idx]
                r["compenso_base"] = float((t["wt_canone_alto"] if r["canone"] > t["wt_canone_limite"] else t["wt_canone_basso"])[idx])
                if r["tied"]:
                    r["extra"].append({"nome": "Tied", "importo": float(t["wt_tied"][idx])})
                if r["piva"]:
                    r["extra"].append({"nome": "Partita IVA", "importo": float(t["wt_piva_extra"])})
            else:
                idx = _soglia_idx(n, t["very_soglie"])
                if idx < 0:
                    r["nota"] = f"Soglia non raggiunta ({n}/{t['very_soglie'][0]})"
                    continue
                r["soglia"] = t["very_soglie"][idx]
                r["compenso_base"] = float((t["very_offerta_alta"] if r["canone"] > t["very_offerta_limite"] else t["very_offerta_bassa"])[idx])
            if extra_attivo:
                imp = t["extra_mnp_top"] if r["provenienza"].lower() in top else t["extra_mnp_altri"]
                r["extra"].append({"nome": f"Extra MNP da {r['provenienza'] or 'altro'}", "importo": float(imp)})
        else:
            idx = _soglia_idx(n, t["fisso_soglie"])
            if idx < 0:
                r["nota"] = "Soglia non raggiunta"
                continue
            r["soglia"] = t["fisso_soglie"][idx]
            if r["piva"]:
                tab = t["fisso_piva"].get(r["categoria"])
                if not tab:
                    r["nota"] = f"Categoria {r['categoria']} non prevista per P.IVA"
                    continue
                r["compenso_base"] = float(tab[idx])
            else:
                if r["categoria"] == "FTTC":
                    r["compenso_base"] = float(t["fisso_consumer"]["FTTH"][idx]) - float(t["fisso_consumer_fttc_meno"])
                else:
                    tab = t["fisso_consumer"].get(r["categoria"])
                    if not tab:
                        r["nota"] = f"Categoria {r['categoria']} non prevista per Consumer"
                        continue
                    r["compenso_base"] = float(tab[idx])
            if r["convergente"]:
                r["extra"].append({"nome": "Convergente", "importo": float(t["convergente_extra"])})
        r["compenso_finale"] = round(r["compenso_base"] + sum(e["importo"] for e in r["extra"]), 2)

    totale_rete = round(sum(r["compenso_finale"] for r in righe), 2)
    negozi = defaultdict(lambda: {"generato": 0.0, "attivazioni": 0, "inseritori": defaultdict(lambda: {"generato": 0.0, "attivazioni": 0})})
    for r in righe:
        if not r["riconosciuta"]:
            continue
        ng = negozi[r["store_id"]]
        ng["nome"] = r["negozio"]
        ng["generato"] = round(ng["generato"] + r["compenso_finale"], 2)
        ng["attivazioni"] += 1
        ins = ng["inseritori"][r["inseritore_id"]]
        ins["nome"] = r["inseritore"]
        ins["generato"] = round(ins["generato"] + r["compenso_finale"], 2)
        ins["attivazioni"] += 1
    ripartizione = []
    for sid, ng in negozi.items():
        quota = round(premio_totale * ng["generato"] / totale_rete, 2) if totale_rete else 0.0
        inseritori = [{"id": uid, "nome": i["nome"], "generato": i["generato"], "attivazioni": i["attivazioni"],
                       "quota": round(quota * i["generato"] / ng["generato"], 2) if ng["generato"] else 0.0} for uid, i in ng["inseritori"].items()]
        ripartizione.append({"store_id": sid, "nome": ng["nome"], "generato": ng["generato"], "attivazioni": ng["attivazioni"], "quota": quota,
                             "inseritori": sorted(inseritori, key=lambda x: -x["generato"])})
    soglie = {c: {"conteggio": n} for c, n in conteggi.items()}
    return {"mese": mese, "premio_totale": premio_totale, "totale_rete": totale_rete, "mnp_rete": mnp_rete, "extra_mnp_attivo": extra_attivo,
            "extra_mnp_soglia": t["extra_mnp_soglia_rete"], "soglie": soglie, "attivazioni": sorted(righe, key=lambda x: x["data"], reverse=True),
            "ripartizione": sorted(ripartizione, key=lambda x: -x["generato"]), "categorie_fisso": CATEGORIE_FISSO, "esiti": ESITI}


@router.get("/gara-windtre/calcolo")
async def gara_calcolo(anno: int, mese: int, admin: dict = Depends(_admin)):
    return await calcola(f"{anno:04d}-{mese:02d}")


async def generato_per_destinatario(mese: str) -> dict:
    """{('store', id): €, ('user', id): €} compensi WindTre/Very finali del mese, per integrazione nei compensi."""
    res = await calcola(mese)
    out = defaultdict(float)
    for r in res["attivazioni"]:
        if r["compenso_finale"]:
            out[("store", r["store_id"])] += r["compenso_finale"]
            out[("user", r["inseritore_id"])] += r["compenso_finale"]
    return dict(out)
