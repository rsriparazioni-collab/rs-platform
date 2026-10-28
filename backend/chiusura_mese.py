import logging
import uuid
from datetime import datetime, timezone


"""Checklist di chiusura mese per entità (ditta/srls): corrispettivi, fatture AdE, estratti conto, fatture estere, scadenze F24.
Solo lettura/controllo: stato verde quando tutto è completo."""
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from banche import CONTI_DEFAULT, ENTITA_CENTRO, require_admin

router = APIRouter(prefix="/chiusura-mese", tags=["chiusura"])
_d: dict = {}


def setup(**deps):
    _d.update(deps)


@router.get("")
async def checklist(entita: str, anno: int, mese: int, user: dict = Depends(require_admin)):
    return await calcola(entita, anno, mese)


async def calcola(entita: str, anno: int, mese: int) -> dict:
    db = _d["db"]
    conti_map = ENTITA_CENTRO
    if entita not in conti_map:
        raise HTTPException(status_code=400, detail="Entità non valida (ditta|srls)")
    centro = next(c for c in await _d["centri_tutti"]() if c["id"] == conti_map[entita])
    pref = f"{anno:04d}-{mese:02d}"
    oggi = date.today()
    ultimo = monthrange(anno, mese)[1]
    fine = min(ultimo, oggi.day) if (anno, mese) == (oggi.year, oggi.month) else ultimo
    voci = []

    # 1. Corrispettivi: ogni giorno non domenica ≤ oggi per ogni negozio del centro
    stores = {s["id"]: s["nome"] async for s in db.stores.find({"id": {"$in": centro["store_ids"]}}, {"_id": 0, "id": 1, "nome": 1})}
    presenti = set()
    async for c in db.corrispettivi.find({"store_id": {"$in": centro["store_ids"]}, "data": {"$regex": f"^{pref}"}}, {"_id": 0, "data": 1, "store_id": 1}):
        presenti.add((c["store_id"], c["data"]))
    mancanti = []
    for sid, nome in stores.items():
        for g in range(1, fine + 1):
            d = date(anno, mese, g)
            if d.weekday() == 6:
                continue
            if (sid, d.isoformat()) not in presenti:
                mancanti.append(f"{nome} {g:02d}")
    chiuso = (anno, mese) < (oggi.year, oggi.month)
    voci.append({"id": "corrispettivi", "titolo": "Corrispettivi giornalieri", "ok": not mancanti, "dettaglio": f"{len(presenti)} chiusure registrate" + (f" · mancano: {', '.join(mancanti[:8])}{'…' if len(mancanti) > 8 else ''}" if mancanti else " · tutti i giorni presenti"), "link": "corrispettivi"})

    # 2. Fatture AdE caricate (emesse e ricevute)
    n_ric = await db.fatture_ade.count_documents({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "ricevute"})
    n_em = await db.fatture_ade.count_documents({"centro_id": centro["id"], "anno": anno, "mese": mese, "direzione": "emesse"})
    voci.append({"id": "fatture", "titolo": "Fatture AdE (emesse e ricevute)", "ok": n_ric > 0, "dettaglio": f"{n_ric} ricevute · {n_em} emesse" + ("" if n_ric else " · importa il CSV dal portale Fatture e Corrispettivi"), "link": "pdp"})

    # 3. Estratti conto per ogni conto dell'entità
    conti = [c for c in CONTI_DEFAULT if c["entita"] == entita]
    senza = []
    for c in conti:
        cop = await db.estratti_caricati.find_one({"conto_id": c["id"], "$or": [{"dal": {"$regex": f"^{pref}"}}, {"dal": {"$lte": f"{pref}-01"}, "al": {"$gte": f"{pref}-28"}}]}, {"_id": 0, "id": 1})
        if not cop:
            senza.append(c["nome"])
    voci.append({"id": "estratti", "titolo": "Estratti conto banca e POS", "ok": not senza, "dettaglio": f"{len(conti) - len(senza)}/{len(conti)} conti caricati" + (f" · mancano: {', '.join(senza)}" if senza else ""), "link": "banche"})

    # 4. Riconciliazione POS: giorni con differenza
    ric = await _d["riconciliazione"](entita, anno, mese)
    ko = [g["data"][8:] for g in ric["giorni"] if g["ok"] is False]
    voci.append({"id": "pos", "titolo": "Riconciliazione POS (chiusure vs transazioni)", "ok": not ko and not senza, "dettaglio": (f"{len(ko)} giorni con differenza: {', '.join(ko[:10])}" if ko else "nessuna differenza") if not senza else "in attesa degli estratti", "link": "banche"})

    # 5. Fatture estere inviate al commercialista
    n_est = await db.fatture_estere.count_documents({"centro_id": centro["id"], "anno": anno, "mese": mese})
    n_est_da = await db.fatture_estere.count_documents({"centro_id": centro["id"], "anno": anno, "mese": mese, "inviata_at": None})
    voci.append({"id": "estere", "titolo": "Fatture estere trasmesse", "ok": n_est_da == 0, "dettaglio": f"{n_est} registrate · {n_est_da} da inviare" if n_est else "nessuna fattura estera nel mese", "link": "estere"})

    # 6. Scadenze F24 / affitti pagate
    sc = await _d["scadenze"](centro["id"], anno, mese)
    non_pagate = [s for s in sc if not s.get("pagata_at")]
    voci.append({"id": "scadenze", "titolo": "Scadenze F24 / affitti pagate", "ok": not non_pagate, "dettaglio": f"{len(sc) - len(non_pagate)}/{len(sc)} pagate" + (f" · aperte: {', '.join(s['voce'] for s in non_pagate[:5])}" if non_pagate else "") if sc else "nessuna scadenza inserita", "link": "scadenzario"})

    # 7. Report al commercialista inviato (solo mesi chiusi)
    inviato = await db.contabilita_invii.find_one({"tipo": "report_commercialista", "centro_id": centro["id"], "anno": anno, "mese": mese}, {"_id": 0, "at": 1}, sort=[("at", -1)])
    voci.append({"id": "report", "titolo": "Report inviato al commercialista", "ok": bool(inviato), "dettaglio": f"inviato il {inviato['at'][:10]}" if inviato else ("da inviare dopo la chiusura del mese" if not chiuso else "non ancora inviato"), "link": "banche", "opzionale": not chiuso})

    completo = all(v["ok"] for v in voci if not v.get("opzionale"))
    return {"entita": entita, "centro": centro["nome"], "anno": anno, "mese": mese, "mese_chiuso": chiuso, "voci": voci, "completo": completo, "completate": sum(1 for v in voci if v["ok"]), "totale": len(voci)}


logger = logging.getLogger("chiusura")


async def promemoria_mese_precedente() -> dict:
    """Cron del 2 del mese: WhatsApp all'amministrazione con le voci ancora rosse della chiusura del mese precedente (ditta + SRLS)."""
    oggi = date.today()
    anno, mese = (oggi.year, oggi.month - 1) if oggi.month > 1 else (oggi.year - 1, 12)
    key = f"chiusura-promemoria-{anno}-{mese:02d}"
    db = _d["db"]
    if await db.scadenze_alert_log.find_one({"key": key}):
        return {"inviati": 0, "motivo": "già inviato"}
    blocchi = []
    for ent in ENTITA_CENTRO:
        try:
            r = await calcola(ent, anno, mese)
        except Exception as e:
            logger.warning(f"chiusura {ent}: {e}")
            continue
        rosse = [v for v in r["voci"] if not v["ok"]]
        if rosse:
            blocchi.append(f"*{r['centro']}* — {r['completate']}/{r['totale']} ok\n" + "\n".join(f"  ✗ {v['titolo']}: {v['dettaglio'][:90]}" for v in rosse))
        else:
            blocchi.append(f"*{r['centro']}* — ✅ tutto verde")
    mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    testo = f"🧾 *Chiusura {mesi[mese]} {anno}* — cosa manca\n" + "\n\n".join(blocchi) + "\n\nContabilità → Chiusura mese."
    try:
        await _d["wa_send"](_d["numero_amministrazione"], testo, session=await _d["store_id_by_name"]("Sondrio") or "default", tipo="chiusura_mese")
    except HTTPException as e:
        return {"inviati": 0, "errore": e.detail}
    await db.scadenze_alert_log.insert_one({"id": str(uuid.uuid4()), "key": key, "sent_at": datetime.now(timezone.utc).isoformat()})
    return {"inviati": 1}
