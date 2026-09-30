import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileDown } from "lucide-react";
import api, { apiError, downloadBlob } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI } from "../../lib/constants";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Switch } from "../ui/switch";
import { Label } from "../ui/label";

export const eur = (v) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(v || 0);
const mesePretty = (m) => (m ? `${MESI[parseInt(m.slice(5)) - 1]?.slice(0, 3)} ${m.slice(0, 4)}` : "");

export const CompensiCalcolo = () => {
  const oggi = new Date();
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [perPagamento, setPerPagamento] = useState(false);
  const [data, setData] = useState(null);

  const load = useCallback(() => api.get("/compensi/calcolo", { params: { anno, mese, per_pagamento: perPagamento } }).then((r) => setData(r.data)).catch((e) => toast.error(apiError(e))), [anno, mese, perPagamento]);
  useEffect(() => { load(); }, [load]);

  const segnaGara = async (riga, pagata) => {
    try { await api.post("/compensi/gare/pagata", { regola_id: riga.regola_id, mese: riga.competenza, pagata }); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="compensi-mese"><SelectValue /></SelectTrigger>
          <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
        <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="compensi-anno"><SelectValue /></SelectTrigger>
          <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5">
          <Switch checked={perPagamento} onCheckedChange={setPerPagamento} data-testid="compensi-per-pagamento" />
          <Label className="text-sm">{perPagamento ? "Cosa si paga in questo mese" : "Lavoro maturato nel mese (competenza)"}</Label>
        </div>
        {data && <span className="ml-auto rounded-full bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white" data-testid="compensi-totale">Totale netto {eur(data.totale_netto)}</span>}
        <Button variant="outline" className="gap-1.5" onClick={() => downloadBlob(`/compensi/report-pdf?anno=${anno}&mese=${mese}&per_pagamento=${perPagamento}`, `compensi_${anno}-${String(mese).padStart(2, "0")}.pdf`)} data-testid="compensi-pdf-tutti"><FileDown className="h-4 w-4" /> PDF tutti</Button>
      </div>

      {data?.destinatari.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500" data-testid="compensi-vuoto">Nessun compenso maturato per il periodo scelto. Controlla le regole (importi a 0 € non producono compensi).</p>}

      {data?.destinatari.map((d) => (
        <div key={d.tipo + d.id} className="rounded-xl border border-slate-200 bg-white" data-testid={`compensi-dest-${d.id}`}>
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-3">
            <span className={`status-badge ${d.tipo === "store" ? "bg-sky-500/15 text-sky-700 border-sky-300" : "bg-violet-500/15 text-violet-700 border-violet-300"}`}>{d.tipo === "store" ? "Negozio" : "Operatore"}</span>
            <h3 className="font-heading text-lg font-semibold text-slate-900">{d.nome}</h3>
            <div className="ml-auto flex flex-wrap gap-4 text-sm">
              <span className="text-slate-500">Lordo <b className="text-slate-900">{eur(d.lordo)}</b></span>
              {d.trattenuta_pct > 0 && <span className="text-slate-500">Trattenuta {d.trattenuta_pct}% <b className="text-rose-700">−{eur(d.trattenuta)}</b>{d.iva_su_trattenuta > 0 && <> + IVA <b className="text-rose-700">−{eur(d.iva_su_trattenuta)}</b></>}</span>}
              {d.addebito_laboratorio > 0 && <span className="text-slate-500">Laboratorio <b className="text-rose-700" data-testid={`compensi-addebito-lab-${d.id}`}>−{eur(d.addebito_laboratorio)}</b></span>}
              <span className="text-slate-500">Netto <b className="text-emerald-700" data-testid={`compensi-netto-${d.id}`}>{eur(d.netto)}</b></span>
              <button type="button" className="inline-flex items-center gap-1 text-xs text-indigo-700 hover:underline" onClick={() => downloadBlob(`/compensi/report-pdf?anno=${anno}&mese=${mese}&per_pagamento=${perPagamento}&dest_id=${d.id}`, `compensi_${anno}-${String(mese).padStart(2, "0")}_${d.nome}.pdf`)} data-testid={`compensi-pdf-${d.id}`}><FileDown className="h-3.5 w-3.5" /> PDF</button>
              {d.gare_in_attesa > 0 && <span className="text-amber-700">Gare in attesa {eur(d.gare_in_attesa)}</span>}
              {(d.ricariche_da_richiedere > 0 || d.costo_sim > 0) && <span className="text-slate-500">Da richiedere: ricariche <b>{eur(d.ricariche_da_richiedere)}</b> · SIM <b>{eur(d.costo_sim)}</b></span>}
            </div>
          </div>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-5 py-2">Voce</th><th className="px-3 py-2">Quantità</th><th className="px-3 py-2">Unitario</th><th className="px-3 py-2">Totale</th><th className="px-3 py-2">Competenza → Pagamento</th><th className="px-3 py-2">Stato</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.righe.map((r) => (
                <tr key={r.regola_id + r.competenza}>
                  <td className="px-5 py-2 text-slate-800">{r.nome}</td>
                  <td className="px-3 py-2">{r.conteggio}{r.soglia > 0 && <span className={`ml-1 text-xs ${r.soglia_raggiunta ? "text-emerald-600" : "text-amber-600"}`}>({r.conteggio_globale ?? r.conteggio}/{r.soglia} soglia)</span>}</td>
                  <td className="px-3 py-2">{r.modalita === "forfait" ? "forfait" : eur(r.importo_unitario)}</td>
                  <td className="px-3 py-2 font-semibold">{eur(r.totale)}</td>
                  <td className="px-3 py-2 text-slate-500">{mesePretty(r.competenza)} → {mesePretty(r.pagamento)}</td>
                  <td className="px-3 py-2">
                    {r.e_gara ? (
                      <button type="button" onClick={() => segnaGara(r, !r.gara_pagata)} className={`status-badge cursor-pointer ${r.gara_pagata ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-amber-500/15 text-amber-700 border-amber-300"}`} data-testid={`gara-toggle-${r.regola_id}`}>
                        {r.gara_pagata ? "Gara incassata" : "Gara in attesa di incasso"}
                      </button>
                    ) : r.soglia > 0 && !r.soglia_raggiunta ? <span className="text-xs text-amber-600">Soglia non raggiunta</span> : <span className="text-xs text-emerald-600">Maturato</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
};
