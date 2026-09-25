import asyncio, os
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


async def m():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    print("USERS:", [(u['name'], u['role'], u.get('store_ids')) async for u in db.users.find({}, {'_id': 0, 'name': 1, 'role': 1, 'store_ids': 1})])
    print("\nSERVIZI tipo:", await db.servizi.distinct('tipo'))
    for t in await db.servizi.distinct('tipo'):
        s = await db.servizi.find_one({'tipo': t}, {'_id': 0})
        print(f"\n[{t}] n={await db.servizi.count_documents({'tipo': t})} keys:", sorted(s.keys()))
        for f in ('sottotipo', 'operatore', 'tipo_operazione', 'stato', 'operazione', 'categoria', 'tipo_linea', 'portabilita', 'fornitore', 'tipo_sim', 'created_by', 'inserito_da', 'operatore_id'):
            if f in s:
                print('  ', f, '->', (await db.servizi.distinct(f, {'tipo': t}))[:20])
    c = await db.clients.find_one({}, {'_id': 0})
    print("\nCLIENTS keys:", sorted(c.keys()))
    for f in ('gestione', 'tipo_operazione', 'operazione', 'stato', 'fornitore_nuovo', 'nuovo_fornitore', 'tipo_contratto', 'created_by', 'operatore_id', 'venditore_id', 'store_id', 'stato_pratica', 'esito'):
        if f in c:
            print('  ', f, '->', (await db.clients.distinct(f))[:15])
    cols = sorted(await db.list_collection_names())
    print("\nCOLLECTIONS:", cols)
    for col in ('vendite', 'chiamate', 'contatti', 'richiami', 'wa_log', 'audit_log', 'interazioni', 'proposte', 'ritiri', 'timeline', 'eventi', 'note'):
        if col in cols:
            d = await db[col].find_one({}, {'_id': 0})
            print(f"\n{col} n={await db[col].count_documents({})} keys:", sorted(d.keys()) if d else None)

asyncio.run(m())
