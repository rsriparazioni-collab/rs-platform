import { useCallback, useEffect, useState } from "react";
import { FileDown, Lock, Unlock } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../../lib/api";
import { Button } from "../ui/button";

export const eur = (v) => `${(v || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;

export const Kpi = ({ label, value, sub, testid, tone = "" }) => (
  <div className={`rounded-xl border border-slate-200 bg-white p-4 ${tone}`} data-testid={testid}>
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
  </div>
);

export const ClassificaTable = ({ classifica, mostraEuro = true }) => (
  <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
    <table className="w-full text-sm" data-testid="inc-classifica">
      <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
        <tr><th className="px-3 py-2">#</th><th className="px-3 py-2">Persona</th><th className="px-3 py-2">Negozio</th><th className="px-3 py-2 text-right">Valore</th>
          <th className="px-3 py-2 text-right">EOLO</th><th className="px-3 py-2 text-right">Energia</th><th className="px-3 py-2 text-right">Riparazioni</th><th className="px-3 py-2 text-right">SIM n/MNP</th><th className="px-3 py-2 text-right">Fisso</th>
          {mostraEuro && <><th className="px-3 py-2 text-right">Gettoni</th><th className="px-3 py-2 text-right">Premio</th><th className="px-3 py-2 text-right">Totale lordo</th><th className="px-3 py-2 text-right">Costo azienda</th></>}</tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {classifica.map((c) => (
          <tr key={c.user_id} data-testid={`inc-classifica-row-${c.user_id}`} className={c.posizione === 1 ? "bg-amber-50/60" : ""}>
            <td className="px-3 py-2 font-bold">{c.posizione}{c.ex_aequo ? "=" : ""}</td>
            <td className="px-3 py-2 font-medium text-slate-900">{c.nome}</td>
            <td className="px-3 py-2 text-slate-500">{c.negozio} <span className="text-xs">({c.entita})</span></td>
            <td className="px-3 py-2 text-right font-semibold">{c.valore.toLocaleString("it-IT")}</td>
            <td className="px-3 py-2 text-right">{c.eolo_n} <span className="text-xs text-slate-400">{eur(c.eolo_importo)}</span></td>
            <td className="px-3 py-2 text-right">{c.energia_n} <span className="text-xs text-slate-400">{eur(c.energia_importo)}</span></td>
            <td className="px-3 py-2 text-right">{c.riparazioni_n} <span className="text-xs text-slate-400">{eur(c.riparazioni_margine)}</span></td>
            <td className="px-3 py-2 text-right">{c.sim_nuova}/{c.sim_mnp}</td>
            <td className="px-3 py-2 text-right">{c.fisso}</td>
            {mostraEuro && <>
              <td className="px-3 py-2 text-right">{c.gettoni_n} · {eur(c.gettoni_lordo)}</td>
              <td className="px-3 py-2 text-right">{c.premio_pct}% · <b>{eur(c.premio_lordo)}</b></td>
              <td className="px-3 py-2 text-right font-semibold">{eur(c.totale_lordo)}</td>
              <td className="px-3 py-2 text-right text-slate-500">{eur(c.costo_azienda)}</td></>}
          </tr>
        ))}
        {!classifica.length && <tr><td colSpan={13} className="px-3 py-6 text-center text-slate-400">Nessun partecipante configurato</td></tr>}
      </tbody>
    </table>
  </div>
);

export const FondoPanel = ({ d }) => (
  <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
    <Kpi label="EOLO gruppo" value={eur(d.fondo.eolo_gruppo_lordo)} sub="Morbegno + Gravedona confermato" testid="inc-kpi-eolo" />
    <Kpi label="Energia gruppo" value={eur(d.fondo.energia_gruppo_lordo)} sub="copre i gettoni, non va a fondo" testid="inc-kpi-energia" />
    <Kpi label="Fondo disponibile" value={eur(d.fondo.fondo_disponibile)} sub={`${d.fondo.fondo_pct}% EOLO dopo gettoni`} testid="inc-kpi-fondo" tone="border-emerald-200 bg-emerald-50/40" />
    <Kpi label="Premi assegnati" value={eur(d.fondo.premi_assegnati)} sub={`residuo ${eur(d.fondo.residuo)}`} testid="inc-kpi-premi" />
    <Kpi label="Gettoni" value={`${d.costi.gettoni_n} · ${eur(d.costi.gettoni_lordi)}`} sub="25 € lordi a contratto" testid="inc-kpi-gettoni" />
    <Kpi label="Risultato azienda" value={eur(d.costi.risultato_azienda)} sub={`costo datore ${eur(d.costi.costo_datore_totale)} · trattenute ${eur(d.costi.trattenute_esterni)}`} testid="inc-kpi-risultato" tone={d.costi.risultato_azienda < 0 ? "border-red-200 bg-red-50/40" : ""} />
  </div>
);

export const IncentiviCalcolo = ({ mese }) => {
  const [d, setD] = useState(null);
  useEffect(() => {
    let attivo = true;
    api.get(`/incentivi/calcolo?mese=${mese}`).then((r) => { if (attivo) setD(r.data); }).catch((e) => toast.error(apiError(e)));
    return () => { attivo = false; };
  }, [mese]);
  const load = useCallback(() => api.get(`/incentivi/calcolo?mese=${mese}`).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [mese]);
  const chiudi = async () => {
    if (!window.confirm(`Chiudere ${mese} e confermare i premi? Il calcolo viene congelato (riapribile).`)) return;
    try { await api.post(`/incentivi/chiusura/${mese}`); toast.success("Mese chiuso e premi confermati"); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const riapri = async () => { try { await api.delete(`/incentivi/chiusura/${mese}`); toast.success("Mese riaperto"); load(); } catch (e) { toast.error(apiError(e)); } };
  if (!d) return <p className="text-sm text-slate-500">Calcolo…</p>;
  return (
    <div className="space-y-4" data-testid="inc-calcolo">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600">{d.n_provvigioni} provvigioni caricate per {mese}{d.chiuso && <span className="ml-2 rounded bg-slate-900 px-2 py-0.5 text-xs text-white">CHIUSO da {d.chiusura?.approvato_da}</span>}</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="gap-1" onClick={() => downloadBlob(`/incentivi/export?mese=${mese}`, `incentivi_${mese}.xlsx`)} data-testid="inc-export"><FileDown className="h-4 w-4" /> Excel</Button>
          {d.chiuso ? <Button variant="outline" size="sm" className="gap-1" onClick={riapri} data-testid="inc-riapri"><Unlock className="h-4 w-4" /> Riapri mese</Button>
            : <Button size="sm" className="gap-1" onClick={chiudi} data-testid="inc-chiudi"><Lock className="h-4 w-4" /> Chiudi mese e conferma premi</Button>}
        </div>
      </div>
      <FondoPanel d={d} />
      <ClassificaTable classifica={d.classifica} />
      {!!d.anomalie.length && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm" data-testid="inc-anomalie">
        <b>Anomalie ({d.anomalie.length})</b>: {d.anomalie.map((a, i) => <span key={i} className="mr-3">{a.tipo} – {a.descrizione} ({eur(a.importo)})</span>)}</div>}
      <p className="text-xs text-slate-400">Premi per società: {Object.entries(d.costi.premi_per_entita).map(([k, v]) => `${k} ${eur(v)}`).join(" · ") || "—"} · Fondo per società: {Object.entries(d.fondo.per_entita).map(([k, v]) => `${k} ${eur(v)}`).join(" · ") || "—"}</p>
    </div>
  );
};
