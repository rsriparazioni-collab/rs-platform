import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileUp, ShieldCheck, Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { eur } from "./shared";

export const CorrispettiviAde = ({ storeId, anno, mese, confronto, stores, reload, isAdmin }) => {
  const ref = useRef();
  const [daAssegnare, setDaAssegnare] = useState([]);
  const [matricole, setMatricole] = useState([]);
  useEffect(() => { api.get("/contabilita/corrispettivi-ade/matricole").then((r) => setMatricole(r.data)).catch(() => {}); }, [storeId]);

  const upload = async (file) => {
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await api.post("/contabilita/corrispettivi-ade/importa", fd, { params: { store_id: storeId }, headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${r.data.importate} chiusure importate${r.data.aggiornate ? `, ${r.data.aggiornate} aggiornate` : ""} (${r.data.giorni} giorni)`);
      setDaAssegnare(r.data.matricole_da_assegnare || []); reload();
    } catch (e) { toast.error(apiError(e)); }
  };
  const assegna = async (matricola, sid) => {
    try { await api.put("/contabilita/corrispettivi-ade/matricole", { matricola, store_id: sid }); toast.success("Matricola assegnata"); setDaAssegnare((l) => l.filter((m) => m !== matricola)); reload(); const r = await api.get("/contabilita/corrispettivi-ade/matricole"); setMatricole(r.data); }
    catch (e) { toast.error(apiError(e)); }
  };
  const svuota = async () => { try { await api.delete("/contabilita/corrispettivi-ade", { params: { store_id: storeId, anno, mese } }); reload(); } catch (e) { toast.error(apiError(e)); } };

  const c = confronto || {};
  const ok = c.presente && Math.abs(c.diff || 0) < 0.01 && !(c.giorni_diff || []).length;
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="corrispettivi-ade">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-slate-900"><ShieldCheck className="h-4 w-4 text-indigo-600" /> Verifica con i corrispettivi telematici (Agenzia Entrate)</h3>
          <p className="text-xs text-slate-500">Carica l'esportazione da Fatture e Corrispettivi → Corrispettivi (CSV/XLSX della consultazione oppure ZIP/XML del download massivo). Le chiusure vengono abbinate al negozio tramite la matricola del registratore e confrontate con gli scontrini inseriti (Riparazioni + Merce + Art. 74).</p>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <input ref={ref} type="file" accept=".csv,.xlsx,.txt,.zip,.xml" className="hidden" onChange={(e) => { if (e.target.files[0]) upload(e.target.files[0]); e.target.value = ""; }} data-testid="ade-corr-upload-input" />
            <Button size="sm" variant="outline" onClick={() => ref.current.click()} data-testid="ade-corr-upload"><FileUp className="mr-1 h-4 w-4" /> Importa corrispettivi AdE</Button>
            {c.presente && <Button size="sm" variant="ghost" onClick={svuota} title="Elimina i dati AdE di questo mese" data-testid="ade-corr-svuota"><Trash2 className="h-4 w-4 text-slate-400" /></Button>}
          </div>
        )}
      </div>
      {daAssegnare.length > 0 && (
        <div className="space-y-2 border-b border-amber-100 bg-amber-50 px-4 py-3" data-testid="ade-corr-matricole">
          <p className="text-xs font-medium text-amber-800">Nuove matricole trovate: indica a quale negozio appartengono.</p>
          {daAssegnare.map((m) => (
            <div key={m} className="flex items-center gap-2 text-sm"><code className="rounded bg-white px-2 py-0.5 text-xs">{m}</code>
              <select className="h-8 rounded border border-slate-300 px-2 text-sm" defaultValue="" onChange={(e) => e.target.value && assegna(m, e.target.value)} data-testid={`ade-corr-matricola-${m}`}>
                <option value="">Scegli negozio…</option>{stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}
      <div className="px-4 py-3">
        {!c.presente ? (
          <p className="text-sm text-slate-500" data-testid="ade-corr-vuoto">Nessun corrispettivo telematico caricato per questo mese.{matricole.length ? ` Matricole note: ${matricole.map((m) => `${m.matricola} → ${m.store_nome}`).join(", ")}.` : ""}</p>
        ) : (
          <div className="space-y-2">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-slate-50 px-3 py-2"><p className="text-xs text-slate-500">Trasmesso all'AdE ({c.giorni_ade} chiusure)</p><p className="font-semibold tabular-nums" data-testid="ade-corr-tot-ade">{eur(c.tot_ade)}</p></div>
              <div className="rounded-lg bg-slate-50 px-3 py-2"><p className="text-xs text-slate-500">Scontrini inseriti negli stessi giorni{c.periodo?.[0] ? ` (${c.periodo[0].slice(8)}/${c.periodo[0].slice(5, 7)} → ${c.periodo[1].slice(8)}/${c.periodo[1].slice(5, 7)})` : ""}</p><p className="font-semibold tabular-nums" data-testid="ade-corr-tot-man">{eur(c.tot_scontrini_periodo)}</p></div>
              <div className={`rounded-lg px-3 py-2 ${ok ? "bg-emerald-50" : "bg-rose-50"}`}><p className="text-xs text-slate-500">Differenza</p><p className={`font-semibold tabular-nums ${ok ? "text-emerald-700" : "text-rose-700"}`} data-testid="ade-corr-diff">{ok ? "Coincidono ✓" : eur(c.diff)}</p></div>
            </div>
            {(c.giorni_diff || []).length > 0 && (
              <ul className="divide-y divide-slate-100 rounded-lg border border-rose-100 text-xs" data-testid="ade-corr-giorni-diff">
                {c.giorni_diff.map((g) => (
                  <li key={g.data} className="flex items-center justify-between px-3 py-1.5">
                    <span className="font-medium">{g.data.slice(8)}/{g.data.slice(5, 7)}</span>
                    <span className="text-slate-600">inserito {eur(g.scontrini)} · AdE {g.ade == null ? "—" : eur(g.ade)}</span>
                    <span className={`font-semibold tabular-nums ${g.diff == null ? "text-amber-700" : "text-rose-700"}`}>{g.diff == null ? "manca chiusura AdE" : `${g.diff > 0 ? "+" : ""}${eur(g.diff)}`}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
