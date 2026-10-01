import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, Num, PeriodoPicker, eur } from "./shared";
import { CentriCostoEditor } from "./CentriCostoEditor";
import { FattureAde } from "./FattureAde";

const CAT = [["entrate", "Entrate", "text-emerald-700"], ["spese_fisse", "Spese fisse", "text-rose-700"], ["spese_semifisse", "Spese semi-fisse modificabili", "text-amber-700"], ["fornitori", "Fornitori / acquisti", "text-slate-700"]];

export const PuntoPareggio = ({ storeId, anno, mese, setAnno, setMese, isAdmin }) => {
  const [centri, setCentri] = useState([]);
  const [centroId, setCentroId] = useState("");
  const [d, setD] = useState(null);
  const [valori, setValori] = useState({});
  const [voci, setVoci] = useState(null);
  const [nuova, setNuova] = useState({});
  const loadCentri = useCallback(() => api.get("/contabilita/pdp/centri").then((r) => {
    setCentri(r.data);
    setCentroId((cur) => (r.data.some((c) => c.id === cur) ? cur : (r.data.find((c) => c.store_ids.includes(storeId)) || r.data[0] || {}).id || ""));
  }).catch((e) => toast.error(apiError(e))), [storeId]);
  useEffect(() => { loadCentri(); }, [loadCentri]);
  const load = useCallback(() => {
    if (!centroId) return;
    api.get("/contabilita/pdp", { params: { centro_id: centroId, anno, mese } }).then((r) => { setD(r.data); setValori(r.data.valori); setVoci(r.data.voci); }).catch((e) => toast.error(apiError(e)));
  }, [centroId, anno, mese]);
  useEffect(() => { load(); }, [load]);
  const salva = async () => { try { const r = await api.put(`/contabilita/pdp/${centroId}/${anno}/${mese}`, { valori, note: d.note || "" }); setD(r.data); toast.success("Punto di pareggio salvato"); } catch (e) { toast.error(apiError(e)); } };
  const salvaVoci = async (v) => { try { await api.put(`/contabilita/pdp/voci/${centroId}`, v); setVoci(v); } catch (e) { toast.error(apiError(e)); } };
  if (!centroId) return <p className="text-sm text-slate-500" data-testid="pdp-nessun-centro">Nessun centro di costo disponibile.</p>;
  if (!d || !voci) return null;
  const AUTO = { entrate: ["Corrispettivi negozi", "Fatture emesse (AdE)"], fornitori: ["Fatture ricevute (AdE)"] };
  const autoVal = (cat) => (AUTO[cat] || []).reduce((a, k) => a + ((cat === "entrate" ? d.entrate[k] : d.sezioni[cat][k]) || 0), 0);
  const somma = (cat) => voci[cat].reduce((a, v) => a + (parseFloat(valori[`${cat}|${v}`]) || 0), 0);
  const entrate = autoVal("entrate") + somma("entrate");
  const uscite = somma("spese_fisse") + somma("spese_semifisse") + somma("fornitori") + autoVal("fornitori");
  const ris = entrate - uscite;
  return (
    <div className="space-y-5" data-testid="pdp-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <select value={centroId} onChange={(e) => setCentroId(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm font-medium" data-testid="pdp-centro-select">
            {centri.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
          <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
          {isAdmin && <CentriCostoEditor centri={centri} onSaved={loadCentri} />}
        </div>
        <Button size="sm" onClick={salva} data-testid="pdp-salva">Salva valori</Button>
      </div>
      <p className="text-xs text-slate-500" data-testid="pdp-centro-negozi">Centro di costo <b>{d.centro.nome}</b>: {d.centro.negozi.join(" + ")} — i corrispettivi dei negozi entrano automaticamente nelle entrate.</p>
      {d.ereditato_da && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900" data-testid="pdp-ereditato">
          <span>Valori precompilati da <b>{d.ereditato_da}</b>: modificali se sono cambiati, poi premi "Salva valori" per confermarli per questo mese.</span>
          <Button size="sm" variant="outline" onClick={salva} data-testid="pdp-conferma-ereditato">Conferma per {MESI[mese]}</Button>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-4" data-testid="pdp-riepilogo">
        <div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs uppercase text-slate-500">Entrate</p><p className="mt-1 text-xl font-semibold text-emerald-700" data-testid="pdp-entrate">{eur(entrate)}</p></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs uppercase text-slate-500">Punto di pareggio (uscite)</p><p className="mt-1 text-xl font-semibold text-rose-700" data-testid="pdp-uscite">{eur(uscite)}</p></div>
        <div className={`rounded-xl border p-4 ${ris >= 0 ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50"}`}><p className="text-xs uppercase text-slate-500">{ris >= 0 ? "Guadagno" : "Sotto pareggio"}</p><p className="mt-1 text-xl font-semibold" data-testid="pdp-risultato">{eur(ris)}</p></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs uppercase text-slate-500">Copertura</p><p className="mt-1 text-xl font-semibold" data-testid="pdp-copertura">{uscite ? `${(entrate / uscite * 100).toFixed(1)}%` : "—"}</p>
          <div className="mt-2 h-2 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${ris >= 0 ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${Math.min(100, uscite ? entrate / uscite * 100 : 0)}%` }} /></div></div>
      </div>
      <FattureAde centroId={centroId} anno={anno} mese={mese} onChanged={load} />
      <div className="grid gap-4 lg:grid-cols-2">
        {CAT.map(([cat, label, color]) => (
          <div key={cat} className="rounded-xl border border-slate-200 bg-white" data-testid={`pdp-sezione-${cat}`}>
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5"><h3 className={`text-sm font-semibold ${color}`}>{label}</h3><span className="text-sm font-semibold tabular-nums">{eur(somma(cat) + autoVal(cat))}</span></div>
            <div className="divide-y divide-slate-50 px-4">
              {cat === "entrate" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Corrispettivi negozi <span className="text-xs text-slate-400">(automatico: {d.centro.negozi.join(" + ")})</span></span><span className="tabular-nums font-medium" data-testid="pdp-corrispettivi-auto">{eur(d.entrate["Corrispettivi negozi"])}</span></div>}
              {cat === "entrate" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Fatture emesse <span className="text-xs text-slate-400">(automatico da Agenzia Entrate)</span></span><span className="tabular-nums font-medium" data-testid="pdp-fatture-emesse-auto">{eur(d.entrate["Fatture emesse (AdE)"])}</span></div>}
              {cat === "fornitori" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Fatture ricevute <span className="text-xs text-slate-400">(automatico da Agenzia Entrate)</span></span><span className="tabular-nums font-medium" data-testid="pdp-fatture-ricevute-auto">{eur(d.sezioni.fornitori["Fatture ricevute (AdE)"])}</span></div>}
              {voci[cat].map((v) => (
                <div key={v} className="flex items-center gap-2 py-1.5 text-sm">
                  <span className="flex-1 text-slate-600">{v}</span>
                  <div className="w-32"><Num value={valori[`${cat}|${v}`]} onChange={(x) => setValori({ ...valori, [`${cat}|${v}`]: x })} testid={`pdp-val-${cat}-${v.replace(/\W/g, "_")}`} /></div>
                  <button onClick={() => salvaVoci({ ...voci, [cat]: voci[cat].filter((x) => x !== v) })} className="text-slate-300 hover:text-rose-600" title="Rimuovi voce" data-testid={`pdp-del-${cat}-${v.replace(/\W/g, "_")}`}><X className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              <div className="flex items-center gap-2 py-2">
                <input placeholder="Nuova voce…" value={nuova[cat] || ""} onChange={(e) => setNuova({ ...nuova, [cat]: e.target.value })} className="h-8 flex-1 rounded border border-dashed border-slate-300 px-2 text-sm" data-testid={`pdp-nuova-${cat}`} />
                <Button size="sm" variant="ghost" onClick={() => { const n = (nuova[cat] || "").trim(); if (n && !voci[cat].includes(n)) { salvaVoci({ ...voci, [cat]: [...voci[cat], n] }); setNuova({ ...nuova, [cat]: "" }); } }} data-testid={`pdp-add-${cat}`}><Plus className="h-4 w-4" /></Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
