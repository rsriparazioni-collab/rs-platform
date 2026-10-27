import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import api from "../../lib/api";

const fmt = (iso) => iso.split("-").reverse().slice(0, 2).join("/");

export const StoricoSettimanale = () => {
  const [data, setData] = useState(null);
  const [settimane, setSettimane] = useState(8);
  useEffect(() => { api.get("/lavorazioni/storico-settimanale", { params: { settimane } }).then((r) => setData(r.data)).catch(() => {}); }, [settimane]);
  if (!data) return null;
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3" data-testid="storico-settimanale">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-slate-800"><BarChart3 className="h-4 w-4 text-emerald-600" /> Pratiche chiuse per settimana</h2>
        <select value={settimane} onChange={(e) => setSettimane(Number(e.target.value))} className="h-8 rounded-md border border-slate-200 px-2 text-sm" data-testid="storico-settimane">
          {[4, 8, 12, 26].map((n) => <option key={n} value={n}>{n} settimane</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-2 py-1.5 text-left">Settimana</th>
              {data.negozi.map((n) => <th key={n} className="px-2 py-1.5">{n}</th>)}
              <th className="px-2 py-1.5 text-emerald-700">Totale</th>
              <th className="px-2 py-1.5 text-left">Chi</th>
            </tr>
          </thead>
          <tbody>
            {data.settimane.map((s) => (
              <tr key={s.settimana} className="border-t border-slate-100" data-testid={`storico-row-${s.settimana}`}>
                <td className="px-2 py-1.5 font-mono text-xs text-slate-600">{fmt(s.settimana)} – {fmt(s.fine)}</td>
                {data.negozi.map((n) => <td key={n} className={`px-2 py-1.5 text-center ${s.negozi[n] ? "font-semibold text-slate-800" : "text-slate-300"}`}>{s.negozi[n] || 0}</td>)}
                <td className={`px-2 py-1.5 text-center font-bold ${s.totale ? "text-emerald-700" : "text-slate-300"}`}>{s.totale}</td>
                <td className="px-2 py-1.5 text-xs text-slate-500">{Object.entries(s.operatori).map(([o, n]) => `${o} ${n}`).join(" · ") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
