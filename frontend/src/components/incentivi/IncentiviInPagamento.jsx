import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, Undo2, Table } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { eur } from "./IncentiviCalcolo";

const SHEET_DEFAULT = "1bYRn-pAzYXPI1BCnWph8XIMGXhfHsEZz6o_22etuG1M";

export const IncentiviInPagamento = ({ mese, meta }) => {
  const [competenza, setCompetenza] = useState(() => { const [y, m] = mese.split("-").map(Number); const d = new Date(y, m - 2, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; });
  const [prev, setPrev] = useState(null);
  const [sel, setSel] = useState({});
  const [importi, setImporti] = useState({});
  const [caricate, setCaricate] = useState(null);
  const [manuale, setManuale] = useState({ fonte: "eolo", store_id: "", user_id: "", importo: "", descrizione: "", data_contratto: "" });
  const [foglio] = useState({ sheet_id: SHEET_DEFAULT, gid: "" });
  const [anteprima, setAnteprima] = useState(null);
  const [busyFoglio, setBusyFoglio] = useState(false);

  const loadCaricate = useCallback(() => api.get(`/incentivi/provvigioni?mese=${mese}`).then((r) => setCaricate(r.data)).catch(() => {}), [mese]);
  const loadPrev = useCallback(() => api.get(`/incentivi/previste?mese=${competenza}`).then((r) => { setPrev(r.data); setSel({}); setImporti({}); }).catch((e) => toast.error(apiError(e))), [competenza]);
  useEffect(() => { loadCaricate(); }, [loadCaricate]);
  useEffect(() => { loadPrev(); }, [loadPrev]);

  const confermaSel = async () => {
    const righe = prev.righe.filter((r) => sel[r.ref_id] && !r.gia_caricata).map((r) => ({ ...r, importo: parseFloat(importi[r.ref_id] ?? r.importo) || 0 }));
    if (!righe.length) return toast.error("Seleziona almeno un contratto");
    try { const res = await api.post("/incentivi/conferma", { mese, righe }); toast.success(`${res.data.inseriti} provvigioni caricate in pagamento ${mese}`); loadPrev(); loadCaricate(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const addManuale = async () => {
    if (!manuale.importo) return toast.error("Importo mancante");
    try { await api.post("/incentivi/conferma", { mese, righe: [{ ...manuale, importo: parseFloat(manuale.importo), sezione: "manuale" }] }); toast.success("Riga aggiunta"); setManuale({ ...manuale, importo: "", descrizione: "" }); loadCaricate(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const storna = async (p) => {
    const m = window.prompt("Mese in cui compensare lo storno (YYYY-MM)", mese);
    if (!m) return;
    try { await api.post("/incentivi/storno", { provvigione_id: p.id, mese: m }); toast.success("Storno registrato"); loadCaricate(); } catch (e) { toast.error(apiError(e)); }
  };
  const elimina = async (p) => { if (!window.confirm("Eliminare la riga?")) return; try { await api.delete(`/incentivi/provvigioni/${p.id}`); loadCaricate(); } catch (e) { toast.error(apiError(e)); } };
  const importa = async (ant) => {
    setBusyFoglio(true);
    try { const r = await api.post("/incentivi/import-foglio", { ...foglio, mese, anteprima: ant }); if (ant) setAnteprima(r.data); else { toast.success(`${r.data.importate} righe caricate per ${mese}`); setAnteprima(null); loadCaricate(); } }
    catch (e) { toast.error(apiError(e)); }
    finally { setBusyFoglio(false); }
  };

  return (
    <div className="space-y-6" data-testid="inc-pagamento">
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-900">Contratti del gestionale da confermare → pagamento {mese}</h3>
          <div className="flex items-center gap-2 text-sm"><span className="text-slate-500">Competenza</span><input type="month" value={competenza} onChange={(e) => setCompetenza(e.target.value)} className="h-9 rounded-md border border-slate-200 px-2" data-testid="inc-competenza" /></div>
        </div>
        {prev && <p className="mt-1 text-xs text-slate-500">EOLO totali nel mese: {prev.n_eolo_totale} → soglia {prev.soglia_eolo ? `Da ${prev.soglia_eolo}` : "non raggiunta (min 5)"}. Energia: {eur(prev.righe.find((r) => r.fonte === "energia")?.importo ?? 25)} a riga (metà acquisizione / metà lavorazione se persone diverse). Modifica l'importo se diverso dalla fattura.</p>}
        <div className="mt-3 max-h-80 overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500"><tr><th className="px-2 py-1"></th><th className="px-2 py-1">Fonte</th><th className="px-2 py-1">Negozio</th><th className="px-2 py-1">Persona</th><th className="px-2 py-1">Data</th><th className="px-2 py-1">Descrizione</th><th className="px-2 py-1">Importo €</th><th className="px-2 py-1">Note</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {(prev?.righe || []).map((r) => (
                <tr key={r.ref_id} className={r.gia_caricata ? "opacity-50" : ""} data-testid={`inc-prev-${r.ref_id}`}>
                  <td className="px-2 py-1"><input type="checkbox" disabled={r.gia_caricata} checked={!!sel[r.ref_id]} onChange={(e) => setSel({ ...sel, [r.ref_id]: e.target.checked })} data-testid={`inc-prev-check-${r.ref_id}`} /></td>
                  <td className="px-2 py-1 uppercase text-xs font-semibold">{r.fonte}</td><td className="px-2 py-1">{r.negozio}</td><td className="px-2 py-1">{r.persona}</td><td className="px-2 py-1">{r.data_contratto}</td><td className="px-2 py-1">{r.descrizione}</td>
                  <td className="px-2 py-1"><Input type="number" step="0.5" className="h-8 w-24" value={importi[r.ref_id] ?? r.importo} onChange={(e) => setImporti({ ...importi, [r.ref_id]: e.target.value })} disabled={r.gia_caricata} /></td>
                  <td className="px-2 py-1 text-xs text-amber-700">{r.gia_caricata ? "già caricata" : r.anomalia}{r.fonte === "energia" && !r.gia_caricata && <span className={`ml-1 rounded px-1 ${r.incassato ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>{r.incassato ? "incassata (Compensi)" : "non ancora incassata"}</span>}</td>
                </tr>))}
              {prev && !prev.righe.length && <tr><td colSpan={8} className="px-2 py-4 text-center text-slate-400">Nessun contratto EOLO/energia nel mese di competenza</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setSel(Object.fromEntries((prev?.righe || []).filter((r) => !r.gia_caricata).map((r) => [r.ref_id, true])))} data-testid="inc-prev-tutti">Seleziona tutti</Button>
          <Button size="sm" variant="outline" onClick={() => setSel(Object.fromEntries((prev?.righe || []).filter((r) => !r.gia_caricata && (r.fonte !== "energia" || r.incassato)).map((r) => [r.ref_id, true])))} data-testid="inc-prev-incassati">Seleziona solo incassati</Button>
          <Button size="sm" onClick={confermaSel} data-testid="inc-conferma">Carica selezionati in pagamento {mese}</Button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="font-semibold text-slate-900">Riga manuale (fattura/estratto conto fornitore)</h3>
        <div className="mt-2 grid gap-2 md:grid-cols-6">
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={manuale.fonte} onChange={(e) => setManuale({ ...manuale, fonte: e.target.value })} data-testid="inc-man-fonte"><option value="eolo">EOLO</option><option value="energia">Energia</option></select>
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={manuale.store_id} onChange={(e) => setManuale({ ...manuale, store_id: e.target.value })} data-testid="inc-man-store"><option value="">Negozio…</option>{meta.stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}</select>
          <select className="h-9 rounded-md border border-slate-200 px-2 text-sm" value={manuale.user_id} onChange={(e) => setManuale({ ...manuale, user_id: e.target.value })} data-testid="inc-man-user"><option value="">Persona (opz.)</option>{meta.users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>
          <Input type="date" value={manuale.data_contratto} onChange={(e) => setManuale({ ...manuale, data_contratto: e.target.value })} />
          <Input placeholder="Descrizione" value={manuale.descrizione} onChange={(e) => setManuale({ ...manuale, descrizione: e.target.value })} data-testid="inc-man-desc" />
          <div className="flex gap-2"><Input type="number" step="0.5" placeholder="€" value={manuale.importo} onChange={(e) => setManuale({ ...manuale, importo: e.target.value })} data-testid="inc-man-importo" /><Button size="sm" onClick={addManuale} data-testid="inc-man-add"><Plus className="h-4 w-4" /></Button></div>
        </div>
      </section>

      <section className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4" data-testid="inc-foglio-box">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="flex items-center gap-2 font-semibold text-slate-900"><Table className="h-4 w-4" /> Compensi EOLO dal foglio Google · {mese}</h3>
            <p className="text-xs text-slate-500">Un click: il gestionale legge la scheda del mese precedente (fatturato EOLO) e la carica nella gara di {mese}, mese in cui viene pagato. Le righe già caricate vengono saltate.</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => importa(true)} disabled={busyFoglio} data-testid="inc-foglio-anteprima">{busyFoglio ? "Leggo il foglio..." : `Carica fatturato EOLO del mese prima → pagato ${mese}`}</Button>
            {anteprima && anteprima.nuove > 0 && <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => importa(false)} disabled={busyFoglio} data-testid="inc-foglio-importa">Conferma {anteprima.nuove} righe ({eur(anteprima.totale_nuove)})</Button>}
          </div>
        </div>
        {anteprima && (
          <div className="mt-3 text-xs" data-testid="inc-foglio-preview">
            {anteprima.nuove === 0 ? <p className="font-medium text-slate-700">Tutto già caricato per {mese}: nessuna riga nuova.</p> : (
              <div className="flex flex-wrap gap-2">{anteprima.per_negozio.map((n) => <span key={n.negozio} className="rounded-full border border-slate-200 bg-white px-2 py-0.5">{n.negozio} · {n.n} · <b>{eur(n.totale)}</b></span>)}</div>
            )}
            {anteprima.righe.some((r) => r.anomalia) && <p className="mt-1 text-amber-700">Negozi non riconosciuti: {[...new Set(anteprima.righe.filter((r) => r.anomalia).map((r) => r.negozio_nome))].join(", ")} → controlla il nome in Gestione Negozi.</p>}
            <details className="mt-1"><summary className="cursor-pointer text-slate-500">Vedi tutte le righe ({anteprima.righe.length})</summary>
              <div className="mt-1 max-h-48 overflow-auto">{anteprima.righe.map((r) => <div key={r.ref_id} className={r.duplicato ? "text-slate-400" : ""}>{r.negozio_nome} · {r.sezione} · {r.data_contratto} · {eur(r.importo)} {r.duplicato && "(già caricata)"}</div>)}</div>
            </details>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="font-semibold text-slate-900">Provvigioni in pagamento {mese} · totale {eur(caricate?.totale)}</h3>
        <div className="mt-2 max-h-96 overflow-auto">
          <table className="w-full text-sm" data-testid="inc-caricate">
            <thead className="text-left text-xs uppercase text-slate-500"><tr><th className="px-2 py-1">Fonte</th><th className="px-2 py-1">Negozio</th><th className="px-2 py-1">Persona</th><th className="px-2 py-1">Data</th><th className="px-2 py-1">Descrizione</th><th className="px-2 py-1">Origine</th><th className="px-2 py-1 text-right">Importo</th><th></th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {(caricate?.righe || []).map((p) => (
                <tr key={p.id} className={p.stato === "stornata" ? "text-red-600" : ""} data-testid={`inc-provv-${p.id}`}>
                  <td className="px-2 py-1 uppercase text-xs font-semibold">{p.fonte}</td><td className="px-2 py-1">{p.negozio}</td><td className="px-2 py-1">{p.persona}</td><td className="px-2 py-1">{p.data_contratto}</td><td className="px-2 py-1">{p.descrizione}</td><td className="px-2 py-1 text-xs">{p.origine}/{p.sezione}</td>
                  <td className="px-2 py-1 text-right">{eur(p.importo)}</td>
                  <td className="px-2 py-1 text-right whitespace-nowrap">{p.stato === "confermata" && <button className="mr-2 text-slate-500 hover:text-amber-600" title="Storna" onClick={() => storna(p)} data-testid={`inc-storna-${p.id}`}><Undo2 className="h-4 w-4" /></button>}<button className="text-slate-400 hover:text-red-600" onClick={() => elimina(p)} data-testid={`inc-del-${p.id}`}><Trash2 className="h-4 w-4" /></button></td>
                </tr>))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
