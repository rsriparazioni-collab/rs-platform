import asyncio
import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from bson import json_util
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter()
_d: dict = {}
logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR") or (Path(__file__).parent / "backups"))
BACKUP_KEEP = 7
COLLEZIONI_ESCLUSE = {"oauth_states", "login_attempts", "password_reset_tokens"}


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


async def crea_zip() -> tuple[bytes, dict]:
    db = _d["db"]
    buf = io.BytesIO()
    manifest = {"creato_il": datetime.now(timezone.utc).isoformat(), "db_name": db.name, "collezioni": {}}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome in sorted(await db.list_collection_names()):
            if nome in COLLEZIONI_ESCLUSE:
                continue
            docs = await db[nome].find({}).to_list(None)
            manifest["collezioni"][nome] = len(docs)
            zf.writestr(f"collections/{nome}.json", json_util.dumps(docs, ensure_ascii=False))
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return buf.getvalue(), manifest


def _nome_file() -> str:
    return f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"


async def salva_backup_automatico() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    data, manifest = await crea_zip()
    path = BACKUP_DIR / _nome_file()
    path.write_bytes(data)
    vecchi = sorted(BACKUP_DIR.glob("backup_*.zip"))[:-BACKUP_KEEP]
    for v in vecchi:
        v.unlink(missing_ok=True)
    await _d["db"].cron_log.insert_one({"job": "backup-automatico", "at": manifest["creato_il"], "file": path.name,
                                        "documenti": sum(manifest["collezioni"].values())})
    logger.info(f"Backup automatico salvato: {path.name}")
    return {"file": path.name, "size": len(data), **manifest}


async def backup_loop() -> None:
    while True:
        try:
            ultimo = await _d["db"].cron_log.find_one({"job": "backup-automatico"}, {"_id": 0, "at": 1}, sort=[("at", -1)])
            if not ultimo or (datetime.now(timezone.utc) - datetime.fromisoformat(ultimo["at"])).total_seconds() >= 86400:
                await salva_backup_automatico()
        except Exception as e:
            logger.error(f"backup_loop errore: {e}")
        await asyncio.sleep(3600)


def _lista() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True):
        st = p.stat()
        out.append({"file": p.name, "size": st.st_size, "creato_il": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()})
    return out


@router.get("/admin/backup")
async def backup_info(admin: dict = Depends(_admin)):
    db = _d["db"]
    nomi = [n for n in sorted(await db.list_collection_names()) if n not in COLLEZIONI_ESCLUSE]
    conteggi = {n: await db[n].count_documents({}) for n in nomi}
    ultimo = await db.cron_log.find_one({"job": "backup-automatico"}, {"_id": 0}, sort=[("at", -1)])
    return {"collezioni": conteggi, "totale_documenti": sum(conteggi.values()), "ultimo_automatico": ultimo,
            "automatici": _lista(), "conserva_ultimi": BACKUP_KEEP}


@router.get("/admin/backup/export")
async def backup_export(admin: dict = Depends(_admin)):
    data, manifest = await crea_zip()
    await _d["db"].audit_log.insert_one({"id": os.urandom(8).hex(), "user_id": admin["id"], "user_name": admin.get("name"),
                                         "action": "backup_export", "target_type": "database", "at": manifest["creato_il"],
                                         "documenti": sum(manifest["collezioni"].values())})
    return StreamingResponse(io.BytesIO(data), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{_nome_file()}"'})


@router.post("/admin/backup/run")
async def backup_run(admin: dict = Depends(_admin)):
    return await salva_backup_automatico()


@router.get("/admin/backup/download/{nome}")
async def backup_download(nome: str, admin: dict = Depends(_admin)):
    if "/" in nome or not nome.startswith("backup_") or not nome.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Nome file non valido")
    path = BACKUP_DIR / nome
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup non trovato")
    return FileResponse(path, media_type="application/zip", filename=nome)
