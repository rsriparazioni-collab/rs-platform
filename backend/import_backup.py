"""Ripristina un backup ZIP (esportato dal gestionale) nel database MongoDB indicato da MONGO_URL/DB_NAME.
Uso: python import_backup.py backup_YYYYMMDD_HHMMSS.zip [--conferma]
"""
import asyncio
import json
import os
import sys
import zipfile

from bson import json_util
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def main(path: str, conferma: bool) -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        print(f"Backup del {manifest['creato_il']} - {sum(manifest['collezioni'].values())} documenti in {len(manifest['collezioni'])} collezioni")
        if not conferma:
            print("ATTENZIONE: le collezioni presenti nel database verranno SOSTITUITE. Rilancia con --conferma per procedere.")
            return
        for nome, n in manifest["collezioni"].items():
            docs = json_util.loads(zf.read(f"collections/{nome}.json").decode("utf-8"))
            await db[nome].drop()
            if docs:
                await db[nome].insert_many(docs, ordered=False)
            print(f"  {nome}: {len(docs)} documenti ripristinati")
    print("Ripristino completato.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], "--conferma" in sys.argv))
