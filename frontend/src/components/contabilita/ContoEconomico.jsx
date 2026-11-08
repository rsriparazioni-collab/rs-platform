import { useCallback, useEffect, useState } from "react";
import { TrendingUp, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { PeriodoPicker, eur } from "./shared";

const MESI_BREVI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];

const Num = ({ label, value, tone = "", sub, testid }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-3" data-testid={testid}>
    <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
    <div className={`text-xl font-bold tabular-nums ${tone}`}>{value === null || value === undefined ? "—" : eur(value)}</div>
    {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
  </div>
);

const Riga = ({ label, value, bold, indent, testid }) => (
  <div className={`flex justify-between py-1 text-sm ${bold ? "font-semibold text-slate-900" : "text-slate-700"} ${indent ? "pl-4" : ""}`} data-testid={testid}>
    <span>{label}</span><span className="tabular-nums">{eur(value)}</span>
  </div>
);

const Classifica = ({ titolo, gruppi, categorie, onSet, testid, hint }) => {
  const [tutti, setTutti] = useState(false);
  const daFare = gruppi.filter((g) => !g.categoria);
  const lista = tutti ? gruppi : daFare;
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid={testid}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
        <div className="text-sm font-semibold">{titolo} {daFare.length > 0 && <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">{daFare.length} da classificare</span>}</div>
        <button type="button" onClick={() => setTutti(!tutti)} className="text-xs text-sky-700 hover:underline" data-testid={`${testid}-toggle`}>{tutti ? "Mostra solo da classificare" : `Mostra tutti (${gruppi.length})`}</button>
      </div>
      {hint && <p className="px-3 pt-2 text-[11px] text-slate-500">{hint}</p>}
      <div className="max-h-96 divide-y overflow-y-auto px-3 text-xs">
        {lista.length === 0 && <p className="py-3 text-slate-400">{gruppi.length ? "Tutto classificato ✓" : "Nessun movimento nel mese."}</p>}
        {lista.map((g) => (
          <div key={g.chiave} className={`flex flex-wrap items-center justify-between gap-2 py-1.5 ${!g.categoria ? "bg-amber-50/60" : ""}`} data-testid={`${testid}-riga-${g.chiave.replace(/\W+/g, "-")}`}>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-slate-800" title={g.nome}>{g.nome}</div>
              <div className="text-[10px] text-slate-400">{g.n} {g.n === 1 ? "movimento" : "movimenti"}{g.auto && " · riconosciuto in automatico"}{g.movimenti?.[0] && ` · es. ${g.movimenti[0].data.slice(5)} ${eur(g.movimenti[0].importo)}`}</div>
            </div>
            <b className="tabular-nums">{eur(g.totale)}</b>
            {g.fissa ? <span className="w-44 text-[11px] text-slate-500">{categorie[g.categoria]}</span> : (
              <select value={g.categoria || ""} onChange={(e) => onSet(g, e.target.value)} className={`h-7 w-44 rounded border px-1 text-[11px] ${!g.categoria ? "border-amber-400 bg-white" : "border-slate-200"}`} data-testid={`${testid}-sel-${g.chiave.replace(/\W+/g, "-")}`}>
                <option value="">— scegli —</option>
                {Object.entries(categorie).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export const ContoEconomico = ({ anno, mese, setAnno, setMese }) => {
  const [entita, setEntita] = useState("ditta");
  const [d, setD] = useState(null);
  const [conf, setConf] = useState([]);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api.get("/margine/conto-economico", { params: { entita, anno, mese } }).then((r) => { setD(r.data); setErr(""); }).catch((e) => setErr(apiError(e)));
    api.get("/margine/confronto", { params: { entita, anno, mese, n: 3 } }).then((r) => setConf(r.data)).catch(() => setConf([]));
  }, [entita, anno, mese]);
  useEffect(() => { load(); }, [load]);

  const setBanca = async (g, categoria) => {
    if (!categoria) return;
    try { await api.put("/margine/regola-banca", { entita, chiave: g.chiave, categoria, esempio: g.nome }); toast.success(`"${g.nome.slice(0, 30)}" → ${d.categorie.banca[categoria]} (vale per tutti i mesi)`); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const setForn = async (g, categoria) => {
    if (!categoria) return;
    try { await api.put("/margine/regola-fornitore", { centro_id: d.centro_id || entita, chiave: g.chiave, categoria, esempio: g.nome }); toast.success(`${g.nome.slice(0, 30)} → ${d.categorie.fornitore[categoria]} (vale per tutti i mesi)`); load(); } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-4" data-testid="conto-economico">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><TrendingUp className="h-5 w-5 text-emerald-600" /> Conto economico del mese</h2>
        <div className="flex items-center gap-2">
          <select value={entita} onChange={(e) => setEntita(e.target.value)} className="h-9 rounded-lg border border-slate-200 px-2 text-sm" data-testid="ce-entita"><option value="ditta">Ditta Enrico Mangani (Morbegno + Gravedona)</option><option value="srls">RS Riparazioni SRLS (Sondrio)</option></select>
          <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
        </div>
      </div>
      <p className="text-xs text-slate-500">Ogni euro ha una sola fonte: <b>banca</b> per ciò che non ha fattura (affitti, F24, stipendi), <b>fattura AdE</b> per ciò che ha fattura, <b>spese cassa</b> per i contanti senza fattura. I pagamenti in banca di una fattura e le spese cassa collegate a una fattura non vengono contati due volte.</p>
      {err && <p className="text-sm text-rose-600" data-testid="ce-errore">{err}</p>}
      {d && (
        <>
          {d.da_classificare > 0 && (
            <div className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900" data-testid="ce-da-classificare">
              <AlertTriangle className="h-4 w-4" /> <b>{eur(d.da_classificare)}</b> di movimenti ancora da classificare (sotto): non sono nel risultato finché non scegli la categoria. Si fa una volta sola per beneficiario/fornitore.
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Num label="Entrate" value={d.entrate.totale} tone="text-emerald-700" sub={`scontrini ${eur(d.entrate.scontrini)} + fatture ${eur(d.entrate.fatture_emesse)}`} testid="ce-entrate" />
            <Num label="Merce e ricambi" value={d.costi_variabili.merce} tone="text-rose-700" sub="fatture ricevute «Merce»" testid="ce-merce" />
            <Num label="Margine lordo" value={d.margine_lordo} tone="text-slate-900" sub={d.margine_lordo_pct !== null ? `${d.margine_lordo_pct}% delle entrate` : ""} testid="ce-margine" />
            <Num label="Costi fissi" value={d.costi_fissi.totale} tone="text-rose-700" sub="banca + utenze/servizi + contanti" testid="ce-fissi" />
            <Num label="Risultato" value={d.risultato} tone={d.risultato >= 0 ? "text-emerald-700" : "text-rose-700"} sub={d.passante ? `escluso passante ${eur(d.passante)}` : ""} testid="ce-risultato" />
          </div>
          {d.per_negozio.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2" data-testid="ce-per-negozio">
              {d.per_negozio.map((n) => (
                <div key={n.store_id} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="flex justify-between text-sm font-semibold"><span>{n.nome}</span><span className="text-xs font-normal text-slate-500">quota {n.quota_pct}% degli scontrini</span></div>
                  <Riga label="Entrate" value={n.entrate} /><Riga label="− Merce (stimata in quota)" value={n.merce} indent /><Riga label="Margine lordo" value={n.margine_lordo} bold /><Riga label="− Costi fissi (in quota)" value={n.costi_fissi} indent /><Riga label="Risultato" value={n.risultato} bold />
                </div>
              ))}
            </div>
          )}
          {conf.length > 1 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid="ce-confronto">
              <div className="border-b px-4 py-2 text-sm font-semibold">Andamento ultimi {conf.length} mesi</div>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-2 text-left">Voce</th>{conf.map((c) => <th key={`${c.anno}-${c.mese}`} className="px-4 py-2 text-right">{MESI_BREVI[c.mese - 1]} {c.anno}</th>)}</tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {[["Entrate", "entrate", ""], ["Merce e ricambi", "merce", "text-rose-700"], ["Margine lordo", "margine_lordo", "font-semibold"], ["Costi fissi", "costi_fissi", "text-rose-700"], ["Risultato", "risultato", "font-semibold"], ["Da classificare", "da_classificare", "text-amber-700"]].map(([l, k, cls]) => (
                    <tr key={k} data-testid={`ce-confronto-${k}`}><td className={`px-4 py-1.5 ${cls}`}>{l}</td>{conf.map((c) => <td key={`${c.anno}-${c.mese}`} className={`px-4 py-1.5 text-right tabular-nums ${cls} ${k === "risultato" ? (c[k] >= 0 ? "text-emerald-700" : "text-rose-700") : ""}`}>{eur(c[k])}{k === "margine_lordo" && c.margine_lordo_pct !== null && <span className="ml-1 text-[10px] font-normal text-slate-400">{c.margine_lordo_pct}%</span>}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <details className="rounded-xl border border-slate-200 bg-white" data-testid="ce-dettaglio">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">Da dove viene ogni numero</summary>
            <div className="grid gap-4 border-t px-4 py-3 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs font-semibold uppercase text-emerald-700">Entrate</div>
                {d.entrate.scontrini_per_negozio.map((s) => <Riga key={s.nome} label={`Scontrini ${s.nome} (corrispettivi)`} value={s.totale} />)}
                <Riga label="Fatture emesse (AdE)" value={d.entrate.fatture_emesse} />
                <Riga label="Totale entrate" value={d.entrate.totale} bold />
                <div className="mb-1 mt-3 text-xs font-semibold uppercase text-rose-700">Costi variabili</div>
                <Riga label="Merce e ricambi (fatture ricevute)" value={d.costi_variabili.merce} />
              </div>
              <div>
                <div className="mb-1 text-xs font-semibold uppercase text-rose-700">Costi fissi</div>
                <Riga label="Affitti (banca)" value={d.costi_fissi.affitto} /><Riga label="Tasse e contributi F24 (banca)" value={d.costi_fissi.tasse} /><Riga label="Stipendi (banca)" value={d.costi_fissi.stipendi} />
                <Riga label="Commissioni banca/POS (banca)" value={d.costi_fissi.commissioni} /><Riga label="Altri costi (banca)" value={d.costi_fissi.altro_costo} />
                <Riga label="Utenze (fatture)" value={d.costi_fissi.utenze} /><Riga label="Servizi (fatture)" value={d.costi_fissi.servizi} />
                <Riga label={`Spese contanti senza fattura (${d.spese_cassa_n})`} value={d.costi_fissi.spese_cassa} />
                <Riga label="Totale costi fissi" value={d.costi_fissi.totale} bold />
                <p className="mt-2 text-[11px] text-slate-500">Non contati (già altrove): {d.fatture_pagate_banca} pagamenti fattura in banca · spese cassa con fattura {eur(d.spese_cassa_con_fattura)} · passante {eur(d.passante)}{d.fatture_aperte ? ` · ${d.fatture_aperte} fatture ricevute senza pagamento trovato (vedi Banche & Fatture)` : ""}</p>
              </div>
            </div>
          </details>
          <div className="grid gap-3 lg:grid-cols-2">
            <Classifica titolo="Uscite banca per beneficiario" gruppi={d.banca} categorie={d.categorie.banca} onSet={setBanca} testid="ce-banca" hint="Affitti, F24 e stipendi si riconoscono spesso da soli. Scegli la categoria una volta: vale per tutti i mesi." />
            <Classifica titolo="Fornitori (fatture ricevute AdE)" gruppi={d.fornitori} categorie={d.categorie.fornitore} onSet={setForn} testid="ce-fornitori" hint="Merce/ricambi entra nel margine; utenze e servizi nei costi fissi; passante (bollette rivendute) non conta." />
          </div>
        </>
      )}
    </div>
  );
};
