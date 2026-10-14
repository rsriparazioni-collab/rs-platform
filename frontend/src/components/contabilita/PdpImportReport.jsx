import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { MESI, eur } from "./shared";

export const PdpImportReport = ({ esito, onClose }) => {
  const [aperta, setAperta] = useState(null);
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
          <span className="ml-2 text-xs text-slate-400">· ogni notte alle 2:00 il foglio viene riletto e le nuove differenze arrivano su WhatsApp all'amministrazione</span>
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
                    {(m.confronto || []).map((r, i) => {
                      const key = `${m.anno}-${m.mese}-${i}`;
                      const cliccabile = !r.ok && r.giorni?.length > 0;
                      return [
                        <tr key={key} onClick={() => cliccabile && setAperta(aperta === key ? null : key)} className={`${r.ok ? "" : "bg-rose-50"} ${cliccabile ? "cursor-pointer hover:bg-rose-100" : ""}`} data-testid={`pdp-import-riga-${r.ok ? "ok" : "diff"}`} title={cliccabile ? "Clicca per vedere i giorni discordanti" : undefined}>
                          <td className="px-3 py-1 text-slate-700">{cliccabile && (aperta === key ? <ChevronDown className="mr-1 inline h-3.5 w-3.5" /> : <ChevronRight className="mr-1 inline h-3.5 w-3.5" />)}{r.voce}{cliccabile && <span className="ml-1.5 text-[10px] text-rose-600">{r.giorni.length} giorni</span>}</td>
                          <td className="px-3 py-1 text-right tabular-nums">{eur(r.foglio)}</td>
                          <td className="px-3 py-1 text-right tabular-nums">{eur(r.gestionale)}</td>
                          <td className={`px-3 py-1 text-right font-semibold tabular-nums ${r.ok ? "text-emerald-600" : "text-rose-700"}`}>{r.ok ? "✓" : `${r.diff > 0 ? "+" : ""}${eur(r.diff)}`}</td>
                        </tr>,
                        aperta === key && (
                          <tr key={`${key}-g`} data-testid="pdp-import-giorni">
                            <td colSpan={4} className="bg-white px-3 py-2">
                              <table className="w-full text-xs">
                                <thead><tr className="text-left text-[10px] uppercase text-slate-400"><th className="py-0.5">Giorno</th><th className="py-0.5 text-right">Scontrini inseriti</th><th className="py-0.5 text-right">Foglio (RT)</th><th className="py-0.5 text-right">Differenza</th></tr></thead>
                                <tbody>
                                  {r.giorni.map((g) => (
                                    <tr key={g.data} className="border-t border-slate-100" data-testid={`pdp-import-giorno-${g.data}`}>
                                      <td className="py-0.5">{g.data.slice(8, 10)}/{g.data.slice(5, 7)}</td>
                                      <td className="py-0.5 text-right tabular-nums">{eur(g.scontrini)}</td>
                                      <td className="py-0.5 text-right tabular-nums">{g.foglio == null ? <span className="text-slate-400">non nel foglio</span> : eur(g.foglio)}</td>
                                      <td className={`py-0.5 text-right font-semibold tabular-nums ${g.diff == null ? "text-slate-400" : "text-rose-700"}`}>{g.diff == null ? "—" : `${g.diff > 0 ? "+" : ""}${eur(g.diff)}`}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        ),
                      ];
                    })}
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
