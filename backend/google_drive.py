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
    await scrivi_ritiro_su_foglio(ritiro_id)

# ---------------- Foglio Google "Ritiri <Negozio>" (una scheda per anno) ----------------
SHEET_HEADER = ["N. bolla", "Data", "Cognome", "Nome", "Telefono", "Codice fiscale", "Articolo", "IMEI", "Prezzo ritiro €",
                "N. documento", "Stato", "N. fattura", "Firma cliente", "Link PDF bolla", "Aggiornato il"]
STATO_LABEL = {"ritirato": "Ritirato", "in_vendita": "In vendita", "venduto": "Venduto", "pezzi_ricambio": "Pezzi di ricambio", "uso_interno": "Uso interno"}


def _sheets(doc: dict):
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=_credentials(doc), cache_discovery=False)


def _riga_ritiro(r: dict) -> list:
    firma = {"firmata": f"Firmata {(r.get('firma_at') or '')[:10]}", "in_attesa": "In attesa"}.get(r.get("firma_stato") or "", "")
    return [r.get("numero", ""), (r.get("data_ritiro") or "")[:10], r.get("cognome", ""), r.get("nome", ""), r.get("telefono", ""),
            r.get("codice_fiscale", ""), r.get("articolo", ""), r.get("imei", ""), r.get("prezzo_ritiro") if r.get("prezzo_ritiro") is not None else "",
            r.get("numero_documento", ""), STATO_LABEL.get(r.get("stato", ""), r.get("stato", "")), r.get("numero_fattura", ""), firma,
            r.get("drive_link", ""), datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")]


def _sheet_negozio_sync(doc: dict, store: dict, anno: str, righe: list) -> dict:
    """Crea (se serve) il foglio del negozio e la scheda dell'anno, poi aggiorna/aggiunge le righe per N. bolla."""
    drive = _service(doc)
    sheets = _sheets(doc)
    sheet_id = store.get("ritiri_sheet_id")
    if sheet_id:
        try:
            drive.files().get(fileId=sheet_id, fields="id,trashed").execute()
        except Exception:
            sheet_id = None
    if not sheet_id:
        parent = None
        for name in [ROOT_FOLDER, "Ritiri", store["nome"]]:
            parent = _find_or_create_folder(drive, name, parent)
        meta = {"name": f"Ritiri {store['nome']}", "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [parent]}
        sheet_id = drive.files().create(body=meta, fields="id").execute()["id"]
    ss = sheets.spreadsheets().get(spreadsheetId=sheet_id, fields="sheets(properties(title,sheetId))").execute()
    titoli = {s["properties"]["title"]: s["properties"]["sheetId"] for s in ss.get("sheets", [])}
    if anno not in titoli:
        if len(titoli) == 1 and list(titoli)[0] in ("Foglio1", "Sheet1"):
            sheets.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
                {"updateSheetProperties": {"properties": {"sheetId": list(titoli.values())[0], "title": anno}, "fields": "title"}}]}).execute()
        else:
            sheets.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [{"addSheet": {"properties": {"title": anno}}}]}).execute()
        sheets.spreadsheets().values().update(spreadsheetId=sheet_id, range=f"'{anno}'!A1", valueInputOption="USER_ENTERED",
                                              body={"values": [SHEET_HEADER]}).execute()
    esistenti = sheets.spreadsheets().values().get(spreadsheetId=sheet_id, range=f"'{anno}'!A:A").execute().get("values", [])
    if not esistenti:
        sheets.spreadsheets().values().update(spreadsheetId=sheet_id, range=f"'{anno}'!A1", valueInputOption="USER_ENTERED",
                                              body={"values": [SHEET_HEADER]}).execute()
        esistenti = [SHEET_HEADER[:1]]
    pos = {row[0]: i + 1 for i, row in enumerate(esistenti) if row}
    updates, nuove = [], []
    for riga in righe:
        if riga[0] in pos:
            updates.append({"range": f"'{anno}'!A{pos[riga[0]]}", "values": [riga]})
        else:
            nuove.append(riga)
    if updates:
        sheets.spreadsheets().values().batchUpdate(spreadsheetId=sheet_id, body={"valueInputOption": "USER_ENTERED", "data": updates}).execute()
    if nuove:
        sheets.spreadsheets().values().append(spreadsheetId=sheet_id, range=f"'{anno}'!A1", valueInputOption="USER_ENTERED",
                                              insertDataOption="INSERT_ROWS", body={"values": nuove}).execute()
    return {"sheet_id": sheet_id, "aggiornate": len(updates), "nuove": len(nuove)}


async def _salva_sheet_id(store_id: str, res: dict) -> None:
    await _d["db"].stores.update_one({"id": store_id}, {"$set": {"ritiri_sheet_id": res["sheet_id"],
                                                                  "ritiri_sheet_url": f"https://docs.google.com/spreadsheets/d/{res['sheet_id']}",
                                                                  "ritiri_sheet_synced_at": datetime.now(timezone.utc).isoformat()}})


async def scrivi_ritiro_su_foglio(ritiro_id: str) -> None:
    """Scrive/aggiorna la riga della bolla sul foglio Google del negozio."""
    db = _d["db"]
    try:
        doc = await _load_settings()
        r = await db.ritiri.find_one({"id": ritiro_id}, {"_id": 0})
        if not doc or not r:
            return
        store = await db.stores.find_one({"id": r["store_id"]}, {"_id": 0})
        if not store:
            return
        anno = (r.get("data_ritiro") or "")[:4] or str(datetime.now().year)
        res = await asyncio.to_thread(_sheet_negozio_sync, doc, store, anno, [_riga_ritiro(r)])
        await _salva_sheet_id(store["id"], res)
        await db.ritiri.update_one({"id": ritiro_id}, {"$set": {"sheet_synced_at": datetime.now(timezone.utc).isoformat()}, "$unset": {"sheet_error": ""}})
    except Exception as e:
        logger.warning("Sheet ritiro %s fallito: %s", ritiro_id, e)
        await db.ritiri.update_one({"id": ritiro_id}, {"$set": {"sheet_error": str(e)[:300]}})


async def riallinea_fogli_ritiri() -> dict:
    """Riscrive tutto lo storico dei ritiri sui fogli dei negozi (per negozio e anno)."""
    db = _d["db"]
    doc = await _load_settings()
    rep = {"negozi": [], "errori": []}
    if not doc:
        return rep
    now = datetime.now(timezone.utc).isoformat()
    async for store in db.stores.find({}, {"_id": 0}):
        ritiri = await db.ritiri.find({"store_id": store["id"]}, {"_id": 0}).sort("data_ritiro", 1).to_list(20000)
        if not ritiri:
            continue
        per_anno: dict = {}
        for r in ritiri:
            per_anno.setdefault((r.get("data_ritiro") or "")[:4] or str(datetime.now().year), []).append(r)
        for anno, lst in sorted(per_anno.items()):
            try:
                res = await asyncio.to_thread(_sheet_negozio_sync, doc, store, anno, [_riga_ritiro(r) for r in lst])
                store["ritiri_sheet_id"] = res["sheet_id"]
                await _salva_sheet_id(store["id"], res)
                await db.ritiri.update_many({"id": {"$in": [r["id"] for r in lst]}}, {"$set": {"sheet_synced_at": now}, "$unset": {"sheet_error": ""}})
                rep["negozi"].append({"negozio": store["nome"], "anno": anno, **res})
            except Exception as e:
                logger.warning("Riallineamento foglio %s/%s fallito: %s", store["nome"], anno, e)
                rep["errori"].append({"negozio": store["nome"], "anno": anno, "errore": str(e)[:300]})
    await db.settings.update_one({"key": "fogli_ritiri_sync"}, {"$set": {"key": "fogli_ritiri_sync", "at": now, "report": rep}}, upsert=True)
    return rep


@router.post("/google-drive/riallinea-fogli-ritiri")
async def riallinea_fogli(background_tasks: BackgroundTasks, user: dict = Depends(_current_user)):
    _solo_admin(user)
    if not await _load_settings():
        raise HTTPException(status_code=400, detail="Google Drive non collegato")
    n = await _d["db"].ritiri.count_documents({})
    background_tasks.add_task(riallinea_fogli_ritiri)
    return {"avviati": n}


@router.get("/google-drive/fogli-ritiri")
async def fogli_ritiri_status(user: dict = Depends(_current_user)):
    db = _d["db"]
    stores = await db.stores.find({}, {"_id": 0, "id": 1, "nome": 1, "ritiri_sheet_url": 1, "ritiri_sheet_synced_at": 1}).to_list(200)
    ultimo = await db.settings.find_one({"key": "fogli_ritiri_sync"}, {"_id": 0})
    return {"connected": bool(await _load_settings()), "negozi": stores, "ultimo_riallineamento": ultimo,
            "non_sincronizzati": await db.ritiri.count_documents({"sheet_synced_at": {"$exists": False}}),
            "errori": await db.ritiri.count_documents({"sheet_error": {"$exists": True}})}




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
