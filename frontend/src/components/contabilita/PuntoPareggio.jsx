import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, Num, PeriodoPicker, eur } from "./shared";
import { CentriCostoEditor } from "./CentriCostoEditor";
import { FattureAde } from "./FattureAde";
import { PdpAnalisi } from "./PdpAnalisi";
import { PdpDashboard } from "./PdpDashboard";
import { PdpImportReport } from "./PdpImportReport";
import { IvaDashboard } from "./IvaDashboard";
import { PdpNegozi } from "./PdpNegozi";

const CAT = [["entrate", "Entrate (fatturato)", "text-emerald-700"], ["spese_fisse", "Spese fisse", "text-rose-700"], ["spese_semifisse", "Spese semi-fisse e contanti", "text-amber-700"], ["fornitori", "Fornitori / acquisti (costi variabili)", "text-slate-700"]];

export const PuntoPareggio = ({ storeId, anno, mese, setAnno, setMese, isAdmin }) => {
  const [centri, setCentri] = useState([]);
  const [centroId, setCentroId] = useState("");
  const [d, setD] = useState(null);
  const [importing, setImporting] = useState(false);
  const [report, setReport] = useState(null);
  const [valori, setValori] = useState({});
  const [voci, setVoci] = useState(null);
  const [nuova, setNuova] = useState({});
  const loadCentri = useCallback(() => api.get("/contabilita/pdp/centri").then((r) => {
    setCentri(r.data);
    setCentroId((cur) => (r.data.some((c) => c.id === cur) ? cur : (r.data.find((c) => c.store_ids.includes(storeId)) || r.data[0] || {}).id || ""));
  }).catch((e) => toast.error(apiError(e))), [storeId]);
  useEffect(() => { loadCentri(); }, [loadCentri]);
  const reqId = useRef(0);
  const load = useCallback(() => {
    if (!centroId) return;
    const id = ++reqId.current;
    api.get("/contabilita/pdp", { params: { centro_id: centroId, anno, mese } }).then((r) => { if (id !== reqId.current) return; setD(r.data); setValori(r.data.valori); setVoci(r.data.voci); }).catch((e) => toast.error(apiError(e)));
  }, [centroId, anno, mese]);
  useEffect(() => { load(); }, [load]);
  const salva = async () => { try { const r = await api.put(`/contabilita/pdp/${centroId}/${anno}/${mese}`, { valori, note: d.note || "" }); setD(r.data); toast.success("Punto di pareggio salvato"); } catch (e) { toast.error(apiError(e)); } };
  const salvaVoci = async (v) => { try { await api.put(`/contabilita/pdp/voci/${centroId}`, v); setVoci(v); } catch (e) { toast.error(apiError(e)); } };
  if (!centroId) return <p className="text-sm text-slate-500" data-testid="pdp-nessun-centro">Nessun centro di costo disponibile.</p>;
  if (!d || !voci) return null;
  const AUTO = { entrate: Object.keys(d.entrate), fornitori: ["Fatture ricevute non abbinate (AdE)"] };
  const adeF = d.ade_fornitori || {};
  const autoVal = (cat) => (AUTO[cat] || []).reduce((a, k) => a + ((cat === "entrate" ? d.entrate[k] : d.sezioni[cat][k]) || 0), 0) + (cat === "fornitori" ? Object.values(adeF).reduce((a, v) => a + v, 0) : 0);
  const emesseAde = d.entrate["Fatture emesse (AdE)"] || 0;
  const somma = (cat) => voci[cat].reduce((a, v) => a + ((cat === "entrate" && emesseAde > 0) || (cat === "fornitori" && adeF[v] > 0) ? 0 : (parseFloat(valori[`${cat}|${v}`]) || 0)), 0);
  const entrate = autoVal("entrate") + somma("entrate");
  const speseCassa = d.tot_spese_cassa || 0;
  const fissi = somma("spese_fisse") + somma("spese_semifisse") + speseCassa;
  const variabili = somma("fornitori") + autoVal("fornitori");
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
        <Button size="sm" variant="outline" disabled={importing} data-testid="pdp-importa-fogli" onClick={async () => { setImporting(true); try { const r = await api.post("/contabilita/pdp/importa-fogli"); setReport(r.data.esito); load(); } catch (e) { toast.error(apiError(e)); } finally { setImporting(false); } }}>{importing ? "Importo…" : "Importa dai fogli Google"}</Button>
      </div>
      <PdpImportReport esito={report} onClose={() => setReport(null)} onChanged={async () => { load(); try { const r = await api.post("/contabilita/pdp/importa-fogli"); setReport(r.data.esito); } catch (e) { toast.error(apiError(e)); } }} />
      <p className="text-xs text-slate-500" data-testid="pdp-centro-negozi">Centro di costo <b>{d.centro.nome}</b>: {d.centro.negozi.join(" + ")} — i corrispettivi dei negozi entrano automaticamente nelle entrate.</p>
      {d.foglio && <div className={`space-y-1 rounded-lg border px-4 py-2 text-sm ${Math.abs(d.foglio.diff_entrate) < 1 && Math.abs(d.foglio.diff_uscite) < 1 ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`} data-testid="pdp-foglio-confronto">
        <div className="flex flex-wrap items-center gap-3">
          <b>Foglio Google:</b> entrate {eur(d.foglio.entrate)} <span className="text-xs">(corrispettivi {eur(d.foglio.corrispettivi)} + fatture {eur(d.foglio.emesse)})</span> → PDP {eur(d.tot_entrate)} <b>{d.foglio.diff_entrate > 0 ? "+" : ""}{eur(d.foglio.diff_entrate)}</b>
          <span className="text-slate-400">|</span> uscite {eur(d.foglio.uscite)} → PDP {eur(d.tot_uscite)} <b>{d.foglio.diff_uscite > 0 ? "+" : ""}{eur(d.foglio.diff_uscite)}</b>
        </div>
        {d.foglio.giorni_diff?.length > 0 && <details className="text-xs" data-testid="pdp-foglio-giorni"><summary className="cursor-pointer">Giorni di scontrini che spiegano la differenza: {d.foglio.giorni_diff.length} giorni, {eur(d.foglio.giorni_diff.reduce((s, g) => s + (g.diff ?? g.scontrini ?? 0), 0))} (gestionale − foglio)</summary>
          {isAdmin && d.foglio.giorni_diff.some((g) => g.foglio && !g.scontrini) && <button className="mt-1 rounded border border-rose-300 bg-rose-50 px-2 py-1 font-medium text-rose-800 hover:bg-rose-100" data-testid="pdp-allinea-rossi" onClick={async () => { const n = d.foglio.giorni_diff.filter((g) => g.foglio && !g.scontrini).length; if (!window.confirm(`Compilare dal foglio i ${n} giorni mancanti nel gestionale (merce = totale registratore, contanti pari importo)?`)) return; try { const r = await api.post("/contabilita/pdp/allinea-foglio", { centro_id: centroId, anno, mese }); toast.success(`${r.data.compilati} giorni compilati dal foglio`); load(); } catch (e) { toast.error(apiError(e)); } }}>Compila dal foglio i giorni rossi</button>}
          <div className="mt-1 flex flex-wrap gap-1">{d.foglio.giorni_diff.map((g, i) => <span key={i} className={`rounded border px-1.5 py-0.5 ${g.foglio == null ? "border-slate-300 bg-white" : g.scontrini === 0 ? "border-rose-300 bg-rose-50" : "border-amber-300 bg-white"}`} title={`Gestionale ${eur(g.scontrini)} · foglio ${g.foglio == null ? "assente" : eur(g.foglio)}`}>{g.data.slice(8)}/{g.data.slice(5, 7)} {g.negozio}: {g.foglio == null ? `solo gestionale ${eur(g.scontrini)}` : g.scontrini === 0 ? `manca nel gestionale (${eur(g.foglio)})` : `${g.diff > 0 ? "+" : ""}${eur(g.diff)}`}</span>)}</div></details>}
      </div>}
      {d.ereditato_da && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900" data-testid="pdp-ereditato">
          <span>Valori precompilati da <b>{d.ereditato_da}</b>: modificali se sono cambiati, poi premi "Salva valori" per confermarli per questo mese.</span>
          <Button size="sm" variant="outline" onClick={salva} data-testid="pdp-conferma-ereditato">Conferma per {MESI[mese]}</Button>
        </div>
      )}
      <PdpDashboard centroId={centroId} anno={anno} mese={mese} fatturato={entrate} fissi={fissi} variabili={variabili} incasso={d.incasso} be={d.break_even} iva={d.iva} />
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4" data-testid="pdp-sezione-iva"><IvaDashboard centroId={centroId} anno={anno} mese={mese} isAdmin={isAdmin} compatto /></div>
      <PdpNegozi anno={anno} mese={mese} isAdmin={isAdmin} />
      <FattureAde centroId={centroId} anno={anno} mese={mese} onChanged={load} />
      <PdpAnalisi centroId={centroId} anno={anno} mese={mese} />
      <div className="grid gap-4 lg:grid-cols-2">
        {CAT.map(([cat, label, color]) => (
          <div key={cat} className="rounded-xl border border-slate-200 bg-white" data-testid={`pdp-sezione-${cat}`}>
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5"><h3 className={`text-sm font-semibold ${color}`}>{label}</h3><span className="text-sm font-semibold tabular-nums">{eur(somma(cat) + autoVal(cat) + (cat === "spese_semifisse" ? speseCassa : 0))}</span></div>
            <div className="divide-y divide-slate-50 px-4">
              {cat === "spese_semifisse" && (
                <div className="py-1.5 text-sm" data-testid="pdp-spese-cassa-auto">
                  <div className="flex items-center justify-between"><span className="text-slate-600">Spese contanti prima nota <span className="text-xs text-slate-400">(automatico dai corrispettivi e dai fogli importati)</span></span><span className="tabular-nums font-medium">{eur(speseCassa)}</span></div>
                  {Object.keys(d.spese_cassa || {}).length > 0 && <p className="mt-0.5 text-[11px] text-slate-400">{Object.entries(d.spese_cassa).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => `${k} ${eur(v)}`).join(" · ")}</p>}
                  {speseCassa > 0 && <p className="mt-0.5 text-[11px] text-amber-600">Non reinserire a mano sotto le stesse spese (es. Ritiri) per evitare il doppio conteggio.</p>}
                  {(d.spese_cassa_in_fattura || []).length > 0 && <p className="mt-0.5 text-[11px] text-emerald-700" data-testid="pdp-spese-cassa-in-fattura">Escluse perché già in fattura AdE: {d.spese_cassa_in_fattura.map((x) => `${x.motivo} ${eur(x.importo)} (${x.controparte_ade})`).join(" · ")}</p>}
                  {(d.possibili_doppi || []).length > 0 && <div className="mt-0.5 text-[11px] font-medium text-rose-700" data-testid="pdp-possibili-doppi">⚠ Possibile doppio conteggio: {d.possibili_doppi.map((x) => (
                    <span key={x.voce} className="mr-2">voce "{x.voce}" {eur(x.importo)} = fattura AdE {x.controparte_ade}
                      {isAdmin && <button type="button" className="ml-1 rounded border border-rose-300 bg-white px-1.5 py-0.5 text-[10px] text-rose-800 hover:bg-rose-50" data-testid={`pdp-alias-${x.voce}`}
                        onClick={async () => { try { await api.put("/contabilita/alias-fornitori", { controparte: x.controparte_ade, voce: x.voce }); toast.success(`Da ora "${x.controparte_ade}" viene letto come "${x.voce}"`); load(); } catch (e) { toast.error(apiError(e)); } }}>È la stessa ditta: collega</button>}
                    </span>))} — se è la stessa fattura azzera la voce manuale.</div>}
                </div>
              )}
              {cat === "entrate" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Corrispettivi negozi (scontrini) <span className="text-xs text-slate-400">(automatico: {d.centro.negozi.join(" + ")})</span></span><span className="tabular-nums font-medium" data-testid="pdp-corrispettivi-auto">{eur(d.entrate["Corrispettivi negozi (scontrini)"])}</span></div>}
              {cat === "entrate" && d.entrate["Fatture da chiusure senza documento AdE"] > 0 && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-rose-700">Fatture da chiusure senza documento AdE <span className="text-xs text-slate-400">(manuali, non riconciliate)</span></span><span className="tabular-nums font-medium" data-testid="pdp-fatture-manuali-sole">{eur(d.entrate["Fatture da chiusure senza documento AdE"])}</span></div>}
              {cat === "entrate" && d.fatture_manuali?.nota && <p className="py-1 text-xs text-amber-700" data-testid="pdp-fatture-manuali-nota">{d.fatture_manuali.nota} Non sommate: {eur(d.fatture_manuali.tot_non_riconciliate)} ({d.fatture_manuali.non_riconciliate.map((x) => `${x.data.slice(8)}/${x.data.slice(5, 7)} ${eur(x.importo)}`).join(", ")})</p>}
              {cat === "entrate" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Fatture emesse <span className="text-xs text-slate-400">(automatico da Agenzia Entrate / fogli)</span></span><span className="tabular-nums font-medium" data-testid="pdp-fatture-emesse-auto">{eur(d.entrate["Fatture emesse (AdE)"])}</span></div>}
              {cat === "entrate" && emesseAde > 0 && <p className="py-1 text-[11px] text-amber-600" data-testid="pdp-entrate-info">Le voci sotto (Eolo, Energia, Telefonia, Pacchi) sono già comprese nelle fatture emesse e non vengono sommate di nuovo.</p>}
              {cat === "fornitori" && Object.keys(adeF).length > 0 && <p className="py-1 text-[11px] text-amber-600">Per i fornitori con fatture ricevute abbinate vale l'importo delle fatture; il valore manuale è ignorato.</p>}
              {cat === "fornitori" && <div className="flex items-center justify-between py-1.5 text-sm"><span className="text-slate-600">Fatture ricevute non abbinate <span className="text-xs text-slate-400">(automatico da Agenzia Entrate{d.ade_non_abbinate?.length ? `: ${d.ade_non_abbinate.slice(0, 4).map((x) => x.controparte).join(", ")}${d.ade_non_abbinate.length > 4 ? "…" : ""}` : ""})</span></span><span className="tabular-nums font-medium" data-testid="pdp-fatture-ricevute-auto">{eur(d.sezioni.fornitori["Fatture ricevute non abbinate (AdE)"])}</span></div>}
              {voci[cat].map((v) => (
                <div key={v} className="flex items-center gap-2 py-1.5 text-sm">
                  <span className="flex-1 text-slate-600">{v}{cat === "fornitori" && adeF[v] ? <span className="ml-1.5 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700" data-testid={`pdp-ade-${v.replace(/\W/g, "_")}`}>fatture {eur(adeF[v])}{parseFloat(valori[`${cat}|${v}`]) ? " + manuale" : ""}</span> : null}</span>
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
