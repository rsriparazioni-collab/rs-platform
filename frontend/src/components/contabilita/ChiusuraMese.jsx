import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { PeriodoPicker } from "./shared";

export const ChiusuraMese = ({ anno, mese, setAnno, setMese, goTab }) => {
  const [entita, setEntita] = useState("ditta");
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/chiusura-mese", { params: { entita, anno, mese } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [entita, anno, mese]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4" data-testid="chiusura-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><ClipboardCheck className="h-5 w-5 text-emerald-600" /> Chiusura mese</h2>
        <div className="flex items-center gap-2">
          <select value={entita} onChange={(e) => setEntita(e.target.value)} className="h-9 rounded-lg border border-slate-200 px-2 text-sm" data-testid="chiusura-entita"><option value="ditta">Ditta Enrico Mangani</option><option value="srls">RS Riparazioni SRLS</option></select>
          <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
        </div>
      </div>
      {d && (
        <>
          <div className={`flex items-center justify-between rounded-xl border p-4 ${d.completo ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`} data-testid="chiusura-stato">
            <div>
              <div className={`text-lg font-bold ${d.completo ? "text-emerald-800" : "text-amber-800"}`}>{d.completo ? "Mese completo: tutto verde" : `${d.completate}/${d.totale} voci completate`}</div>
              <div className="text-xs text-slate-600">{d.centro} · {d.mese_chiuso ? "mese chiuso" : "mese in corso (controlli fino a oggi)"}</div>
            </div>
            <div className="h-3 w-48 overflow-hidden rounded-full bg-white"><div className={`h-full ${d.completo ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${(d.completate / d.totale) * 100}%` }} /></div>
          </div>
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {d.voci.map((v) => (
              <li key={v.id} className="flex items-start gap-3 p-3 text-sm" data-testid={`chiusura-voce-${v.id}`}>
                {v.ok ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /> : v.opzionale ? <MinusCircle className="mt-0.5 h-5 w-5 shrink-0 text-slate-300" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" />}
                <div className="flex-1">
                  <div className="font-semibold text-slate-800">{v.titolo}</div>
                  <div className="text-xs text-slate-500">{v.dettaglio}</div>
                </div>
                {!v.ok && goTab && <button onClick={() => goTab(v.link)} className="text-xs font-semibold text-sky-700 hover:underline" data-testid={`chiusura-vai-${v.id}`}>Vai →</button>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};
