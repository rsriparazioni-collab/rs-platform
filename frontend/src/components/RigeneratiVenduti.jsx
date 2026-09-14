import { useEffect, useState } from "react";
import { BadgeEuro, ChevronDown, ChevronUp } from "lucide-react";
import api from "../lib/api";
import { fmtDate } from "../lib/constants";

export default function RigeneratiVenduti({ canSeeAll }) {
  const [data, setData] = useState({ vendite: [], totale_margine: 0, totale_vendite: 0 });
  const [open, setOpen] = useState(true);

  useEffect(() => { api.get("/rigenerati/venduti").then((r) => setData(r.data)).catch(() => {}); }, []);

  return (
    <div className="overflow-hidden rounded-xl border border-violet-200 bg-white shadow-sm" data-testid="rigenerati-venduti-panel">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-5 py-3 text-left" data-testid="rigenerati-venduti-toggle">
        <div className="flex items-center gap-2">
          <BadgeEuro className="h-4 w-4 text-violet-700" />
          <span className="font-heading text-base font-semibold text-slate-900">Rigenerati venduti</span>
          <span className="text-xs text-slate-500">{data.vendite.length} vendite</span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-600">Incasso € {data.totale_vendite.toFixed(2)}</span>
          <span className="font-bold text-violet-800" data-testid="rigenerati-margine-totale">Margine € {data.totale_margine.toFixed(2)}</span>
          {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
        </div>
      </button>
      {open && (
        <table className="w-full border-t border-slate-100 text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-5 py-2">Data</th><th className="px-5 py-2">Dispositivo</th><th className="px-5 py-2">Ritiro / Rip.</th>
              {canSeeAll && <th className="px-5 py-2">Negozio</th>}<th className="px-5 py-2">Costo</th><th className="px-5 py-2">Venduto</th><th className="px-5 py-2">Margine</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.vendite.map((v, i) => (
              <tr key={v.id} data-testid={`rigenerato-venduto-${i}`}>
                <td className="px-5 py-2 text-slate-600">{fmtDate(v.venduto_at)}</td>
                <td className="px-5 py-2 font-medium text-slate-900">{v.nome}{v.imei ? <span className="block text-xs text-slate-400">IMEI {v.imei}</span> : null}</td>
                <td className="px-5 py-2 text-xs text-slate-600">{v.ritiro_numero || "-"}{v.riparazione_numero ? ` / ${v.riparazione_numero}` : ""}</td>
                {canSeeAll && <td className="px-5 py-2 text-slate-600">{v.store_name}</td>}
                <td className="px-5 py-2 text-slate-600">€ {v.costo.toFixed(2)}</td>
                <td className="px-5 py-2 text-slate-800">€ {v.prezzo_vendita.toFixed(2)}</td>
                <td className={`px-5 py-2 font-bold ${v.margine < 0 ? "text-rose-700" : "text-violet-800"}`}>€ {v.margine.toFixed(2)}</td>
              </tr>
            ))}
            {data.vendite.length === 0 && <tr><td colSpan={7} className="px-5 py-6 text-center text-xs text-slate-500" data-testid="rigenerati-venduti-empty">Nessun rigenerato venduto: usa "Venduto" sulla riga di un dispositivo rigenerato.</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}
