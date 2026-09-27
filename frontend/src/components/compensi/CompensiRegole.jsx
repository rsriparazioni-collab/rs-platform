import { useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { RegolaDialog } from "./RegolaDialog";
import { eur } from "./CompensiCalcolo";

export const CompensiRegole = ({ meta }) => {
  const [regole, setRegole] = useState([]);
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => api.get("/compensi/regole").then((r) => setRegole(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const nomeDest = (r) => {
    if (!r.destinatario_id) return r.destinatario_tipo === "store" ? "Tutti i negozi" : "Tutti gli operatori";
    const list = r.destinatario_tipo === "store" ? meta.stores : meta.users;
    return list.find((x) => x.id === r.destinatario_id)?.nome || list.find((x) => x.id === r.destinatario_id)?.name || "?";
  };
  const elimina = async (r) => {
    if (!window.confirm(`Eliminare la regola "${r.nome}"?`)) return;
    try { await api.delete(`/compensi/regole/${r.id}`); toast.success("Regola eliminata"); load(); } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Ogni regola vale per un periodo (da/a): per cambiare un importo nel tempo chiudi la vecchia regola e creane una nuova.</p>
        <Button onClick={() => setEdit({})} className="gap-1.5" data-testid="regola-nuova"><Plus className="h-4 w-4" /> Nuova regola</Button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-2">Regola</th><th className="px-3 py-2">Destinatario</th><th className="px-3 py-2">Voce / filtri</th><th className="px-3 py-2">Importo</th><th className="px-3 py-2">Soglia</th><th className="px-3 py-2">Pagamento</th><th className="px-3 py-2">Validità</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {regole.map((r) => (
              <tr key={r.id} className={r.attiva ? "" : "opacity-50"} data-testid={`regola-row-${r.id}`}>
                <td className="px-4 py-2 font-medium text-slate-900">{r.nome}{r.e_gara && <span className="status-badge ml-2 bg-amber-500/15 text-amber-700 border-amber-300">Gara</span>}{r.note && <p className="text-xs font-normal text-slate-400">{r.note}</p>}</td>
                <td className="px-3 py-2 text-slate-600">{nomeDest(r)}</td>
                <td className="px-3 py-2 text-slate-600">{meta.voci[r.voce]}{r.operatore_tel && <> · {r.operatore_tel}</>}{r.tipo_attivazione && <> · {r.tipo_attivazione.toUpperCase()}</>}
                  {r.provenienza_in?.length > 0 && <p className="text-xs text-slate-400">da: {r.provenienza_in.join(", ")}</p>}
                  {r.provenienza_not_in?.length > 0 && <p className="text-xs text-slate-400">non da: {r.provenienza_not_in.join(", ")}</p>}
                  {r.solo_incassato && <p className="text-xs text-slate-400">solo incassati</p>}</td>
                <td className="px-3 py-2 font-semibold">{eur(r.importo)}<span className="text-xs font-normal text-slate-400"> {r.modalita === "forfait" ? "forfait" : "/cad."}</span></td>
                <td className="px-3 py-2 text-slate-600">{r.soglia > 0 ? `≥${r.soglia}${r.conteggio_globale ? " globali" : ""}` : "-"}</td>
                <td className="px-3 py-2 text-slate-600">{r.mesi_pagamento > 0 ? `+${r.mesi_pagamento} mesi` : "nel mese"}</td>
                <td className="px-3 py-2 text-slate-600">{r.valido_da || "…"} → {r.valido_a || "…"}</td>
                <td className="px-3 py-2"><div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => setEdit(r)} data-testid={`regola-edit-${r.id}`}><Pencil className="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" onClick={() => elimina(r)} data-testid={`regola-del-${r.id}`}><Trash2 className="h-4 w-4 text-rose-600" /></Button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit !== null && <RegolaDialog meta={meta} regola={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
    </div>
  );
};
