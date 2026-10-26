import { useEffect, useState } from "react";
import { Trophy } from "lucide-react";
import api from "../../lib/api";
import { eur } from "./IncentiviCalcolo";

export const IncentiviMio = () => {
  const [d, setD] = useState(null);
  const [mese, setMese] = useState(() => { const o = new Date(); return `${o.getFullYear()}-${String(o.getMonth() + 1).padStart(2, "0")}`; });
  useEffect(() => { api.get(`/incentivi/mio?mese=${mese}`).then((r) => setD(r.data)).catch(() => setD(null)); }, [mese]);
  if (!d) return null;
  const m = d.mio;
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-4" data-testid="inc-mio">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold text-slate-900"><Trophy className="h-5 w-5 text-amber-500" /> I miei incentivi {d.chiuso && <span className="rounded bg-slate-900 px-2 py-0.5 text-xs text-white">confermato</span>}</h3>
        <input type="month" value={mese} onChange={(e) => setMese(e.target.value)} className="h-8 rounded-md border border-slate-200 px-2 text-sm" data-testid="inc-mio-mese" />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-xs uppercase text-slate-500">Classifica del mese</p>
          <ol className="mt-1 space-y-1 text-sm">{d.classifica.map((c) => <li key={c.nome} className={`flex justify-between rounded px-2 py-1 ${c.io ? "bg-white font-semibold" : ""}`} data-testid={`inc-mio-pos-${c.posizione}`}><span>{c.posizione}{c.ex_aequo ? "=" : ""}. {c.nome}{c.io ? " (io)" : ""}</span><span className="text-xs text-slate-500">{c.negozio}</span></li>)}</ol>
        </div>
        {m && <div className="text-sm">
          <p className="text-xs uppercase text-slate-500">I miei numeri</p>
          <p className="mt-1 text-2xl font-bold">{m.posizione}º posto · valore {m.valore.toLocaleString("it-IT")}</p>
          <p className="text-slate-600">EOLO {m.eolo_n} · energia {m.energia_n} · riparazioni {m.riparazioni_n} ({eur(m.riparazioni_margine)} margine) · SIM {m.sim_nuova}/{m.sim_mnp} · fisso {m.fisso}</p>
          <p className="mt-2">Gettoni: {m.gettoni_n} × 25 € = <b>{eur(m.gettoni_lordo)}</b> lordi</p>
          <p>Premio classifica ({m.premio_pct}% del fondo): <b>{eur(m.premio_lordo)}</b> lordi</p>
          <p className="mt-1 text-lg font-semibold text-emerald-700" data-testid="inc-mio-totale">Totale stimato lordo: {eur(m.totale_lordo)}</p>
          <p className="text-xs text-slate-500">{d.chiuso ? "Importo confermato dall'amministrazione." : "Stima: diventa definitiva con la chiusura del mese."}</p>
        </div>}
      </div>
    </div>
  );
};
