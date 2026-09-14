import { useState } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

function Negozi({ rows, kind }) {
  return (
    <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-xs">
      {rows.map((n) => (
        <li key={n.store} className="flex items-center justify-between px-3 py-1.5">
          <span className="font-medium text-slate-800">{n.store}{n.tab && n.tab !== n.store ? <span className="text-slate-400"> (pagina {n.tab})</span> : null}</span>
          {n.status === "ok"
            ? <span className="text-slate-600">{kind === "energia" ? `${n.nuovi} nuovi · ${n.aggiornati} aggiornati` : `${n.nuove} nuove · ${n.aggiornate} aggiornate`}</span>
            : <span className="flex items-center gap-1 text-amber-700"><AlertTriangle className="h-3 w-3" /> {n.status.replace(/_/g, " ")}</span>}
        </li>
      ))}
    </ul>
  );
}

export default function SyncFogliDialog({ open, onClose, onDone }) {
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (dryRun) => {
    setBusy(true);
    try {
      const r = await api.post("/admin/sync-fogli", { dry_run: dryRun });
      if (dryRun) setPreview(r.data); else { setResult(r.data); toast.success("Sincronizzazione completata"); onDone?.(); }
    } catch (e) { toast.error(apiError(e, "Sincronizzazione fallita")); }
    finally { setBusy(false); }
  };

  const close = () => { setPreview(null); setResult(null); onClose(); };
  const data = result || preview;
  const e = data?.energia, r = data?.riparazioni;
  const nothing = data && (e?.nuovi || 0) + (e?.aggiornati || 0) + (r?.nuove || 0) + (r?.aggiornate || 0) === 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="sync-fogli-dialog">
        <DialogHeader><DialogTitle className="font-heading text-xl">Sincronizza fogli Google</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-500">Legge i fogli energia (per negozio) e riparazioni, aggiunge le righe nuove e aggiorna quelle cambiate. Prima ti mostro l'anteprima: nulla viene scritto finché non confermi.</p>

        {!data && (
          <div className="flex justify-end">
            <Button onClick={() => run(true)} disabled={busy} className="gap-2 bg-slate-900 hover:bg-slate-800" data-testid="sync-preview-button"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> {busy ? "Lettura fogli..." : "Calcola anteprima"}</Button>
          </div>
        )}

        {data && (
          <div className="space-y-4" data-testid="sync-preview">
            {result && <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800" data-testid="sync-done"><CheckCircle2 className="h-4 w-4" /> Import eseguito</div>}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-slate-900">Energia · <span data-testid="sync-energia-nuovi">{e?.nuovi ?? 0}</span> nuovi, <span data-testid="sync-energia-aggiornati">{e?.aggiornati ?? 0}</span> aggiornati, {e?.invariati ?? 0} uguali</h3>
                {e && <Negozi rows={e.negozi} kind="energia" />}
                {e?.campi_aggiornati && Object.keys(e.campi_aggiornati).length > 0 && (
                  <p className="text-xs text-slate-500">Campi: {Object.entries(e.campi_aggiornati).map(([k, v]) => `${k} (${v})`).join(", ")}</p>
                )}
                {e?.esempi_nuovi?.length > 0 && <div className="text-xs text-slate-600"><p className="font-medium">Nuovi clienti:</p><ul className="list-disc pl-4">{e.esempi_nuovi.map((x) => <li key={x}>{x}</li>)}</ul></div>}
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-slate-900">Riparazioni · <span data-testid="sync-rip-nuove">{r?.nuove ?? 0}</span> nuove, {r?.aggiornate ?? 0} aggiornate, {r?.invariate ?? 0} uguali</h3>
                {r && <Negozi rows={r.negozi} kind="rip" />}
                {r?.saltate_modificate_in_app > 0 && <p className="text-xs text-slate-500">{r.saltate_modificate_in_app} già modificate nel gestionale: non toccate.</p>}
                {r?.esempi_nuove?.length > 0 && <div className="text-xs text-slate-600"><p className="font-medium">Nuove riparazioni:</p><ul className="list-disc pl-4">{r.esempi_nuove.map((x) => <li key={x}>{x}</li>)}</ul></div>}
              </div>
            </div>
            {nothing && !result && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600" data-testid="sync-nothing">Tutto già aggiornato: nessuna modifica da importare.</p>}
            <div className="flex justify-end gap-3 border-t border-slate-200 pt-4">
              <Button type="button" variant="outline" onClick={close} data-testid="sync-close">Chiudi</Button>
              {!result && !nothing && <Button onClick={() => run(false)} disabled={busy} className="bg-emerald-600 hover:bg-emerald-700" data-testid="sync-confirm-button">{busy ? "Importazione..." : "Conferma e importa"}</Button>}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
