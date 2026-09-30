import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Num, PeriodoPicker, eur } from "./shared";

const Pct = ({ v }) => v == null ? <span className="text-slate-300">—</span> : <span className={v >= 0 ? "text-emerald-700" : "text-rose-700"}>{v > 0 ? "+" : ""}{v.toFixed(2)}%</span>;

export const ReportAnnuale = ({ storeId, anno, setAnno, isAdmin }) => {
  const [r, setR] = useState(null);
  const [importing, setImporting] = useState(false);
  const importa = async () => {
    setImporting(true);
    try { const x = await api.post("/contabilita/report/importa-fogli"); toast.success(x.data.esito.map((e) => `${e.negozio}: ${e.errore || e.mesi_importati + " mesi"}`).join(" · ")); load(); }
    catch (e) { toast.error(apiError(e)); } finally { setImporting(false); }
  };
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => api.get("/contabilita/report/annuale", { params: { store_id: storeId, anno } }).then((x) => setR(x.data)).catch((e) => toast.error(apiError(e))), [storeId, anno]);
  useEffect(() => { load(); }, [load]);
  const salvaStorico = async () => {
    try { await api.put(`/contabilita/report/storico/${storeId}/${edit.anno}/${edit.mese}`, { enel: parseFloat(edit.enel) || 0, altro: parseFloat(edit.altro) || 0 }); setEdit(null); toast.success("Storico salvato"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  if (!r) return null;
  const max = Math.max(...r.mesi.map((m) => Math.max(m.tot, m.tot_ap)), 1);
  return (
    <div className="space-y-5" data-testid="report-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PeriodoPicker anno={anno} setAnno={setAnno} soloAnno />
        {isAdmin && <Button size="sm" variant="outline" onClick={importa} disabled={importing} data-testid="report-importa-fogli">{importing ? "Importo…" : "Importa storico dai fogli Google"}</Button>}
        <p className="w-full text-xs text-slate-500">Fatturato = corrispettivi inseriti + entrate del punto di pareggio (ENEL/Energia separato). Clicca un mese per inserire i valori storici (il dato storico prevale finché corrispettivi + entrate PDP del mese non lo superano).</p>
      </div>
      <div className="flex h-40 items-end gap-2 rounded-xl border border-slate-200 bg-white p-4" data-testid="report-grafico">
        {r.mesi.map((m) => (
          <div key={m.mese} className="flex flex-1 flex-col items-center gap-1" title={`${m.nome}: ${eur(m.tot)} (AP ${eur(m.tot_ap)})`}>
            <div className="flex w-full items-end justify-center gap-0.5" style={{ height: 110 }}>
              <div className="w-1/2 rounded-t bg-slate-200" style={{ height: `${m.tot_ap / max * 100}%` }} />
              <div className="w-1/2 rounded-t bg-sky-600" style={{ height: `${m.tot / max * 100}%` }} />
            </div>
            <span className="text-[10px] uppercase text-slate-500">{m.nome.slice(0, 3)}</span>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm" data-testid="report-table">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr>
            <th className="px-3 py-2 text-left">Mese</th><th className="px-3 py-2 text-right">{anno - 1} ENEL</th><th className="px-3 py-2 text-right">{anno - 1} Altro</th><th className="px-3 py-2 text-right">{anno - 1} Tot</th>
            <th className="px-3 py-2 text-right">{anno} ENEL</th><th className="px-3 py-2 text-right">{anno} Altro</th><th className="px-3 py-2 text-right">{anno} Tot</th><th className="px-3 py-2 text-right">% ENEL AP</th><th className="px-3 py-2 text-right">% Altro AP</th><th className="px-3 py-2 text-right">% Tot AP</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {r.mesi.map((m) => (
              <tr key={m.mese} className="cursor-pointer hover:bg-sky-50" onClick={() => setEdit({ anno, mese: m.mese, nome: m.nome, enel: m.enel || "", altro: m.altro || "" })} data-testid={`report-row-${m.mese}`}>
                <td className="px-3 py-1.5 font-medium">{m.nome}{m.storico && <span className="ml-1 text-[10px] text-slate-400">storico</span>}</td>
                <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{m.enel_ap ? eur(m.enel_ap) : ""}</td><td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{m.altro_ap ? eur(m.altro_ap) : ""}</td><td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{m.tot_ap ? eur(m.tot_ap) : ""}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{m.enel ? eur(m.enel) : ""}</td><td className="px-3 py-1.5 text-right tabular-nums">{m.altro ? eur(m.altro) : ""}</td><td className="px-3 py-1.5 text-right font-semibold tabular-nums">{m.tot ? eur(m.tot) : ""}</td>
                <td className="px-3 py-1.5 text-right"><Pct v={m.pct_enel} /></td><td className="px-3 py-1.5 text-right"><Pct v={m.pct_altro} /></td><td className="px-3 py-1.5 text-right"><Pct v={m.pct} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50 font-semibold"><tr>
            <td className="px-3 py-2">Totale</td><td className="px-3 py-2 text-right tabular-nums">{eur(r.totali.enel_ap)}</td><td className="px-3 py-2 text-right tabular-nums">{eur(r.totali.altro_ap)}</td><td className="px-3 py-2 text-right tabular-nums">{eur(r.totali.tot_ap)}</td>
            <td className="px-3 py-2 text-right tabular-nums">{eur(r.totali.enel)}</td><td className="px-3 py-2 text-right tabular-nums">{eur(r.totali.altro)}</td><td className="px-3 py-2 text-right tabular-nums" data-testid="report-tot">{eur(r.totali.tot)}</td><td /><td /><td className="px-3 py-2 text-right"><Pct v={r.totali.pct} /></td></tr></tfoot>
        </table>
      </div>
      {edit && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4" data-testid="storico-editor">
          <p className="w-full text-sm font-medium">Valori storici {edit.nome} {edit.anno} (usati finché i dati inseriti nel gestionale non li superano)</p>
          <label className="text-xs text-slate-600">ENEL / Energia<div className="w-36"><Num value={edit.enel} onChange={(v) => setEdit({ ...edit, enel: v })} testid="storico-enel" /></div></label>
          <label className="text-xs text-slate-600">Altro<div className="w-36"><Num value={edit.altro} onChange={(v) => setEdit({ ...edit, altro: v })} testid="storico-altro" /></div></label>
          <Button size="sm" onClick={salvaStorico} data-testid="storico-salva">Salva</Button>
          <Button size="sm" variant="ghost" onClick={() => setEdit(null)}>Chiudi</Button>
        </div>
      )}
    </div>
  );
};
