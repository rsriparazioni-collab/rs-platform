import { useCallback, useEffect, useState } from "react";
import { DatabaseBackup, Download, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { Button } from "../components/ui/button";
import { fmtDate } from "../lib/constants";

const fmtSize = (b) => (b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export const BackupCard = () => {
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/admin/backup").then((r) => setInfo(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const esporta = async () => {
    setBusy(true);
    try {
      await downloadBlob("/admin/backup/export", `backup_gestionale_${new Date().toISOString().slice(0, 10)}.zip`);
      toast.success("Backup scaricato: conservalo su una chiavetta o un disco esterno");
    } catch (e) { toast.error(apiError(e, "Esportazione non riuscita")); } finally { setBusy(false); }
  };

  const eseguiOra = async () => {
    setBusy(true);
    try { await api.post("/admin/backup/run"); toast.success("Backup automatico creato"); load(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid="backup-card">
      <div className="flex items-start gap-3">
        <DatabaseBackup className="mt-0.5 h-6 w-6 text-emerald-600" />
        <div className="flex-1">
          <h2 className="font-heading text-lg font-semibold text-slate-900">Backup di tutti i dati</h2>
          <p className="mt-1 text-sm text-slate-500">
            Scarica una copia completa del database (clienti, servizi, magazzino, ritiri, vendite, utenti, KPI…) in formato ZIP.
            Utile in caso di assenza di internet: il file può essere importato su un server locale in negozio.
          </p>
          {info && (
            <p className="mt-2 text-xs text-slate-500" data-testid="backup-totale">
              {info.totale_documenti} documenti in {Object.keys(info.collezioni).length} collezioni · backup automatico ogni 24h (conserva gli ultimi {info.conserva_ultimi})
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={esporta} disabled={busy} className="gap-1.5" data-testid="backup-export-button"><Download className="h-4 w-4" /> Esporta tutti i dati</Button>
            <Button variant="outline" onClick={eseguiOra} disabled={busy} className="gap-1.5" data-testid="backup-run-button"><RefreshCw className="h-4 w-4" /> Crea backup automatico ora</Button>
          </div>
          {info?.automatici?.length > 0 && (
            <ul className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-100 text-sm" data-testid="backup-list">
              {info.automatici.map((b) => (
                <li key={b.file} className="flex items-center justify-between px-3 py-2">
                  <span className="text-slate-700">{fmtDate(b.creato_il)} · {fmtSize(b.size)}</span>
                  <button className="text-emerald-700 hover:underline" onClick={() => downloadBlob(`/admin/backup/download/${b.file}`, b.file)} data-testid={`backup-download-${b.file}`}>Scarica</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
