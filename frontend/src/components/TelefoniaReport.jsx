import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Smartphone, Phone, TrendingUp, TrendingDown, Minus } from "lucide-react";
import api, { apiError } from "../lib/api";
import { Button } from "./ui/button";

const MESI = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];
const eur = (v) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(v || 0);

const Delta = ({ a, b }) => {
  const d = a - b;
  if (!d) return <span className="inline-flex items-center gap-0.5 text-xs text-slate-400"><Minus className="h-3 w-3" /> {b}</span>;
  return <span className={`inline-flex items-center gap-0.5 text-xs ${d > 0 ? "text-emerald-700" : "text-rose-700"}`}>{d > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />} {d > 0 ? "+" : ""}{d} vs {b}</span>;
};

const Sezione = ({ id, titolo, Icon, s, canSeeAll }) => (
  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid={`report-tel-${id}`}>
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
      <h3 className="flex items-center gap-2 font-semibold text-slate-900"><Icon className="h-4 w-4 text-sky-600" /> {titolo}</h3>
      <div className="flex items-center gap-4 text-sm">
        <span className="font-semibold text-slate-900" data-testid={`report-tel-${id}-totale`}>{s.totale} attivazioni</span>
        <Delta a={s.totale} b={s.totale_prec} />
        {s.importo > 0 && <span className="text-slate-600">{eur(s.importo)}</span>}
        {s.annullati > 0 && <span className="text-xs text-rose-600">{s.annullati} annullate/respinte</span>}
      </div>
    </div>
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <th className="px-4 py-2">Operatore</th><th className="px-4 py-2 text-right">Attivazioni</th><th className="px-4 py-2">vs mese prec.</th>
          {id === "mobile" && <th className="px-4 py-2">Nuove / MNP / Cambio</th>}
          {id === "fisso" && <th className="px-4 py-2">Prodotti</th>}
          <th className="px-4 py-2 text-right">Importo</th><th className="px-4 py-2">Pagate</th>{canSeeAll && <th className="px-4 py-2">Negozi</th>}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {s.righe.map((r) => (
          <tr key={r.operatore} data-testid={`report-tel-${id}-${r.operatore.toLowerCase().replace(/\W+/g, "-")}`}>
            <td className="px-4 py-2 font-medium text-slate-900">{r.operatore}</td>
            <td className="px-4 py-2 text-right text-lg font-semibold tabular-nums">{r.n}</td>
            <td className="px-4 py-2"><Delta a={r.n} b={r.n_prec} /></td>
            {id === "mobile" && <td className="px-4 py-2 text-slate-600">{r.nuovi} / {r.mnp} / {r.cambio_offerta}</td>}
            {id === "fisso" && <td className="px-4 py-2 text-xs text-slate-600">{Object.entries(r.categorie).map(([k, v]) => `${k} ×${v}`).join(", ") || "—"}</td>}
            <td className="px-4 py-2 text-right tabular-nums text-slate-700">{r.importo ? eur(r.importo) : "—"}</td>
            <td className="px-4 py-2 text-xs"><span className="text-emerald-700">{r.pagati} sì</span>{r.non_pagati > 0 && <span className="ml-1 text-rose-600">{r.non_pagati} no</span>}</td>
            {canSeeAll && <td className="px-4 py-2 text-xs text-slate-600">{Object.entries(r.negozi).map(([k, v]) => `${k} ${v}`).join(" · ")}</td>}
          </tr>
        ))}
        {!s.righe.length && <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-500">Nessuna attivazione nel mese.</td></tr>}
      </tbody>
    </table>
    {canSeeAll && Object.keys(s.negozi).length > 0 && (
      <div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-2 text-xs text-slate-600">
        <span className="font-medium">Per negozio:</span>{Object.entries(s.negozi).sort((a, b) => b[1] - a[1]).map(([k, v]) => <span key={k} className="rounded bg-slate-100 px-2 py-0.5">{k} <b>{v}</b></span>)}
      </div>
    )}
  </div>
);

export const TelefoniaReport = ({ canSeeAll }) => {
  const oggi = new Date();
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/telefonia/report", { params: { anno, mese } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))); }, [anno, mese]);
  const csv = () => {
    const righe = [["Sezione", "Operatore", "Attivazioni", "Mese prec.", "Nuove", "MNP", "Cambio offerta", "Importo", "Pagate", "Non pagate", "Annullate", "Negozi"]];
    for (const [sez, s] of Object.entries(d.sezioni)) for (const r of s.righe) righe.push([sez, r.operatore, r.n, r.n_prec, r.nuovi, r.mnp, r.cambio_offerta, r.importo, r.pagati, r.non_pagati, r.annullati, Object.entries(r.negozi).map(([k, v]) => `${k} ${v}`).join(" | ")]);
    const blob = new Blob(["\ufeff" + righe.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")).join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `telefonia_${anno}-${String(mese).padStart(2, "0")}.csv`; a.click();
  };
  return (
    <div className="space-y-4" data-testid="telefonia-report">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <select value={mese} onChange={(e) => setMese(+e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="report-tel-mese">{MESI.slice(1).map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
          <select value={anno} onChange={(e) => setAnno(+e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm" data-testid="report-tel-anno">{[anno - 2, anno - 1, anno, anno + 1].filter((a) => a <= oggi.getFullYear()).map((a) => <option key={a} value={a}>{a}</option>)}</select>
          {d && <span className="text-xs text-slate-500">confronto con {d.mese_prec}</span>}
        </div>
        {d && <Button variant="outline" size="sm" onClick={csv} className="gap-1.5" data-testid="report-tel-csv"><Download className="h-4 w-4" /> Scarica CSV</Button>}
      </div>
      {d && <Sezione id="mobile" titolo="Mobile (SIM)" Icon={Smartphone} s={d.sezioni.mobile} canSeeAll={canSeeAll} />}
      {d && <Sezione id="fisso" titolo="Fisso (internet e voce)" Icon={Phone} s={d.sezioni.fisso} canSeeAll={canSeeAll} />}
    </div>
  );
};
