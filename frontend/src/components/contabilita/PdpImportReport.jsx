import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { MESI, eur } from "./shared";

export const PdpImportReport = ({ esito, onClose }) => {
  if (!esito) return null;
  const mesi = [...esito].sort((a, b) => b.anno - a.anno || b.mese - a.mese);
  const nDiff = mesi.reduce((a, m) => a + (m.confronto || []).filter((r) => !r.ok).length, 0);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto" data-testid="pdp-import-report">
        <DialogHeader><DialogTitle>Import dai fogli Google — confronto foglio vs gestionale</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-600" data-testid="pdp-import-report-summary">
          {mesi.length} schede lette{mesi.some((m) => m.nuova_scheda) ? ` (nuove riconosciute: ${mesi.filter((m) => m.nuova_scheda).map((m) => `${MESI[m.mese]} ${m.anno}`).join(", ")})` : ""} ·{" "}
          {nDiff === 0 ? <span className="font-semibold text-emerald-700">tutte le voci coincidono</span> : <span className="font-semibold text-rose-700">{nDiff} voci con differenza</span>}
        </p>
        <div className="space-y-4">
          {mesi.map((m) => (
            <div key={`${m.anno}-${m.mese}`} className="rounded-lg border border-slate-200" data-testid={`pdp-import-mese-${m.anno}-${m.mese}`}>
              <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2 text-sm font-semibold">
                <span>{MESI[m.mese]} {m.anno}{m.nuova_scheda && <span className="ml-2 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] text-sky-800">nuova scheda</span>}</span>
                {m.errore ? <span className="text-rose-600">{m.errore}</span> : <span className="text-xs font-normal text-slate-500">{m.fatture_emesse_nuove + m.fatture_ricevute_nuove} fatture nuove · {m.corrispettivi_ade_nuovi} chiusure RT nuove</span>}
              </div>
              {!m.errore && (
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-[11px] uppercase text-slate-400"><th className="px-3 py-1">Voce</th><th className="px-3 py-1 text-right">Foglio</th><th className="px-3 py-1 text-right">Gestionale</th><th className="px-3 py-1 text-right">Differenza</th></tr></thead>
                  <tbody>
                    {(m.confronto || []).map((r, i) => (
                      <tr key={i} className={r.ok ? "" : "bg-rose-50"} data-testid={`pdp-import-riga-${r.ok ? "ok" : "diff"}`}>
                        <td className="px-3 py-1 text-slate-700">{r.voce}</td>
                        <td className="px-3 py-1 text-right tabular-nums">{eur(r.foglio)}</td>
                        <td className="px-3 py-1 text-right tabular-nums">{eur(r.gestionale)}</td>
                        <td className={`px-3 py-1 text-right font-semibold tabular-nums ${r.ok ? "text-emerald-600" : "text-rose-700"}`}>{r.ok ? "✓" : `${r.diff > 0 ? "+" : ""}${eur(r.diff)}`}</td>
                      </tr>
                    ))}
                    {!(m.confronto || []).length && <tr><td colSpan={4} className="px-3 py-2 text-xs text-slate-400">Nessuna voce confrontabile.</td></tr>}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};
