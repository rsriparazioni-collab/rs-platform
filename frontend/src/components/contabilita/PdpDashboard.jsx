import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import api from "../../lib/api";
import { eur } from "./shared";

const pct = (v) => (v == null ? "—" : `${Number(v).toFixed(1)}%`);

const Kpi = ({ label, value, sub, tone = "text-slate-900", testid }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid={testid}>
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`mt-1 text-xl font-semibold tabular-nums ${tone}`}>{value}</p>
    {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
  </div>
);

export const PdpDashboard = ({ centroId, anno, mese, fatturato, fissi, variabili, incasso, be }) => {
  const [trend, setTrend] = useState([]);
  useEffect(() => {
    if (!centroId) return;
    api.get("/contabilita/pdp/trend", { params: { centro_id: centroId, anno, mese, mesi: 6 } }).then((r) => setTrend(r.data)).catch(() => setTrend([]));
  }, [centroId, anno, mese]);

  const mdc = fatturato - variabili;
  const mdcPct = fatturato ? mdc / fatturato : 0;
  const bep = fatturato && mdc > 0 ? fissi / mdcPct : null;
  const uscite = fissi + variabili;
  const risultato = fatturato - uscite;
  const sicurezza = bep != null ? fatturato - bep : null;
  const giorniAp = be?.giorni_apertura_stimati || 26;
  const bepGiorno = bep != null ? bep / giorniAp : null;
  const copertura = bep ? Math.min(100, (fatturato / bep) * 100) : 0;
  const maxTrend = Math.max(1, ...trend.flatMap((t) => [t.fatturato, t.uscite, t.bep || 0]));

  return (
    <div className="space-y-4" data-testid="pdp-dashboard">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Fatturato (scontrini + fatture)" value={eur(fatturato)} sub={`IVA scorporata stimata ${eur(incasso?.iva)}`} tone="text-emerald-700" testid="pdp-kpi-fatturato" />
        <Kpi label="Incassato reale" value={eur(incasso?.incassato)} sub={`contanti ${eur(incasso?.contanti)} · POS ${eur(incasso?.pos)}${incasso?.non_riscosso ? ` · non riscosso ${eur(incasso.non_riscosso)}` : ""}`} tone="text-sky-700" testid="pdp-kpi-incassato" />
        <Kpi label="Spese totali" value={eur(uscite)} sub={`fisse ${eur(fissi)} · variabili ${eur(variabili)}`} tone="text-rose-700" testid="pdp-kpi-spese" />
        <Kpi label={risultato >= 0 ? "Utile del mese" : "Perdita del mese"} value={eur(risultato)} sub={be?.in_corso ? `proiezione fine mese ${eur(be.proiezione_risultato)}` : "mese chiuso"} tone={risultato >= 0 ? "text-emerald-700" : "text-rose-700"} testid="pdp-kpi-risultato" />
      </div>

      <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4" data-testid="pdp-bep-box">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-indigo-700">Punto di pareggio (Break Even Point)</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-indigo-900" data-testid="pdp-bep-valore">{bep != null ? eur(bep) : "—"}</p>
            <p className="text-xs text-slate-600">fatturato minimo del mese per coprire tutte le spese{bepGiorno != null ? ` · ${eur(bepGiorno)} al giorno su ${giorniAp} giorni di apertura` : ""}</p>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
            <div><p className="text-xs text-slate-500">Margine di contribuzione</p><p className="font-semibold tabular-nums" data-testid="pdp-mdc">{eur(mdc)} <span className="text-xs font-normal text-slate-500">({pct(mdcPct * 100)})</span></p></div>
            <div><p className="text-xs text-slate-500">{sicurezza != null && sicurezza >= 0 ? "Margine di sicurezza" : "Mancano al pareggio"}</p><p className={`font-semibold tabular-nums ${sicurezza != null && sicurezza >= 0 ? "text-emerald-700" : "text-rose-700"}`} data-testid="pdp-sicurezza">{sicurezza != null ? eur(Math.abs(sicurezza)) : "—"}{sicurezza != null && fatturato ? <span className="text-xs font-normal text-slate-500"> ({pct(Math.abs(sicurezza) / fatturato * 100)})</span> : null}</p></div>
            <div><p className="text-xs text-slate-500">Media fatturato / giorno</p><p className="font-semibold tabular-nums" data-testid="pdp-media-giorno">{eur(be?.media_giorno)} <span className="text-xs font-normal text-slate-500">({be?.giorni_inseriti || 0} gg inseriti)</span></p></div>
          </div>
        </div>
        <div className="mt-3 h-2.5 rounded-full bg-white"><div className={`h-2.5 rounded-full transition-all ${copertura >= 100 ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${copertura}%` }} data-testid="pdp-bep-bar" /></div>
        <p className="mt-2 flex items-start gap-1.5 text-[11px] text-slate-500"><Info className="mt-0.5 h-3 w-3 shrink-0" />BEP = costi fissi ÷ (1 − costi variabili ÷ fatturato). Fissi: stipendi, affitti, utenze, semi-fisse e spese contanti della prima nota. Variabili: fornitori/acquisti merce (crescono con le vendite). Valori lordi IVA come i corrispettivi.</p>
      </div>

      {trend.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="pdp-trend">
          <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Andamento ultimi {trend.length} mesi</p>
          <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }}>
            {trend.map((t) => (
              <div key={t.label} className="flex flex-col items-center gap-1" data-testid={`pdp-trend-${t.anno}-${t.mese}`}>
                <div className="relative flex h-28 w-full items-end justify-center gap-1">
                  <div className="w-1/3 rounded-t bg-emerald-500" style={{ height: `${(t.fatturato / maxTrend) * 100}%` }} title={`Fatturato ${eur(t.fatturato)}`} />
                  <div className="w-1/3 rounded-t bg-rose-400" style={{ height: `${(t.uscite / maxTrend) * 100}%` }} title={`Spese ${eur(t.uscite)}`} />
                  {t.bep != null && <div className="absolute left-0 right-0 border-t-2 border-dashed border-indigo-500" style={{ bottom: `${(t.bep / maxTrend) * 100}%` }} title={`BEP ${eur(t.bep)}`} />}
                </div>
                <p className="text-[11px] font-medium text-slate-700">{t.label}</p>
                <p className={`text-[11px] font-semibold tabular-nums ${t.risultato >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{t.risultato >= 0 ? "+" : ""}{Math.round(t.risultato).toLocaleString("it-IT")}</p>
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-[11px] text-slate-500"><span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-500" />Fatturato</span><span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-rose-400" />Spese</span><span><span className="mr-1 inline-block w-3 border-t-2 border-dashed border-indigo-500 align-middle" /> Punto di pareggio</span></div>
        </div>
      )}
    </div>
  );
};
