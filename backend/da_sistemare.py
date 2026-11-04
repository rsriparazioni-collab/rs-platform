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
    nome = store["nome"]
    dati = await _d["mese_dati"](store["id"], anno, mese)
    oggi = date.today()
    ultimo = monthrange(anno, mese)[1]
    fine = min(ultimo, oggi.day - 1) if (anno, mese) == (oggi.year, oggi.month) else ultimo
    if (anno, mese) > (oggi.year, oggi.month):
        fine = 0
    out = []

    # 1. giorni senza chiusura (non domenica, già passati)
    mancanti = [r["data"] for r in dati["righe"] if r.get("vuoto") and not r.get("chiuso") and int(r["data"][8:]) <= fine and date.fromisoformat(r["data"]).weekday() != 6]
    for d in mancanti:
        out.append({"livello": "medio", "testo": f"Manca il corrispettivo del {_dmy(d)} per {nome}: inserisci la chiusura o segna il giorno come chiuso.", "tab": "cassa", "data": d, "tipo": "corrispettivo_mancante"})

    # 3. cassa
    t = dati["totali"]
    if t["da_versare"] < -0.01:
        out.append({"livello": "alto", "testo": f"A {nome} risulta un ammanco di cassa di {_eur(abs(t['da_versare']))}: sono stati versati più contanti di quelli incassati. Controlla versamenti, spese e riporto.", "tab": "cassa", "tipo": "ammanco"})
    elif (anno, mese) < (oggi.year, oggi.month) and t["da_versare"] > 0.01:
        out.append({"livello": "medio", "testo": f"A {nome} restano {_eur(t['da_versare'])} in contanti di {MESI[mese]} non ancora versati in banca: registra il versamento in 'Versamenti dopo fine mese' quando lo fai.", "tab": "cassa", "tipo": "da_versare"})

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
