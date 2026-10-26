import { useEffect, useState } from "react";
import api from "../../lib/api";
import { eur } from "./IncentiviCalcolo";

export const IncentiviStorico = () => {
  const [righe, setRighe] = useState(null);
  useEffect(() => { api.get("/incentivi/storico").then((r) => setRighe(r.data)).catch(() => setRighe([])); }, []);
  if (!righe) return <p className="text-sm text-slate-500">Caricamento…</p>;
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm" data-testid="inc-storico">
        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-3 py-2">Mese</th><th className="px-3 py-2">Stato</th><th className="px-3 py-2 text-right">Fondo</th><th className="px-3 py-2 text-right">Premi</th><th className="px-3 py-2">Approvato</th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          {righe.map((r) => <tr key={r.mese} data-testid={`inc-storico-${r.mese}`}><td className="px-3 py-2 font-medium">{r.mese}</td><td className="px-3 py-2">{r.chiuso ? <span className="rounded bg-slate-900 px-2 py-0.5 text-xs text-white">chiuso</span> : <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">aperto</span>}</td><td className="px-3 py-2 text-right">{eur(r.fondo)}</td><td className="px-3 py-2 text-right">{eur(r.premi)}</td><td className="px-3 py-2 text-xs text-slate-500">{r.chiuso ? `${r.approvato_da} · ${(r.at || "").slice(0, 10)}` : "—"}</td></tr>)}
          {!righe.length && <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-400">Nessun mese con provvigioni caricate</td></tr>}
        </tbody>
      </table>
    </div>
  );
};
