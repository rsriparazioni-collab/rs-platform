import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Sparkles, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";

export const PdpAnalisi = ({ centroId, anno, mese }) => {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(false);
  const load = useCallback(() => api.get("/contabilita/pdp/analisi", { params: { centro_id: centroId, anno, mese } }).then((r) => setD(r.data)).catch(() => {}), [centroId, anno, mese]);
  useEffect(() => { load(); }, [load]);
  const genera = async () => {
    setLoading(true);
    try { const r = await api.post("/contabilita/pdp/analisi", null, { params: { centro_id: centroId, anno, mese } }); setD(r.data); toast.success("Analisi generata"); }
    catch (e) { toast.error(apiError(e)); } finally { setLoading(false); }
  };
  return (
    <div className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/70 to-white" data-testid="pdp-analisi">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 px-4 py-3">
        <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-indigo-600" /><h3 className="text-sm font-semibold text-slate-900">Strategia migliorativa (AI)</h3>
          {d?.at && <span className="text-xs text-slate-500">generata il {new Date(d.at).toLocaleString("it-IT")}</span>}</div>
        <Button size="sm" onClick={genera} disabled={loading} data-testid="pdp-analisi-genera"><RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />{loading ? "Analizzo…" : d?.testo ? "Rigenera analisi" : "Genera analisi"}</Button>
      </div>
      <div className="px-5 py-4">
        {d?.testo ? (
          <div className="text-sm leading-relaxed text-slate-700 [&_h1]:mt-3 [&_h1]:text-sm [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:mt-3 [&_h3]:text-sm [&_h3]:font-semibold [&_p]:my-1.5 [&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_strong]:text-slate-900" data-testid="pdp-analisi-testo"><ReactMarkdown>{d.testo}</ReactMarkdown></div>
        ) : (
          <p className="text-sm text-slate-500" data-testid="pdp-analisi-vuota">Premi "Genera analisi": l'AI confronta entrate, spese fisse, fornitori e fatture del mese con i mesi precedenti e propone azioni strategiche e spunti fiscali (da verificare col commercialista).</p>
        )}
        <p className="mt-3 text-[11px] text-slate-400">Gli spunti fiscali sono indicazioni generali, non sostituiscono il parere del commercialista.</p>
      </div>
    </div>
  );
};
