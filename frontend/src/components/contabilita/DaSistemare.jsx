import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import api from "../../lib/api";

const LIV = {
  alto: { cls: "border-rose-200 bg-rose-50 text-rose-900", dot: "bg-rose-500", label: "Urgente" },
  medio: { cls: "border-amber-200 bg-amber-50 text-amber-900", dot: "bg-amber-500", label: "Da fare" },
  basso: { cls: "border-slate-200 bg-slate-50 text-slate-700", dot: "bg-slate-400", label: "Consiglio" },
};

export const DaSistemare = ({ storeId, anno, mese, goTab, refreshKey }) => {
  const [d, setD] = useState(null);
  const [aperto, setAperto] = useState(false);
  const load = useCallback(() => {
    if (!storeId) return;
    api.get("/contabilita/da-sistemare", { params: { store_id: storeId, anno, mese } }).then((r) => setD(r.data)).catch(() => setD(null));
  }, [storeId, anno, mese]);
  useEffect(() => { load(); }, [load, refreshKey]);
  if (!d) return null;
  if (!d.items.length) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" data-testid="da-sistemare-ok">
        <CheckCircle2 className="h-5 w-5" /> Tutto in ordine per questo mese: nessuna cosa da sistemare.
      </div>
    );
  }
  const visibili = aperto ? d.items : d.items.slice(0, 3);
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="da-sistemare">
      <button type="button" onClick={() => setAperto((a) => !a)} className="flex w-full items-center justify-between px-4 py-3 text-left" data-testid="da-sistemare-toggle">
        <span className="flex items-center gap-2 font-semibold text-slate-900">
          <AlertTriangle className={`h-5 w-5 ${d.alto ? "text-rose-600" : "text-amber-500"}`} />
          Cose da sistemare <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-white" data-testid="da-sistemare-count">{d.totale}</span>
          {d.alto > 0 && <span className="text-xs font-normal text-rose-700">{d.alto} urgent{d.alto === 1 ? "e" : "i"}</span>}
        </span>
        {aperto ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
      </button>
      <ol className="space-y-1.5 border-t border-slate-100 p-3">
        {visibili.map((p, i) => (
          <li key={i} className={`flex items-start gap-3 rounded-lg border px-3 py-2 text-sm ${LIV[p.livello].cls}`} data-testid={`da-sistemare-item-${i}`}>
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${LIV[p.livello].dot}`} />
            <span className="flex-1">{p.testo}</span>
            {goTab && <button type="button" onClick={() => goTab(p.tab, p.data, p.tipo)} className="shrink-0 text-xs font-semibold underline-offset-2 hover:underline" data-testid={`da-sistemare-vai-${i}`}>Vai</button>}
          </li>
        ))}
      </ol>
      {!aperto && d.items.length > 3 && <p className="px-4 pb-3 text-xs text-slate-500">… e altre {d.items.length - 3}. Clicca sul titolo per vederle tutte.</p>}
    </div>
  );
};
