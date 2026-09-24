import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter()
_d: dict = {}
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
ROOT_FOLDER = "Gestionale RS"
SETTINGS_KEY = "google_drive"


def setup(**deps):
    _d.update(deps)


async def _current_user(request: Request):
    auth = request.headers.get("authorization", "")
    creds = None
    if auth.lower().startswith("bearer "):
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth[7:])
    return await _d["get_current_user"](request, creds)


def _solo_admin(user: dict) -> None:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")


def _redirect_uri(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    scheme = "http" if host.startswith("localhost") else "https"
    return f"{scheme}://{host}/api/google-drive/callback"


def _client_config(redirect_uri: str) -> dict:
    return {"web": {"client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]}}


async def _load_settings() -> dict | None:
    return await _d["db"].settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})


def _credentials(doc: dict):
    from google.oauth2.credentials import Credentials
    return Credentials(token=None, refresh_token=_d["fernet"]().decrypt(doc["refresh_token_enc"].encode()).decode(),
                       token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["GOOGLE_CLIENT_ID"],
                       client_secret=os.environ["GOOGLE_CLIENT_SECRET"], scopes=doc.get("scopes") or SCOPES)


def _service(doc: dict):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_credentials(doc), cache_discovery=False)


def _find_or_create_folder(svc, name: str, parent: str | None) -> str:
    safe = name.replace("'", "\\'")
    q = f"name = '{safe}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent:
        q += f" and '{parent}' in parents"
    res = svc.files().list(q=q, fields="files(id)", pageSize=1).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        meta["parents"] = [parent]
    return svc.files().create(body=meta, fields="id").execute()["id"]


def _upload_sync(doc: dict, folders: list, filename: str, data: bytes, content_type: str, file_id: str | None) -> dict:
    from googleapiclient.http import MediaIoBaseUpload
    svc = _service(doc)
    parent = None
    for name in [ROOT_FOLDER] + folders:
        parent = _find_or_create_folder(svc, name, parent)
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=content_type, resumable=False)
    if file_id:
        try:
            return svc.files().update(fileId=file_id, media_body=media, body={"name": filename}, fields="id,webViewLink").execute()
        except Exception:
            pass
    return svc.files().create(body={"name": filename, "parents": [parent]}, media_body=media, fields="id,webViewLink").execute()


async def upload_file(folders: list, filename: str, data: bytes, content_type: str, file_id: str | None = None) -> dict | None:
    doc = await _load_settings()
    if not doc:
        return None
    return await asyncio.to_thread(_upload_sync, doc, folders, filename, data, content_type, file_id)


async def carica_ritiro_su_drive(ritiro_id: str) -> None:
    """Carica (o aggiorna) la bolla del ritiro con i documenti su Drive: Gestionale RS/Ritiri/<Negozio>/<Anno>."""
    db = _d["db"]
    try:
        r = await db.ritiri.find_one({"id": ritiro_id}, {"_id": 0})
        if not r or not r.get("storage_path"):
            return
        store = await db.stores.find_one({"id": r["store_id"]}, {"_id": 0, "nome": 1}) or {}
        data, _ = _d["get_object"](r["storage_path"])
        anno = (r.get("data_ritiro") or "")[:4] or str(datetime.now().year)
        fname = f"{r['numero'].replace('/', '-')}_{r.get('cognome', '')}_{r.get('nome', '')}".strip("_") + ".pdf"
        res = await upload_file(["Ritiri", store.get("nome", "Negozio"), anno], fname, data, "application/pdf", r.get("drive_file_id"))
        if res:
            await db.ritiri.update_one({"id": ritiro_id}, {"$set": {"drive_file_id": res["id"], "drive_link": res.get("webViewLink", ""),
                                                                    "drive_uploaded_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.warning("Drive upload ritiro %s fallito: %s", ritiro_id, e)
        await db.ritiri.update_one({"id": ritiro_id}, {"$set": {"drive_error": str(e)[:300]}})


async def carica_report_su_drive(store_nome: str, anno: int, mese: int, pdf: bytes, zip_data: bytes) -> None:
    try:
        await upload_file(["Report commercialista", store_nome], f"Report_ritiri_{store_nome}_{anno}-{mese:02d}.pdf", pdf, "application/pdf")
        await upload_file(["Report commercialista", store_nome], f"Ritiri_{store_nome}_{anno}-{mese:02d}_bolle_documenti.zip", zip_data, "application/zip")
    except Exception as e:
        logger.warning("Drive upload report fallito: %s", e)


@router.get("/google-drive/status")
async def drive_status(user: dict = Depends(_current_user)):
    doc = await _load_settings()
    configured = bool(os.environ.get("GOOGLE_CLIENT_ID")) and bool(os.environ.get("GOOGLE_CLIENT_SECRET"))
    if not doc:
        return {"configured": configured, "connected": False}
    db = _d["db"]
    return {"configured": configured, "connected": True, "email": doc.get("email", ""), "connected_at": doc.get("connected_at"),
            "connected_by": doc.get("connected_by_name", ""), "folder": ROOT_FOLDER,
            "ritiri_caricati": await db.ritiri.count_documents({"drive_file_id": {"$exists": True}}),
            "ritiri_da_caricare": await db.ritiri.count_documents({"drive_file_id": {"$exists": False}, "storage_path": {"$nin": [None, ""]}}),
            "ultimo_errore": (await db.ritiri.find_one({"drive_error": {"$exists": True}}, {"_id": 0, "drive_error": 1, "numero": 1}))}


@router.get("/google-drive/connect")
async def drive_connect(request: Request, user: dict = Depends(_current_user)):
    _solo_admin(user)
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        raise HTTPException(status_code=400, detail="Credenziali Google non configurate")
    from google_auth_oauthlib.flow import Flow
    redirect_uri = _redirect_uri(request)
    flow = Flow.from_client_config(_client_config(redirect_uri), scopes=SCOPES, redirect_uri=redirect_uri)
    state = uuid.uuid4().hex
    await _d["db"].oauth_states.insert_one({"state": state, "user_id": user["id"], "user_name": user["name"], "redirect_uri": redirect_uri,
                                            "created_at": datetime.now(timezone.utc).isoformat()})
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return {"authorization_url": url}


@router.get("/google-drive/callback")
async def drive_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    db = _d["db"]
    front = os.environ.get("FRONTEND_URL", "").rstrip("/") or f"https://{request.headers.get('host', '')}"
    st = await db.oauth_states.find_one_and_delete({"state": state})
    if error or not st or not code:
        return RedirectResponse(f"{front}/ritiri?drive=error&msg={error or 'stato_non_valido'}")
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_config(_client_config(st["redirect_uri"]), scopes=None, redirect_uri=st["redirect_uri"])
        flow.fetch_token(code=code)
        creds = flow.credentials
        if not set(SCOPES).issubset(set(creds.scopes or [])):
            return RedirectResponse(f"{front}/ritiri?drive=error&msg=permessi_drive_mancanti")
        if not creds.refresh_token:
            return RedirectResponse(f"{front}/ritiri?drive=error&msg=refresh_token_mancante")
        email = ""
        try:
            from googleapiclient.discovery import build
            about = build("drive", "v3", credentials=creds, cache_discovery=False).about().get(fields="user(emailAddress)").execute()
            email = about.get("user", {}).get("emailAddress", "")
        except Exception:
            pass
        await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {
            "key": SETTINGS_KEY, "refresh_token_enc": _d["fernet"]().encrypt(creds.refresh_token.encode()).decode(),
            "scopes": list(creds.scopes or SCOPES), "email": email, "connected_by": st["user_id"], "connected_by_name": st["user_name"],
            "connected_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return RedirectResponse(f"{front}/ritiri?drive=ok")
    except Exception as e:
        logger.error("Drive callback fallito: %s", e)
        return RedirectResponse(f"{front}/ritiri?drive=error&msg=oauth")


@router.post("/google-drive/disconnect")
async def drive_disconnect(user: dict = Depends(_current_user)):
    _solo_admin(user)
    doc = await _load_settings()
    if doc:
        try:
            import httpx
            token = _d["fernet"]().decrypt(doc["refresh_token_enc"].encode()).decode()
            async with httpx.AsyncClient(timeout=10) as h:
                await h.post("https://oauth2.googleapis.com/revoke", params={"token": token})
        except Exception:
            pass
    await _d["db"].settings.delete_one({"key": SETTINGS_KEY})
    return {"connected": False}


async def _sync_tutti() -> None:
    db = _d["db"]
    ids = [r["id"] async for r in db.ritiri.find({"drive_file_id": {"$exists": False}, "storage_path": {"$nin": [None, ""]}}, {"_id": 0, "id": 1})]
    for rid in ids:
        await carica_ritiro_su_drive(rid)


@router.post("/google-drive/sync-ritiri")
async def drive_sync(background_tasks: BackgroundTasks, user: dict = Depends(_current_user)):
    _solo_admin(user)
    if not await _load_settings():
        raise HTTPException(status_code=400, detail="Google Drive non collegato")
    n = await _d["db"].ritiri.count_documents({"drive_file_id": {"$exists": False}, "storage_path": {"$nin": [None, ""]}})
    background_tasks.add_task(_sync_tutti)
    return {"avviati": n}
