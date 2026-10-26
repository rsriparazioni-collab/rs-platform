import { useState } from "react";
import { Play, Plus, X } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { eur, ClassificaTable, FondoPanel } from "./IncentiviCalcolo";

const CAMPI = [["gettone_lordo", "Gettone lordo €"], ["eolo_fondo_pct", "% EOLO al fondo"], ["costo_datore_fattore", "Fattore costo datore"], ["coef_riparazione", "Coeff. riparazioni %"], ["coef_eolo", "Coeff. EOLO %"], ["coef_energia", "Coeff. energia %"], ["valore_sim_nuova", "Valore SIM nuova €"], ["valore_sim_mnp", "Valore SIM MNP €"], ["valore_fisso", "Valore fisso €"], ["tetto_fondo", "Tetto fondo € (0 = nessuno)"]];

export const IncentiviSimulazione = ({ mese, cfg }) => {
  const [scenari, setScenari] = useState([{ nome: "Scenario A", p: Object.fromEntries(CAMPI.map(([k]) => [k, cfg[k]])), premi: cfg.premi_pct.join("/") }]);
  const [risultati, setRisultati] = useState([]);
  const [meseSim, setMeseSim] = useState(mese);

  const run = async () => {
    try {
      const res = await Promise.all(scenari.map((s) => api.get(`/incentivi/calcolo?mese=${meseSim}&override=${encodeURIComponent(JSON.stringify({ ...Object.fromEntries(Object.entries(s.p).map(([k, v]) => [k, parseFloat(v) || 0])), premi_pct: s.premi.split("/").map((x) => parseFloat(x) || 0) }))}`)));
      setRisultati(res.map((r) => r.data)); toast.success("Simulazione eseguita (nessun dato salvato)");
    } catch (e) { toast.error(apiError(e)); }
  };
  const upd = (i, k, v) => setScenari(scenari.map((s, j) => (j === i ? { ...s, p: { ...s.p, [k]: v } } : s)));

  return (
    <div className="space-y-4" data-testid="inc-simulazione">
      <p className="text-sm text-slate-600">Confronta più configurazioni sullo stesso mese già caricato. Nulla viene salvato: per adottare uno scenario, riporta i valori nella tab Regole.</p>
      <div className="flex items-center gap-2 text-sm"><span className="text-slate-500">Mese</span><input type="month" value={meseSim} onChange={(e) => setMeseSim(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2" data-testid="inc-sim-mese" />
        <Button size="sm" variant="outline" className="gap-1" onClick={() => setScenari([...scenari, { ...scenari[scenari.length - 1], nome: `Scenario ${String.fromCharCode(65 + scenari.length)}` }])} data-testid="inc-sim-add"><Plus className="h-4 w-4" /> Aggiungi scenario</Button>
        <Button size="sm" className="gap-1" onClick={run} data-testid="inc-sim-run"><Play className="h-4 w-4" /> Simula</Button></div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {scenari.map((s, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white p-3" data-testid={`inc-sim-scenario-${i}`}>
            <div className="flex items-center justify-between"><Input className="h-8 w-40 font-semibold" value={s.nome} onChange={(e) => setScenari(scenari.map((x, j) => (j === i ? { ...x, nome: e.target.value } : x)))} />{scenari.length > 1 && <button onClick={() => setScenari(scenari.filter((_, j) => j !== i))}><X className="h-4 w-4 text-slate-400" /></button>}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
              {CAMPI.map(([k, l]) => <label key={k} className="space-y-0.5"><span className="text-slate-500">{l}</span><Input type="number" step="0.5" className="h-8" value={s.p[k]} onChange={(e) => upd(i, k, e.target.value)} data-testid={`inc-sim-${i}-${k}`} /></label>)}
              <label className="space-y-0.5"><span className="text-slate-500">Premi % (1º/2º/3º…)</span><Input className="h-8" value={s.premi} onChange={(e) => setScenari(scenari.map((x, j) => (j === i ? { ...x, premi: e.target.value } : x)))} data-testid={`inc-sim-${i}-premi`} /></label>
            </div>
          </div>))}
      </div>
      {!!risultati.length && (
        <div className="space-y-6">
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm" data-testid="inc-sim-confronto">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-3 py-2">Scenario</th><th className="px-3 py-2 text-right">Fondo</th><th className="px-3 py-2 text-right">Premi</th><th className="px-3 py-2 text-right">Gettoni</th><th className="px-3 py-2 text-right">Costo datore</th><th className="px-3 py-2 text-right">Risultato azienda</th>{risultati[0].classifica.map((c) => <th key={c.user_id} className="px-3 py-2 text-right">{c.nome}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-100">
                {risultati.map((r, i) => <tr key={i}><td className="px-3 py-2 font-medium">{scenari[i].nome}</td><td className="px-3 py-2 text-right">{eur(r.fondo.fondo_disponibile)}</td><td className="px-3 py-2 text-right">{eur(r.fondo.premi_assegnati)}</td><td className="px-3 py-2 text-right">{eur(r.costi.gettoni_lordi)}</td><td className="px-3 py-2 text-right">{eur(r.costi.costo_datore_totale)}</td><td className={`px-3 py-2 text-right font-semibold ${r.costi.risultato_azienda < 0 ? "text-red-600" : "text-emerald-700"}`}>{eur(r.costi.risultato_azienda)}</td>
                  {risultati[0].classifica.map((c0) => { const c = r.classifica.find((x) => x.user_id === c0.user_id); return <td key={c0.user_id} className="px-3 py-2 text-right">{c ? `${c.posizione}º · ${eur(c.totale_lordo)}` : "—"}</td>; })}</tr>)}
              </tbody>
            </table>
          </div>
          {risultati.map((r, i) => <div key={i} className="space-y-2"><h4 className="font-semibold text-slate-800">{scenari[i].nome}</h4><FondoPanel d={r} /><ClassificaTable classifica={r.classifica} /></div>)}
        </div>)}
    </div>
  );
};
