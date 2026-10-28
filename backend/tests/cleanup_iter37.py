# Cleanup of Switcho test data (iteration 37)
import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import dotenv_values

BE = dotenv_values("/app/backend/.env")
db = MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
include_old = "--old" in sys.argv

q = [{"nome": "Testa", "cognome": "Bolletta"}, {"nome": "Testb", "cognome": "Link"}, {"nome": {"$regex": "^TEST"}}, {"cognome": {"$regex": "^TEST"}}]
if include_old:
    morb = "348642fd-364f-48ab-897b-83c6236b061f"
    today = datetime.now(timezone.utc).date().isoformat()
    for cg in ("Lino", "Lentini", "Melazzi", "Ciappa"):
        q.append({"cognome": cg, "venditore_id": morb, "created_at": {"$gte": today}})
ids = [c["id"] for c in db.clients.find({"$or": q}, {"id": 1, "cognome": 1, "nome": 1})]
print("clients:", list(db.clients.find({"id": {"$in": ids}}, {"_id": 0, "nome": 1, "cognome": 1, "created_at": 1})))
segq = {"$or": [{"client_id": {"$in": ids}}, {"testo": {"$regex": "Pinco Pallino|TESTUI"}}] + ([{"client_id": None}] if include_old else [])}
msg_ids = {s["messaggio_id"] for s in db.switcho_segnalazioni.find(segq, {"messaggio_id": 1})}
print("segs:", db.switcho_segnalazioni.delete_many(segq).deleted_count)
print("msgs:", db.switcho_messaggi.delete_many({"$or": [{"id": {"$in": list(msg_ids)}}, {"id": {"$regex": "^TEST_"}}]}).deleted_count)
print("wa_log:", db.wa_log.delete_many({"client_id": {"$in": ids}}).deleted_count)
print("lav_log:", db.lavorazioni_log.delete_many({"client_id": {"$in": ids}}).deleted_count)
print("attachments:", db.attachments.delete_many({"client_id": {"$in": ids}}).deleted_count)
print("clients deleted:", db.clients.delete_many({"id": {"$in": ids}}).deleted_count)
