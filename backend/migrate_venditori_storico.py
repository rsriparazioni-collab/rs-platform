"""Migrazione una tantum: assegna operatore_id (venditore) ai clienti storici
leggendo la colonna 'venditore' dai tab del foglio energia Google.
Match per nome+cognome normalizzato dentro il negozio del tab.
Uso: cd /app/backend && python3 migrate_venditori_storico.py
"""
import asyncio
import re

import httpx

from server import db, _parse_any_csv, _venditori_name_map

SHEET_ID = "19pEn41GLbJi6iI6BQ7v83idmro4GUoazUwdLGBUuksY"
ADMIN = {"id": "migration", "name": "migration"}


def _key(nome: str, cognome: str) -> str:
    return re.sub(r"\s+", " ", f"{nome} {cognome}".strip().lower())


async def main():
    vend_map = await _venditori_name_map()
    vend_fallback = vend_map.get("enrico", "")
    print("Mappa venditori:", vend_map, "| fallback (diretto):", vend_fallback)

    stores = {s["nome"]: s["id"] for s in await db.stores.find({}, {"_id": 0}).to_list(100)}
    tot_updated, tot_pagati = 0, 0

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
        fb = await http.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=__non_esiste__")
        import hashlib
        fb_hash = hashlib.sha256(fb.text.encode()).hexdigest()

        for store_name, store_id in stores.items():
            r = await http.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={store_name}")
            if r.status_code != 200:
                continue
            if hashlib.sha256(r.text.encode()).hexdigest() == fb_hash:
                # Il fallback di Google per tab inesistenti restituisce il PRIMO foglio.
                # Lo processiamo solo per il negozio del primo foglio (Sondrio), evitando duplicati.
                if store_name != "Sondrio":
                    continue
                print(f"[{store_name}] tab non trovato con questo nome: uso il primo foglio del documento")
            if "venditore" not in r.text[:3000].lower():
                print(f"[{store_name}] nessuna colonna venditore, skip")
                continue
            parsed, err = _parse_any_csv(r.text, store_id, ADMIN, vend_map, vend_fallback)
            if err:
                print(f"[{store_name}] errore parse: {err}")
                continue
            docs, _ = parsed

            sheet_map = {}
            conflicts = 0
            for d in docs:
                if not d.get("operatore_id"):
                    continue
                k = _key(d["nome"], d["cognome"])
                if k in sheet_map and sheet_map[k][0] != d["operatore_id"]:
                    conflicts += 1
                sheet_map[k] = (d["operatore_id"], d.get("venditore_pagato", False))

            updated, pagati = 0, 0
            async for c in db.clients.find({"venditore_id": store_id},
                                           {"_id": 0, "id": 1, "nome": 1, "cognome": 1}):
                k = _key(c.get("nome", ""), c.get("cognome", ""))
                if k not in sheet_map:
                    continue
                op_id, vpag = sheet_map[k]
                upd = {"operatore_id": op_id}
                if vpag:
                    upd["venditore_pagato"] = True
                    pagati += 1
                await db.clients.update_one({"id": c["id"]}, {"$set": upd})
                updated += 1
            tot_updated += updated
            tot_pagati += pagati
            print(f"[{store_name}] righe foglio con venditore: {len(sheet_map)} | clienti aggiornati: {updated} "
                  f"(di cui pagati: {pagati}) | conflitti nome: {conflicts}")

    print(f"\nTOTALE: {tot_updated} clienti aggiornati, {tot_pagati} con compenso già pagato")
    print("\nConteggi finali per venditore (clienti assegnati / da_pagare):")
    async for v in db.venditori.find({}, {"_id": 0}).sort("nome", 1):
        n = await db.clients.count_documents({"operatore_id": v["id"]})
        dp = await db.clients.count_documents({"operatore_id": v["id"], "venditore_pagato": {"$ne": True}})
        print(f"  {v['nome']}: {n} vendite, {dp} da pagare")


if __name__ == "__main__":
    asyncio.run(main())
