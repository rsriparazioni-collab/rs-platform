import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { RefreshCw, ExternalLink } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { MESI, PeriodoPicker, eur } from "./shared";

const SHEET_URL = "https://docs.google.com/spreadsheets/d/1aVjFCxg-Gm3zNQNcEE-Jq-WkTaIluLzlLRXFPCd82hw/edit";
const GRUPPO = { entrate: ["Entrate", "bg-emerald-50 text-emerald-900"], spese_fisse: ["Spese fisse", "bg-rose-50 text-rose-900"], spese_semifisse: ["Spese semi fisse modificabili", "bg-amber-50 text-amber-900"] };
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const n0 = (v) => (v ? eur(v) : <span className="text-slate-300">—</span>);
const ESCLUSI = ["tirano", "sondalo"];
const SEPARATO = "sondrio";

const Griglia = ({ titolo, negozi, p, d, testid }) => {
  if (!negozi.length) return null;
  const tot = Object.fromEntries(p.colonne.map((c) => [c.key, negozi.reduce((a, n) => a + (n.valori[c.key] || 0), 0)]));
  const totE = negozi.reduce((a, n) => a + n.tot_entrate, 0);
  const totS = negozi.reduce((a, n) => a + n.tot_spese, 0);
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid={testid}>
      <p className="border-b border-slate-100 px-3 py-2 text-sm font-semibold text-slate-800">{titolo}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide">
            <th className="px-3 py-1.5" />
            {Object.entries(GRUPPO).map(([g, [l, cls]]) => { const n = p.colonne.filter((c) => c.gruppo === g).length; return n ? <th key={g} colSpan={n} className={`px-3 py-1.5 text-center ${cls}`}>{l}</th> : null; })}
            <th className="px-3 py-1.5 text-center bg-slate-100 text-slate-700" colSpan={3}>Totali</th>
          </tr>
          <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2">Negozio</th>
            {p.colonne.map((c) => <th key={c.key} className="px-3 py-2 text-right">{c.label}</th>)}
            <th className="px-3 py-2 text-right">Entrate</th><th className="px-3 py-2 text-right">Spese</th><th className="px-3 py-2 text-right">Risultato</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {negozi.map((n) => {
            const g = d.gestionale_corrispettivi[n.nome.toLowerCase()];
            return (
              <tr key={n.nome} data-testid={`pdp-specchio-riga-${n.nome.toLowerCase()}`}>
                <td className="px-3 py-2 font-medium text-slate-900">{cap(n.nome)}</td>
                {p.colonne.map((c, i) => <td key={c.key} className="px-3 py-2 text-right tabular-nums">{n0(n.valori[c.key])}{i === 0 && g != null && Math.abs(g - (n.valori[c.key] || 0)) >= 1 && <span className="block text-[10px] text-amber-600" title="Corrispettivi inseriti nel gestionale">gest. {eur(g)}</span>}</td>)}
                <td className="px-3 py-2 text-right font-semibold tabular-nums text-emerald-700">{eur(n.tot_entrate)}</td>
                <td className="px-3 py-2 text-right font-semibold tabular-nums text-rose-700">{eur(n.tot_spese)}</td>
                <td className={`px-3 py-2 text-right font-bold tabular-nums ${n.risultato >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{eur(n.risultato)}</td>
              </tr>
            );
          })}
        </tbody>
        {negozi.length > 1 && (
          <tfoot className="bg-slate-50 font-semibold">
            <tr data-testid={`${testid}-totali`}><td className="px-3 py-2">Fatturato</td>{p.colonne.map((c) => <td key={c.key} className="px-3 py-2 text-right tabular-nums">{n0(tot[c.key])}</td>)}
              <td className="px-3 py-2 text-right text-emerald-700">{eur(totE)}</td><td className="px-3 py-2 text-right text-rose-700">{eur(totS)}</td><td className={`px-3 py-2 text-right ${totE - totS >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{eur(totE - totS)}</td></tr>
          </tfoot>
        )}
      </table>
    </div>
  );
};

const Dettaglio = ({ titolo, righe, cols, testid }) => (
  <details className="rounded-xl border border-slate-200 bg-white" data-testid={testid}>
    <summary className="cursor-pointer px-4 py-2.5 text-sm font-semibold text-slate-900">{titolo} <span className="text-xs font-normal text-slate-500">({righe.length} righe · {eur(righe.reduce((a, r) => a + (r.totale || 0), 0))})</span></summary>
    <div className="overflow-x-auto border-t border-slate-100">
      <table className="w-full text-xs"><thead className="bg-slate-50 text-left uppercase tracking-wide text-slate-500"><tr>{cols.map(([k, l]) => <th key={k} className={`px-3 py-1.5 ${["imponibile", "imposta", "totale"].includes(k) ? "text-right" : ""}`}>{l}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-50">{righe.map((r, i) => <tr key={i}>{cols.map(([k]) => <td key={k} className={`px-3 py-1 ${["imponibile", "imposta", "totale"].includes(k) ? "text-right tabular-nums" : ""}`}>{["imponibile", "imposta", "totale"].includes(k) ? eur(r[k]) : r[k]}</td>)}</tr>)}</tbody></table>
    </div>
  </details>
);

export const PdpSpecchio = ({ anno, mese, setAnno, setMese }) => {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get("/contabilita/pdp-specchio", { params: { anno, mese } }).then((r) => setD(r.data)).catch((e) => toast.error(apiError(e))), [anno, mese]);
  useEffect(() => { load(); }, [load]);
  const carica = async () => { setBusy(true); try { const r = await api.post("/contabilita/pdp-specchio/carica"); const ok = r.data.esito.filter((e) => !e.errore); toast.success(`Foglio PDP letto: ${ok.length} mesi aggiornati`); load(); } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); } };
  if (!d) return null;
  const p = d.dati;
  return (
    <div className="space-y-4" data-testid="pdp-specchio">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <PeriodoPicker anno={anno} mese={mese} setAnno={setAnno} setMese={setMese} />
          {p?.at && <span className="text-xs text-slate-500" data-testid="pdp-specchio-at">letto dal foglio il {new Date(p.at).toLocaleString("it-IT")}</span>}
        </div>
        <div className="flex gap-2">
          <a href={SHEET_URL} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 hover:bg-slate-50" data-testid="pdp-specchio-apri-foglio"><ExternalLink className="h-4 w-4" /> Apri il foglio</a>
          <Button size="sm" onClick={carica} disabled={busy} className="gap-1.5" data-testid="pdp-specchio-carica"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /> {busy ? "Leggo il foglio…" : "Aggiorna dal foglio PDP"}</Button>
        </div>
      </div>
      {!p ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500" data-testid="pdp-specchio-vuoto">Nessuna scheda "{MESI[mese].slice(0, 3).toLowerCase()}{String(anno).slice(2)}" trovata nel foglio per {MESI[mese]} {anno}. Premi "Aggiorna dal foglio PDP" dopo averla creata.</p> : (
        <>
          <Griglia titolo="Negozi RS (Morbegno + Gravedona)" negozi={p.negozi.filter((n) => !ESCLUSI.includes(n.nome.toLowerCase()) && n.nome.toLowerCase() !== SEPARATO)} p={p} d={d} testid="pdp-specchio-griglia" />
          <Griglia titolo="Sondrio (a parte)" negozi={p.negozi.filter((n) => n.nome.toLowerCase() === SEPARATO)} p={p} d={d} testid="pdp-specchio-griglia-sondrio" />

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="pdp-specchio-ade">
            {[["Totale RT + fatture (AdE)", p.ade?.totale, "text-slate-900"], ["Corrispettivi RT (AdE)", p.ade?.corrispettivi, "text-emerald-700"], ["Fatture emesse (AdE)", p.ade?.fatture_emesse, "text-emerald-700"], ["Fatture ricevute (AdE)", p.ade?.fatture_ricevute, "text-rose-700"], ["Fornitori", p.tot_fornitori, "text-rose-700"], ["Guadagno", p.guadagno, p.guadagno >= 0 ? "text-emerald-700" : "text-rose-700"]].map(([l, v, cls]) => (
              <div key={l} className="rounded-xl border border-slate-200 bg-white p-3"><p className="text-[11px] uppercase tracking-wide text-slate-500">{l}</p><p className={`mt-1 text-lg font-semibold tabular-nums ${cls}`}>{v == null ? "—" : eur(v)}</p></div>
            ))}
          </div>
          {p.iva != null && <p className="text-xs text-slate-500">IVA indicata nel foglio: <b>{eur(p.iva)}</b></p>}

          {p.fornitori?.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="pdp-specchio-fornitori">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Fornitori del mese</p>
              <div className="flex flex-wrap gap-2">{p.fornitori.map((f, i) => <span key={`${f.nome}-${i}`} className={`rounded-lg border px-2.5 py-1 text-xs ${f.importo ? "border-slate-200 bg-slate-50 text-slate-800" : "border-dashed border-slate-200 text-slate-400"}`}>{f.nome} <b className="tabular-nums">{f.importo ? eur(f.importo) : "—"}</b></span>)}</div>
            </div>
          )}

          <Dettaglio titolo="Corrispettivi RT" righe={p.corrispettivi} cols={[["data", "Data"], ["negozio", "Negozio"], ["matricola", "Matricola"], ["imponibile", "Imponibile"], ["imposta", "IVA"], ["totale", "Totale"]]} testid="pdp-specchio-corrispettivi" />
          <Dettaglio titolo="Fatture emesse" righe={p.emesse} cols={[["data", "Data"], ["numero", "Numero"], ["controparte", "Cliente"], ["imponibile", "Imponibile"], ["imposta", "IVA"], ["totale", "Totale"]]} testid="pdp-specchio-emesse" />
          <Dettaglio titolo="Fatture ricevute" righe={p.ricevute} cols={[["numero", "Numero"], ["controparte", "Fornitore"], ["imponibile", "Imponibile"], ["imposta", "IVA"], ["totale", "Totale"]]} testid="pdp-specchio-ricevute" />
        </>
      )}
    </div>
  );
};
