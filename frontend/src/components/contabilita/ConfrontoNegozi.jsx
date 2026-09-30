import { Fragment, useEffect, useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { eur } from "./shared";

const COLORI = ["bg-sky-600", "bg-emerald-600", "bg-amber-500", "bg-rose-500", "bg-violet-600", "bg-teal-600"];

export const ConfrontoNegozi = ({ anno }) => {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/contabilita/report/confronto", { params: { anno } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))); }, [anno]);
  if (!d || d.negozi.length < 2) return null;
  const max = Math.max(1, ...d.negozi.flatMap((n) => n.mesi.map((m) => m.tot)));
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4" data-testid="confronto-negozi">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Confronto negozi {anno}</h3>
        <div className="flex flex-wrap gap-3 text-xs">{d.negozi.map((n, i) => <span key={n.id} className="inline-flex items-center gap-1.5"><span className={`h-2.5 w-2.5 rounded-sm ${COLORI[i % COLORI.length]}`} />{n.nome}</span>)}</div>
      </div>
      <div className="flex h-44 items-end gap-2">
        {d.mesi.map((nome, mi) => (
          <div key={nome} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full items-end justify-center gap-px" style={{ height: 150 }}>
              {d.negozi.map((n, i) => <div key={n.id} className={`flex-1 rounded-t ${COLORI[i % COLORI.length]}`} style={{ height: `${n.mesi[mi].tot / max * 100}%` }} title={`${n.nome} ${nome}: ${eur(n.mesi[mi].tot)}`} />)}
            </div>
            <span className="text-[10px] uppercase text-slate-500">{nome.slice(0, 3)}</span>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" data-testid="confronto-table">
          <thead className="text-slate-500"><tr><th className="px-2 py-1 text-left">Negozio</th>{d.mesi.map((m) => <th key={m} className="px-2 py-1 text-right">{m.slice(0, 3)}</th>)}<th className="px-2 py-1 text-right">Totale</th><th className="px-2 py-1 text-right">vs {anno - 1}</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {d.negozi.map((n, i) => (
              <Fragment key={n.id}>
                <tr data-testid={`confronto-row-${n.id}`}>
                  <td className="px-2 py-1.5 font-medium"><span className={`mr-1.5 inline-block h-2 w-2 rounded-sm ${COLORI[i % COLORI.length]}`} />{n.nome}</td>
                  {n.mesi.map((m) => <td key={m.mese} className="px-2 py-1.5 text-right tabular-nums">{m.tot ? eur(m.tot).replace("€ ", "") : ""}</td>)}
                  <td className="px-2 py-1.5 text-right font-semibold tabular-nums">{eur(n.tot)}</td>
                  <td className={`px-2 py-1.5 text-right ${n.pct == null ? "text-slate-300" : n.pct >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{n.pct == null ? "—" : `${n.pct > 0 ? "+" : ""}${n.pct.toFixed(1)}%`}</td>
                </tr>
                <tr className="bg-slate-50/60 text-[11px]" data-testid={`confronto-pdp-${n.id}`}>
                  <td className="px-2 py-1 pl-6 text-slate-500">Guadagno netto PDP</td>
                  {n.mesi.map((m) => <td key={m.mese} className={`px-2 py-1 text-right tabular-nums ${m.pdp_risultato == null ? "text-slate-300" : m.pdp_risultato >= 0 ? "text-emerald-700" : "text-rose-700"}`} title={m.pdp_uscite != null ? `Pareggio: ${eur(m.pdp_uscite)}` : "PDP non compilato"}>{m.pdp_risultato == null ? "·" : eur(m.pdp_risultato).replace("€ ", "")}</td>)}
                  <td className={`px-2 py-1 text-right font-semibold tabular-nums ${n.pdp_tot == null ? "text-slate-300" : n.pdp_tot >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{n.pdp_tot == null ? "—" : eur(n.pdp_tot)}</td>
                  <td />
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[11px] text-slate-400">Guadagno netto = entrate − uscite del Punto di pareggio del mese; "·" = PDP non ancora compilato per quel mese.</p>
      </div>
    </div>
  );
};
