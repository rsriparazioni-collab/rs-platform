import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, FileUp, Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { eur } from "./shared";

const UploadBtn = ({ label, onFile, testid }) => {
  const ref = useRef();
  return (<>
    <input ref={ref} type="file" accept=".csv,.xlsx,.txt" className="hidden" onChange={(e) => { if (e.target.files[0]) onFile(e.target.files[0]); e.target.value = ""; }} data-testid={`${testid}-input`} />
    <Button size="sm" variant="outline" onClick={() => ref.current.click()} data-testid={testid}><FileUp className="mr-1 h-4 w-4" /> {label}</Button>
  </>);
};

export const FattureAde = ({ centroId, anno, mese, onChanged }) => {
  const [d, setD] = useState({ righe: [], totali: { emesse: 0, ricevute: 0, n_emesse: 0, n_ricevute: 0 } });
  const [aperto, setAperto] = useState(false);
  const load = useCallback(() => api.get("/contabilita/pdp/fatture", { params: { centro_id: centroId, anno, mese } }).then((r) => setD(r.data)).catch(() => {}), [centroId, anno, mese]);
  useEffect(() => { load(); }, [load]);
  const upload = async (direzione, file) => {
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await api.post("/contabilita/pdp/fatture/importa", fd, { params: { centro_id: centroId, anno, mese, direzione }, headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${r.data.importate} fatture ${direzione} importate${r.data.duplicate ? `, ${r.data.duplicate} già presenti` : ""}`); load(); onChanged();
    } catch (e) { toast.error(apiError(e)); }
  };
  const svuota = async (direzione) => { try { await api.delete("/contabilita/pdp/fatture", { params: { centro_id: centroId, anno, mese, direzione } }); load(); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  const del = async (id) => { try { await api.delete(`/contabilita/pdp/fatture/${id}`); load(); onChanged(); } catch (e) { toast.error(apiError(e)); } };
  const t = d.totali;
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="fatture-ade">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Fatture Agenzia Entrate — {String(mese).padStart(2, "0")}/{anno}</h3>
          <p className="text-xs text-slate-500">Carica l'esportazione (CSV/XLSX, "Esporta tabella" da Fatture e Corrispettivi). Le note di credito vengono sottratte. Entrano nel punto di pareggio come "Fatture emesse" (entrate) e "Fatture ricevute" (fornitori).</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <UploadBtn label="Importa fatture emesse" onFile={(f) => upload("emesse", f)} testid="ade-upload-emesse" />
          <UploadBtn label="Importa fatture ricevute" onFile={(f) => upload("ricevute", f)} testid="ade-upload-ricevute" />
        </div>
      </div>
      <div className="grid gap-3 p-4 sm:grid-cols-2">
        {[["emesse", "Fatture emesse (entrate)", "text-emerald-700"], ["ricevute", "Fatture ricevute (fornitori)", "text-rose-700"]].map(([k, l, c]) => (
          <div key={k} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/60 px-3 py-2" data-testid={`ade-tot-${k}`}>
            <span className="text-sm text-slate-600">{l} <span className="text-xs text-slate-400">({t[`n_${k}`]} doc.)</span></span>
            <span className="flex items-center gap-2"><b className={`tabular-nums ${c}`}>{eur(t[k])}</b>{t[`n_${k}`] > 0 && <button onClick={() => svuota(k)} className="text-slate-300 hover:text-rose-600" title="Svuota" data-testid={`ade-svuota-${k}`}><Trash2 className="h-3.5 w-3.5" /></button>}</span>
          </div>
        ))}
      </div>
      {d.righe.length > 0 && (
        <div className="border-t border-slate-100">
          <button onClick={() => setAperto(!aperto)} className="flex w-full items-center justify-between px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50" data-testid="ade-toggle-lista">Dettaglio documenti ({d.righe.length}) {aperto ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</button>
          {aperto && (
            <div className="max-h-80 overflow-auto"><table className="w-full text-xs" data-testid="ade-table">
              <thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-1.5 text-left">Dir.</th><th className="px-3 py-1.5 text-left">Data</th><th className="px-3 py-1.5 text-left">Tipo</th><th className="px-3 py-1.5 text-left">Numero</th><th className="px-3 py-1.5 text-left">Controparte</th><th className="px-3 py-1.5 text-right">Imponibile</th><th className="px-3 py-1.5 text-right">IVA</th><th className="px-3 py-1.5 text-right">Totale</th><th /></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {d.righe.map((r) => (
                  <tr key={r.id} data-testid={`ade-row-${r.id}`}>
                    <td className="px-3 py-1"><span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${r.direzione === "emesse" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{r.direzione === "emesse" ? "E" : "R"}</span></td>
                    <td className="px-3 py-1 text-slate-500">{r.data ? r.data.split("-").reverse().join("/") : ""}</td><td className="px-3 py-1">{r.tipo}</td><td className="px-3 py-1">{r.numero}</td><td className="px-3 py-1 truncate max-w-[220px]">{r.controparte}</td>
                    <td className="px-3 py-1 text-right tabular-nums">{eur(r.imponibile)}</td><td className="px-3 py-1 text-right tabular-nums">{eur(r.imposta)}</td><td className="px-3 py-1 text-right font-medium tabular-nums">{eur(r.totale)}</td>
                    <td className="px-2 py-1 text-right"><button onClick={() => del(r.id)} className="text-slate-300 hover:text-rose-600" data-testid={`ade-del-${r.id}`}><Trash2 className="h-3.5 w-3.5" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>
      )}
    </div>
  );
};
