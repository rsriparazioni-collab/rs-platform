import { useCallback, useEffect, useState } from "react";
import { FileDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { Button } from "./ui/button";

const MESI = ["", "Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];
const ym = (s) => `${MESI[parseInt(s.slice(5, 7))]} ${s.slice(2, 4)}`;
const Trend = ({ v }) => { if (v.length < 2) return null; const a = v[v.length - 2], b = v[v.length - 1]; if (a === b) return <span className="text-slate-400">=</span>; return <span className={b > a ? "text-emerald-600" : "text-rose-600"}>{b > a ? "▲" : "▼"} {a ? Math.round(((b - a) / a) * 100) : "—"}%</span>; };

const Tab = ({ titolo, righe, mesi, key = "label", testid }) => (
  <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid={testid}>
    <table className="w-full text-xs">
      <thead className="bg-slate-50 text-slate-500"><tr><th className="sticky left-0 bg-slate-50 px-3 py-2 text-left">{titolo}</th>{mesi.map((m) => <th key={m} className="px-2 py-2 text-right">{ym(m)}</th>)}<th className="px-2 py-2 text-right font-bold">Totale</th><th className="px-2 py-2 text-right">vs mese prec.</th></tr></thead>
      <tbody className="divide-y divide-slate-100">
        {righe.map((r) => (
          <tr key={r.id || r[key]} className="hover:bg-slate-50" data-testid={`${testid}-riga`}>
            <td className="sticky left-0 bg-white px-3 py-1.5 font-medium text-slate-800">{r[key] || r.nome}</td>
            {r.valori.map((v, i) => <td key={i} className={`px-2 py-1.5 text-right tabular-nums ${v ? "" : "text-slate-300"}`}>{v || "·"}</td>)}
            <td className="px-2 py-1.5 text-right font-bold tabular-nums">{r.totale}</td><td className="px-2 py-1.5 text-right"><Trend v={r.valori} /></td>
          </tr>))}
        {!righe.length && <tr><td colSpan={mesi.length + 3} className="px-3 py-3 text-slate-400">Nessun inserimento nel periodo</td></tr>}
      </tbody>
    </table>
  </div>
);

export const ReportInserimenti = () => {
  const [mesi, setMesi] = useState(12);
  const [storeId, setStoreId] = useState("");
  const [userId, setUserId] = useState("");
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/report/inserimenti", { params: { mesi, store_id: storeId, user_id: userId } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [mesi, storeId, userId]);
  useEffect(() => { load(); }, [load]);
  if (!d) return <p className="text-sm text-slate-500" data-testid="report-inserimenti-loading">Caricamento…</p>;
  const lav = d.lavorazioni.filter((l) => l.totale > 0);
  return (
    <div className="space-y-4" data-testid="report-inserimenti">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900 md:text-lg"><TrendingUp className="h-5 w-5" /> Andamento inserimenti mensili</h2>
        <span className="text-xs text-slate-500">Lavorazioni realmente inserite nel gestionale (riparazioni, vendite, SIM, internet, accessori, ritiri, contratti energia, nuovi clienti) per mese, negozio e persona.</span>
        <div className="ml-auto flex flex-wrap gap-2">
          <select value={mesi} onChange={(e) => setMesi(parseInt(e.target.value))} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="report-mesi">{[3, 6, 12, 24].map((n) => <option key={n} value={n}>Ultimi {n} mesi</option>)}</select>
          <select value={storeId} onChange={(e) => setStoreId(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="report-negozio"><option value="">Tutti i negozi</option>{d.filtri.stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}</select>
          <select value={userId} onChange={(e) => setUserId(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="report-persona"><option value="">Tutte le persone</option>{d.filtri.users.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</select>
          <Button variant="outline" size="sm" className="h-9 gap-1" onClick={() => downloadBlob(`/report/inserimenti/export?mesi=${mesi}&store_id=${storeId}&user_id=${userId}`, "inserimenti_mensili.xlsx")} data-testid="report-export"><FileDown className="h-4 w-4" /> Excel</Button>
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-3" data-testid="report-kpi">
        <div className="rounded-xl border border-slate-200 bg-white p-3"><p className="text-[11px] uppercase text-slate-500">Inserimenti ultimo mese</p><p className="text-2xl font-bold tabular-nums">{d.totale_mese[d.totale_mese.length - 1]}</p><Trend v={d.totale_mese} /></div>
        <div className="rounded-xl border border-slate-200 bg-white p-3"><p className="text-[11px] uppercase text-slate-500">Media mensile</p><p className="text-2xl font-bold tabular-nums">{Math.round(d.totale_mese.reduce((a, b) => a + b, 0) / d.totale_mese.length)}</p></div>
        <div className="rounded-xl border border-slate-200 bg-white p-3"><p className="text-[11px] uppercase text-slate-500">Totale periodo</p><p className="text-2xl font-bold tabular-nums">{d.totale_mese.reduce((a, b) => a + b, 0)}</p></div>
      </div>
      <Tab titolo="Lavorazione" righe={[...lav, { id: "tot", label: "TOTALE", valori: d.totale_mese, totale: d.totale_mese.reduce((a, b) => a + b, 0) }]} mesi={d.mesi} testid="report-lavorazioni" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Tab titolo="Negozio" righe={d.negozi} mesi={d.mesi} key="nome" testid="report-negozi" />
        <Tab titolo="Persona" righe={d.persone} mesi={d.mesi} key="nome" testid="report-persone" />
      </div>
    </div>
  );
};
