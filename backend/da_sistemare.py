"""Riquadro "Cose da sistemare": i problemi del mese per un negozio, in italiano semplice, in ordine di urgenza.
Solo lettura: non modifica nulla. Usato dalla Contabilità e dall'avviso WhatsApp dopo l'import AdE."""
import logging
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Request

logger = logging.getLogger("da_sistemare")
router = APIRouter(prefix="/contabilita", tags=["contabilita"])
_d: dict = {}
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def setup(**deps):
    _d.update(deps)


def _dmy(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def _eur(v: float) -> str:
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def problemi_negozio(store: dict, anno: int, mese: int, is_admin: bool) -> list:
    db = _d["db"]
    nome = store["nome"]
    dati = await _d["mese_dati"](store["id"], anno, mese)
    oggi = date.today()
    ultimo = monthrange(anno, mese)[1]
    fine = min(ultimo, oggi.day - 1) if (anno, mese) == (oggi.year, oggi.month) else ultimo
    if (anno, mese) > (oggi.year, oggi.month):
        fine = 0
    out = []
    ade = dati.get("confronto_ade") or {}
    ade_giorni = {g["data"]: g for g in ade.get("giorni_diff") or []}

    # 1. giorni senza chiusura (non domenica, già passati)
    mancanti = [r["data"] for r in dati["righe"] if r.get("vuoto") and int(r["data"][8:]) <= fine and date.fromisoformat(r["data"]).weekday() != 6]
    for d in mancanti:
        a = ade_giorni.get(d) or {}
        if a.get("ade") is not None:
            out.append({"livello": "alto", "testo": f"Manca il corrispettivo del {_dmy(d)} per {nome}, ma l'Agenzia delle Entrate ha registrato {_eur(a['ade'])}: inserisci la chiusura di quel giorno.", "tab": "cassa", "data": d, "tipo": "corrispettivo_mancante"})
        else:
            out.append({"livello": "medio", "testo": f"Manca il corrispettivo del {_dmy(d)} per {nome}: inserisci la chiusura o segna il giorno come chiuso.", "tab": "cassa", "data": d, "tipo": "corrispettivo_mancante"})

    # 2. differenze con l'AdE
    for g in ade.get("giorni_diff") or []:
        if g["data"] in mancanti:
            continue
        if g.get("ade") is None:
            if int(g["data"][8:]) <= fine and g.get("scontrini"):
                out.append({"livello": "medio", "testo": f"Il {_dmy(g['data'])} {nome} ha inserito {_eur(g['scontrini'])} di scontrini ma dall'Agenzia delle Entrate non risulta nessuna chiusura di cassa: controlla che il registratore abbia trasmesso.", "tab": "cassa", "data": g["data"], "tipo": "ade_assente"})
        elif g.get("diff") is not None and abs(g["diff"]) >= 0.01:
            segno = "in più" if g["diff"] > 0 else "in meno"
            out.append({"livello": "alto", "testo": f"Il {_dmy(g['data'])} {nome} ha {_eur(abs(g['diff']))} {segno} rispetto all'Agenzia delle Entrate (inserito {_eur(g['scontrini'])}, AdE {_eur(g['ade'])}): correggi la chiusura del giorno.", "tab": "cassa", "data": g["data"], "tipo": "ade_differenza"})
    if not ade.get("presente") and fine >= 7:
        out.append({"livello": "basso", "testo": f"Per {MESI[mese]} non è ancora stato caricato il file dei corrispettivi dall'Agenzia delle Entrate per {nome}: scaricalo dal portale Fatture e Corrispettivi e caricalo nel riquadro Confronto AdE.", "tab": "cassa", "tipo": "ade_file_mancante"})

    # 3. cassa
    t = dati["totali"]
    if t["da_versare"] < -0.01:
        out.append({"livello": "alto", "testo": f"A {nome} risulta un ammanco di cassa di {_eur(abs(t['da_versare']))}: sono stati versati più contanti di quelli incassati. Controlla versamenti, spese e riporto.", "tab": "cassa", "tipo": "ammanco"})
    elif (anno, mese) < (oggi.year, oggi.month) and t["da_versare"] > 0.01:
        out.append({"livello": "medio", "testo": f"A {nome} restano {_eur(t['da_versare'])} in contanti di {MESI[mese]} non ancora versati in banca: registra il versamento in 'Versamenti dopo fine mese' quando lo fai.", "tab": "cassa", "tipo": "da_versare"})

    if not is_admin:
        return out
    # 4. scadenze scadute non pagate (entità del negozio)
    pref = f"{anno:04d}-{mese:02d}"
    try:
        centri = [c for c in await _d["centri_tutti"]() if store["id"] in (c.get("store_ids") or [])]
        for c in centri:
            for s in await _d["scadenze"](c["id"], anno, mese):
                if not s.get("pagata_at") and s["data"] < oggi.isoformat():
                    out.append({"livello": "alto", "testo": f"Scadenza '{s['voce']}' di {_eur(s['importo'])} del {_dmy(s['data'])} non risulta pagata: se l'hai pagata segnala come pagata, altrimenti provvedi.", "tab": "scadenze", "tipo": "scadenza"})
            n_est = await db.fatture_estere.count_documents({"centro_id": c["id"], "anno": anno, "mese": mese, "inviata_at": None})
            if n_est and (anno, mese) < (oggi.year, oggi.month):
                out.append({"livello": "medio", "testo": f"{n_est} fattur{'a' if n_est == 1 else 'e'} ester{'a' if n_est == 1 else 'e'} di {MESI[mese]} non ancora trasmess{'a' if n_est == 1 else 'e'} allo SdI (scadenza il 15 del mese dopo).", "tab": "banche", "tipo": "estere"})
            ent = next((e for e, cid in (_d.get("entita_centro") or {}).items() if cid == c["id"]), None)
            conti_ids = [x["id"] for x in (_d.get("conti") or []) if x["entita"] == ent and x["tipo"] == "banca"] if ent else []
            if conti_ids and not await db.estratti_caricati.find_one({"conto_id": {"$in": conti_ids}, "dal": {"$regex": f"^{pref}"}}) and (anno, mese) < (oggi.year, oggi.month):
                out.append({"livello": "basso", "testo": f"Nessun estratto conto di {MESI[mese]} caricato per {c['nome']}: scarica i movimenti da Intesa/Nexi/myPOS e caricali in Banche & Fatture.", "tab": "banche", "tipo": "estratti"})
    except Exception as e:
        logger.warning(f"da_sistemare admin {store['id']}: {e}")
    return out


ORD = {"alto": 0, "medio": 1, "basso": 2}


@router.get("/da-sistemare")
async def da_sistemare(store_id: str, anno: int, mese: int, request: Request):
    user = await _d["user"](request)
    store, _ = await _d["store_completo"](user, store_id)
    is_admin = user["role"] == "admin" or user.get("can_view_all")
    items = await problemi_negozio(store, anno, mese, is_admin)
    items.sort(key=lambda x: (ORD[x["livello"]], x.get("data") or ""))
    return {"items": items, "alto": sum(1 for i in items if i["livello"] == "alto"), "totale": len(items)}
