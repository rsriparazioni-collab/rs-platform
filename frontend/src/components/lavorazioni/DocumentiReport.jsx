import { useEffect, useState } from "react";
import { FileCheck2, ChevronDown, ChevronUp } from "lucide-react";
import api from "../../lib/api";

export const DocumentiReport = ({ onOpen }) => {
  const [d, setD] = useState(null);
  const [aperto, setAperto] = useState(null);
  useEffect(() => { api.get("/lavorazioni/documenti-report").then((r) => setD(r.data)).catch(() => setD(null)); }, []);
  if (!d || !d.negozi.length) return null;
  const colore = (p) => (p >= 80 ? "bg-emerald-500" : p >= 50 ? "bg-amber-400" : "bg-rose-500");
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3" data-testid="documenti-report">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800"><FileCheck2 className="h-4 w-4 text-emerald-600" /> Documenti pratiche aperte (bolletta + documento)</h3>
        <span className="text-xs text-slate-500" data-testid="documenti-report-totale">{d.totali.completi}/{d.totali.totale} complete · {d.totali.pct_completi}%</span>
      </div>
      <div className="space-y-1.5">
        {d.negozi.map((s) => (
          <div key={s.store_id} data-testid={`documenti-report-${s.store_id}`}>
            <button type="button" className="flex w-full items-center gap-2 text-left text-xs" onClick={() => setAperto(aperto === s.store_id ? null : s.store_id)}>
              <span className="w-24 shrink-0 font-semibold text-slate-700">{s.negozio}</span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><span className={`block h-full ${colore(s.pct_completi)}`} style={{ width: `${s.pct_completi}%` }} /></span>
              <span className="w-40 shrink-0 text-right tabular-nums text-slate-600">{s.completi}/{s.totale} complete · <span className="text-rose-600">{s.totale - s.completi} no</span></span>
              {s.mancanti.length > 0 && (aperto === s.store_id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
            </button>
            {aperto === s.store_id && s.mancanti.length > 0 && (
              <div className="ml-26 mt-1 flex flex-wrap gap-1 pl-24">
                {s.mancanti.map((m) => <button key={m.id} type="button" onClick={() => onOpen?.({ id: m.id })} className="rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[11px] text-rose-800 hover:bg-rose-100" data-testid={`documenti-mancante-${m.id}`}>{m.nome} <span className="text-rose-500">manca {m.manca.join("+")}</span></button>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
