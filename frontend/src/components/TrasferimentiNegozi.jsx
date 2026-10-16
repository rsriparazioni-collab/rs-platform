import { useCallback, useEffect, useState } from "react";
import { ArrowLeftRight, FileDown, Receipt } from "lucide-react";
import { toast } from "sonner";
import api, { apiError, downloadBlob } from "../lib/api";
import { MESI } from "../lib/constants";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { TrasferimentoConsegna } from "./TrasferimentoConsegna";

const eur = (v) => new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(v || 0);

export const TrasferimentiNegozi = () => {
  const oggi = new Date();
  const [open, setOpen] = useState(false);
  const [anno, setAnno] = useState(oggi.getFullYear());
  const [mese, setMese] = useState(oggi.getMonth() + 1);
  const [data, setData] = useState(null);

  const load = useCallback(() => api.get("/magazzino/trasferimenti", { params: { anno, mese } }).then((r) => setData(r.data)).catch(() => {}), [anno, mese]);
  useEffect(() => { if (open) load(); }, [open, load]);

  const fattura = async (r) => {
    const num = r.fatturato ? "" : window.prompt("Numero fattura (opzionale)", "");
    if (!r.fatturato && num === null) return;
    try { await api.post(`/magazzino/trasferimenti/${r.id}/fatturato`, { fatturato: !r.fatturato, numero_fattura: num || "" }); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const prezzo = async (r) => {
    const v = window.prompt(`Prezzo unitario per la fattura tra negozi (${r.nome})`, String(r.prezzo_unitario));
    if (v === null) return;
    try { await api.patch(`/magazzino/trasferimenti/${r.id}`, { prezzo_unitario: parseFloat(v.replace(",", ".")) || 0 }); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="trasferimenti-box">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-5 py-3 text-left" data-testid="trasferimenti-toggle">
        <ArrowLeftRight className="h-5 w-5 text-indigo-600" />
        <div className="flex-1">
          <p className="font-heading font-semibold text-slate-900">Trasferimenti tra negozi</p>
          <p className="text-xs text-slate-500">Pezzi presi dal magazzino di un altro negozio (riparazioni e vendite): report per la fattura dal negozio cedente a quello ricevente.</p>
        </div>
        <span className="text-xs text-slate-400">{open ? "Chiudi" : "Apri"}</span>
      </button>
      {open && (
        <div className="space-y-4 border-t border-slate-100 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <Select value={String(mese)} onValueChange={(v) => setMese(parseInt(v))}><SelectTrigger className="w-[140px]" data-testid="trasferimenti-mese"><SelectValue /></SelectTrigger>
              <SelectContent>{MESI.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select>
            <Select value={String(anno)} onValueChange={(v) => setAnno(parseInt(v))}><SelectTrigger className="w-[100px]" data-testid="trasferimenti-anno"><SelectValue /></SelectTrigger>
              <SelectContent>{[anno - 1, anno, anno + 1].map((a) => <SelectItem key={a} value={String(a)}>{a}</SelectItem>)}</SelectContent></Select>
            <Button variant="outline" className="gap-2" onClick={() => downloadBlob(`/magazzino/trasferimenti/export?anno=${anno}&mese=${mese}`, `trasferimenti_${anno}-${String(mese).padStart(2, "0")}.xlsx`)} data-testid="trasferimenti-export"><FileDown className="h-4 w-4" /> Excel</Button>
            {data && <span className="ml-auto text-sm text-slate-600">Totale mese <b data-testid="trasferimenti-totale">{eur(data.totale)}</b></span>}
          </div>
          {data?.coppie.length === 0 && <p className="text-sm text-slate-400" data-testid="trasferimenti-vuoto">Nessun trasferimento nel mese.</p>}
          {data?.coppie.map((c) => (
            <div key={c.da_store_id + c.a_store_id} className="rounded-lg border border-slate-200" data-testid={`trasferimenti-coppia-${c.da_store_id}-${c.a_store_id}`}>
              <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm">
                <span className="font-semibold text-slate-900">{c.da_store}</span><ArrowLeftRight className="h-3.5 w-3.5 text-slate-400" /><span className="font-semibold text-slate-900">{c.a_store}</span>
                <span className="text-xs text-slate-500">{c.pezzi} pz</span>
                <span className="ml-auto text-xs text-slate-600">Imponibile {eur(c.imponibile)} · IVA {eur(c.iva)} · <b>Totale {eur(c.totale)}</b>{c.da_fatturare > 0 && <span className="ml-2 text-amber-700">da fatturare {eur(c.da_fatturare)}</span>}{c.non_pagato > 0 && <span className="ml-2 text-rose-700" data-testid="trasferimenti-non-pagato">non pagato {eur(c.non_pagato)}</span>}{c.da_consegnare > 0 && <span className="ml-2 text-sky-700" data-testid="trasferimenti-da-consegnare">{c.da_consegnare} pz da consegnare</span>}</span>
              </div>
              <table className="w-full text-sm"><tbody className="divide-y divide-slate-100">
                {c.righe.map((r) => (
                  <tr key={r.id} className={r.fatturato ? "opacity-60" : ""}>
                    <td className="px-4 py-1.5 text-slate-500">{r.at.slice(0, 10)}</td>
                    <td className="px-2 py-1.5 text-slate-800">{r.nome}<span className="ml-1 text-xs text-slate-400">{r.riferimento}</span>{r.in_ordine && <span className="status-badge ml-1 bg-rose-500/15 text-rose-700 border-rose-300">in ordine</span>}
                      <div className="mt-1"><TrasferimentoConsegna r={r} onChanged={load} /></div>
                    </td>
                    <td className="px-2 py-1.5">{r.quantita} × <button type="button" className="underline decoration-dotted" onClick={() => !r.fatturato && prezzo(r)} data-testid={`trasferimento-prezzo-${r.id}`}>{eur(r.prezzo_unitario)}</button> <span className="text-xs text-slate-400">{r.regime_iva}</span></td>
                    <td className="px-2 py-1.5 font-semibold">{eur(r.totale)}</td>
                    <td className="px-4 py-1.5 text-right">
                      <button type="button" onClick={() => fattura(r)} className={`status-badge cursor-pointer ${r.fatturato ? "bg-emerald-500/15 text-emerald-700 border-emerald-300" : "bg-slate-500/10 text-slate-600 border-slate-300"}`} data-testid={`trasferimento-fattura-${r.id}`}>
                        <Receipt className="h-3 w-3" /> {r.fatturato ? `Fatturato${r.numero_fattura ? ` n. ${r.numero_fattura}` : ""}` : "Segna fatturato"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody></table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
