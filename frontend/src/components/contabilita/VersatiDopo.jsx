import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Num, eur } from "./shared";

export const VersatiDopo = ({ storeId, anno, mese, versati, totali, reload }) => {
  const [f, setF] = useState({ data: new Date().toISOString().slice(0, 10), importo: "", note: "" });
  const add = async () => {
    if (!f.importo) return toast.error("Importo obbligatorio");
    try { await api.post(`/contabilita/corrispettivi/${storeId}/${anno}/${mese}/versati-dopo`, { ...f, importo: parseFloat(f.importo) }); setF({ ...f, importo: "", note: "" }); toast.success("Versamento registrato"); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const del = async (id) => { try { await api.delete(`/contabilita/corrispettivi/${storeId}/${anno}/${mese}/versati-dopo/${id}`); reload(); } catch (e) { toast.error(apiError(e)); } };
  const dv = totali.da_versare;
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="versati-dopo">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
        <h3 className="font-semibold text-slate-900">Versamenti dopo fine mese <span className="text-xs font-normal text-slate-500">(competenza {mese}/{anno})</span></h3>
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <span>Contanti {eur(totali.contanti)}</span><span>− Spese {eur(totali.spese_contanti)}</span><span>− Versati {eur(totali.versati_totale)}</span>
          <span className={`font-semibold ${Math.abs(dv) < 0.01 ? "text-emerald-700" : dv < 0 ? "text-rose-700" : "text-amber-700"}`} data-testid="versati-da-versare">= {Math.abs(dv) < 0.01 ? "tutto versato" : dv < 0 ? `Ammanco ${eur(dv)}` : `Da versare ${eur(dv)}`}</span>
        </div>
      </div>
      <div className="grid gap-2 border-b border-slate-100 p-4 sm:grid-cols-[150px_120px_1fr_auto]">
        <Input type="date" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} className="h-8" data-testid="versato-data" />
        <Num value={f.importo} onChange={(v) => setF({ ...f, importo: v })} testid="versato-importo" />
        <Input placeholder="Note (es. versamento banca)" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} className="h-8" data-testid="versato-note" />
        <Button size="sm" onClick={add} data-testid="versato-add">Aggiungi</Button>
      </div>
      <table className="w-full text-sm"><tbody className="divide-y divide-slate-100">
        {versati.map((v) => (
          <tr key={v.id} data-testid={`versato-row-${v.id}`}><td className="px-5 py-1.5 text-slate-500">{v.data.split("-").reverse().join("/")}</td><td className="px-3 py-1.5 text-right tabular-nums">{eur(v.importo)}</td><td className="px-3 py-1.5 text-slate-500">{v.note}</td>
            <td className="px-3 py-1.5 text-right"><button onClick={() => del(v.id)} className="text-slate-400 hover:text-rose-600" data-testid={`versato-del-${v.id}`}><Trash2 className="h-4 w-4" /></button></td></tr>
        ))}
        {!versati.length && <tr><td className="px-5 py-3 text-sm text-slate-400">Nessun versamento successivo registrato</td></tr>}
      </tbody></table>
    </div>
  );
};
