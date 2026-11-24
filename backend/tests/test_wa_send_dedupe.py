import asyncio, os, sys, uuid
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import server
from fastapi import HTTPException

TAG = "TESTDEDUP-" + uuid.uuid4().hex[:6]
INVIATI = []


async def finto_post(self, url, json=None, headers=None):
    INVIATI.append((json["phone"], json["session"]))
    class R:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self): return {"success": True, "session": json["session"]}
    return R()


async def main():
    db = server.db
    import httpx
    httpx.AsyncClient.post = finto_post
    server._WA_STATUS_CACHE.update({"at": 9e12, "sessions": [{"session": "negozioA", "user": {"name": "A"}}]})
    server.WA_ORARIO_AUTOMATICI = (0, 24)
    server.WA_PAUSA_AUTOMATICI_SEC = (0, 0)
    async def no_dry(): return False
    server.wa_dry_run_attivo = no_dry
    tel = "3330009999"
    msg = f"{TAG} ciao"
    # 1) primo invio automatico passa (sessione negozioA)
    r1 = await server.wa_send(tel, msg, session="negozioA", tipo="compleanno")
    assert r1.get("success"), r1
    # 2) stesso tipo stesso numero → saltato
    r2 = await server.wa_send("+39 333 000 9999", f"{TAG} auguri di nuovo", session="negozioA", tipo="compleanno")
    assert r2.get("saltato"), r2
    # 3) stesso testo entro 6h, tipo diverso → saltato
    r3 = await server.wa_send(tel, msg, session="negozioA", tipo="custom")
    assert r3.get("saltato"), r3
    # 4) sessione non connessa e non default → in attesa di riaggancio (fallito, recuperabile)
    try:
        await server.wa_send(tel, f"{TAG} rinnovo", session="negozioB", tipo="rinnovo_energia")
        raise AssertionError("doveva fallire")
    except HTTPException as e:
        assert "riaggancio" in e.detail, e.detail
    # 5) messaggio interno all'amministrazione con default giù → parte da negozioA
    r5 = await server.wa_send(server.contabilita_module.NUMERO_AMMINISTRAZIONE, f"{TAG} riepilogo", session="default", tipo="riepilogo_lavorazioni")
    assert r5.get("session") == "negozioA", r5
    # 6) riaggancio negozioB → reinvio automatico recupera il rinnovo una sola volta
    server._WA_STATUS_CACHE.update({"at": 9e12, "sessions": [{"session": "negozioA"}, {"session": "negozioB"}]})
    orig = server.wa_sessioni_connesse
    async def conn(max_age=20.0): return server._WA_STATUS_CACHE["sessions"]
    server.wa_sessioni_connesse = conn
    prima = len(INVIATI)
    res = await server.reinvio_automatico_falliti()
    res2 = await server.reinvio_automatico_falliti()
    server.wa_sessioni_connesse = orig
    rinnovi = [i for i in INVIATI[prima:] if i[1] == "negozioB"]
    assert len(rinnovi) == 1, (res, res2, INVIATI)
    # 7) fuori orario → 429 e niente invio
    server.WA_ORARIO_AUTOMATICI = (25, 26)
    try:
        await server.wa_send("3330001111", f"{TAG} notte", session="negozioA", tipo="bollette")
        raise AssertionError("doveva fermarsi")
    except HTTPException as e:
        assert e.status_code == 429 and "fuori orario" in e.detail
    n_corso = await db.wa_log.count_documents({"message": {"$regex": TAG}, "in_corso": True})
    assert n_corso == 0
    print("OK", {"inviati": INVIATI, "reinvio": res, "reinvio2": res2})
    await db.wa_log.delete_many({"message": {"$regex": TAG}})

asyncio.run(main())
