import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { eur } from "./shared";
import { Badge } from "./IvaDashboard";

const Cell = ({ v, nd, cls = "" }) => <td className={`px-2 py-1.5 text-right tabular-nums ${cls}`}>{nd ? <span className="text-[10px] text-rose-700">n.d.</span> : v == null ? "—" : eur(v)}</td>;

export const PdpNegozi = ({ anno, mese, isAdmin }) => {
  const [d, setD] = useState(null);
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => api.get("/contabilita/fiscale/negozi", { params: { anno, mese } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); }, [load]);
  if (!d) return null;
  const salva = async () => { try { await api.put("/contabilita/fiscale/obiettivi", { store_id: edit.store_id, obiettivo_mese: parseFloat(edit.obiettivo_mese) || 0, obiettivo_anno: parseFloat(edit.obiettivo_anno) || 0 }, { params: { anno } }); setEdit(null); toast.success("Obiettivo salvato"); load(); } catch (e) { toast.error(apiError(e)); } };
  const az = d.azienda;
  const righe = [...d.negozi, { ...az, store_id: "azienda", store_nome: "AZIENDA (tutti i negozi)", centro: "", netti_certezza: az.netti_determinabili ? "certo" : "incompleto", ricavi_netti: az.ricavi_netti, obiettivo_mese: az.obiettivo, ytd_lordo: az.ytd, tot: true }];
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="pdp-negozi">
      <div className="border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-900">Punto di pareggio per negozio e azienda</h3>
        <p className="text-xs text-slate-500">Ricavi netti IVA solo quando l'RT AdE copre tutto il mese (altrimenti n.d. e si usa il lordo). Costi fissi/fornitori del centro ripartiti pro quota sui ricavi lordi. Previsione annuale = andamento YTD proiettato su 12 mesi.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" data-testid="pdp-negozi-table">
          <thead className="bg-slate-50 text-slate-500"><tr><th className="px-2 py-1.5 text-left">Negozio</th><th className="px-2 py-1.5 text-left">Netti IVA</th><th className="px-2 py-1.5 text-right">Ricavi lordi</th><th className="px-2 py-1.5 text-right">Ricavi netti</th><th className="px-2 py-1.5 text-right">Costi fissi</th><th className="px-2 py-1.5 text-right">Variabili</th><th className="px-2 py-1.5 text-right">MDC</th><th className="px-2 py-1.5 text-right">BEP</th><th className="px-2 py-1.5 text-right">Risultato</th><th className="px-2 py-1.5 text-right">Obiettivo mese</th><th className="px-2 py-1.5 text-right">Scostamento</th><th className="px-2 py-1.5 text-right">YTD</th><th className="px-2 py-1.5 text-right">Previsione anno</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {righe.map((r) => (
              <tr key={r.store_id} className={r.tot ? "bg-indigo-50/60 font-semibold" : ""} data-testid={`pdp-negozio-${r.store_id}`}>
                <td className="px-2 py-1.5">{r.store_nome}{r.centro && <span className="ml-1 text-[10px] text-slate-400">{r.centro}{r.fissi_ripartiti ? ` · ${r.quota_pct}%` : ""}</span>}</td>
                <td className="px-2 py-1.5"><Badge certezza={r.netti_certezza} />{r.copertura_rt && <span className="ml-1 text-[10px] text-slate-400">RT {r.copertura_rt}</span>}</td>
                <Cell v={r.ricavi_lordi} /><Cell v={r.ricavi_netti} nd={r.ricavi_netti == null} /><Cell v={r.costi_fissi} /><Cell v={r.costi_variabili} />
                <Cell v={r.mdc} cls={r.mdc_pct != null ? "" : ""} /><Cell v={r.bep} /><Cell v={r.risultato} cls={r.risultato >= 0 ? "text-emerald-700" : "text-rose-700"} />
                <td className="px-2 py-1.5 text-right tabular-nums">{r.tot ? eur(r.obiettivo_mese) : isAdmin ? <button className="underline decoration-dotted" onClick={() => setEdit({ store_id: r.store_id, obiettivo_mese: r.obiettivo_mese || "", obiettivo_anno: r.obiettivo_anno || "" })} data-testid={`pdp-obiettivo-edit-${r.store_id}`}>{r.obiettivo_mese ? eur(r.obiettivo_mese) : "imposta"}</button> : eur(r.obiettivo_mese)}</td>
                <Cell v={r.scostamento} cls={r.scostamento >= 0 ? "text-emerald-700" : "text-rose-700"} /><Cell v={r.ytd_lordo} /><Cell v={r.previsione_anno} />
              </tr>))}
          </tbody>
        </table>
      </div>
      {edit && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50 px-4 py-2 text-xs" data-testid="pdp-obiettivo-form">
          <span>Obiettivo {anno}:</span>
          <input type="number" placeholder="€ al mese" value={edit.obiettivo_mese} onChange={(e) => setEdit({ ...edit, obiettivo_mese: e.target.value })} className="h-7 w-32 rounded border border-slate-300 px-2" data-testid="pdp-obiettivo-mese" />
          <input type="number" placeholder="€ anno" value={edit.obiettivo_anno} onChange={(e) => setEdit({ ...edit, obiettivo_anno: e.target.value })} className="h-7 w-32 rounded border border-slate-300 px-2" data-testid="pdp-obiettivo-anno" />
          <Button size="sm" className="h-7 text-xs" onClick={salva} data-testid="pdp-obiettivo-salva">Salva</Button><button className="text-slate-500" onClick={() => setEdit(null)}>annulla</button>
        </div>)}
    </div>
  );
};
