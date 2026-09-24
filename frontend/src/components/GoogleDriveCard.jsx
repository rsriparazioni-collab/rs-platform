import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Cloud, CloudOff, RefreshCw, Unplug } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { fmtDateTime } from "../lib/constants";

export default function GoogleDriveCard({ isAdmin }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [params, setParams] = useSearchParams();

  const load = useCallback(() => api.get("/google-drive/status").then((r) => setStatus(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const drive = params.get("drive");
    if (!drive) return;
    if (drive === "ok") toast.success("Google Drive collegato: le bolle verranno archiviate automaticamente");
    else toast.error(`Collegamento Google Drive fallito (${params.get("msg") || "errore"})`);
    params.delete("drive"); params.delete("msg");
    setParams(params, { replace: true });
  }, [params, setParams]);

  const connect = async () => {
    setBusy(true);
    try { const r = await api.get("/google-drive/connect"); window.location.href = r.data.authorization_url; }
    catch (e) { toast.error(apiError(e)); setBusy(false); }
  };
  const disconnect = async () => {
    if (!window.confirm("Scollegare Google Drive? Le bolle già caricate restano su Drive.")) return;
    setBusy(true);
    try { await api.post("/google-drive/disconnect"); toast.success("Google Drive scollegato"); load(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const sync = async () => {
    setBusy(true);
    try { const r = await api.post("/google-drive/sync-ritiri"); toast.success(`Caricamento avviato per ${r.data.avviati} bolle`); setTimeout(load, 4000); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  if (!status || (!status.connected && !isAdmin)) return null;
  const ok = status.connected;
  return (
    <div className={`flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm ${ok ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/60"}`} data-testid="google-drive-card">
      {ok ? <Cloud className="h-5 w-5 text-emerald-700" /> : <CloudOff className="h-5 w-5 text-amber-700" />}
      <div className="flex-1">
        <p className="font-semibold text-slate-800" data-testid="google-drive-status">
          {ok ? `Google Drive collegato${status.email ? ` (${status.email})` : ""}` : "Google Drive non collegato"}
        </p>
        <p className="text-xs text-slate-600">
          {ok
            ? <>Cartella "{status.folder}/Ritiri/&lt;Negozio&gt;/&lt;Anno&gt;" · {status.ritiri_caricati} bolle caricate{status.ritiri_da_caricare > 0 ? `, ${status.ritiri_da_caricare} da caricare` : ""}{status.connected_at ? ` · collegato il ${fmtDateTime(status.connected_at)}` : ""}</>
            : "Collega l'account Google aziendale per archiviare automaticamente bolle e documenti dei ritiri."}
          {status.ultimo_errore && <span className="ml-1 text-rose-600" data-testid="google-drive-error">Ultimo errore ({status.ultimo_errore.numero}): {status.ultimo_errore.drive_error}</span>}
        </p>
      </div>
      {isAdmin && !ok && <Button size="sm" disabled={busy || !status.configured} onClick={connect} className="gap-1.5 bg-slate-900 hover:bg-slate-800" data-testid="google-drive-connect"><Cloud className="h-4 w-4" /> Collega Google Drive</Button>}
      {isAdmin && ok && status.ritiri_da_caricare > 0 && <Button size="sm" variant="outline" disabled={busy} onClick={sync} className="gap-1.5" data-testid="google-drive-sync"><RefreshCw className="h-4 w-4" /> Carica {status.ritiri_da_caricare} bolle mancanti</Button>}
      {isAdmin && ok && <Button size="sm" variant="ghost" disabled={busy} onClick={disconnect} className="gap-1.5 text-slate-500" data-testid="google-drive-disconnect"><Unplug className="h-4 w-4" /> Scollega</Button>}
    </div>
  );
}
