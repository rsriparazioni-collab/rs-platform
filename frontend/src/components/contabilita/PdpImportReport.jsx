import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Pencil } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { GiornoDialog } from "./GiornoDialog";
import { MESI, eur } from "./shared";

export const PdpImportReport = ({ esito, onClose, onChanged }) => {
  const [aperta, setAperta] = useState(null);
  const [giorno, setGiorno] = useState(null);
  const [allineando, setAllineando] = useState(false);
  if (!esito) return null;
  const allinea = async (r) => {
    const mancanti = r.giorni.filter((g) => g.scontrini === 0 && g.foglio > 0);
    if (!mancanti.length) return;
    setAllineando(true);
    try { const x = await api.post("/contabilita/pdp/allinea-giorni", { store_id: r.store_id, giorni: mancanti.map((g) => ({ data: g.data, foglio: g.foglio })) }); toast.success(`${x.data.creati.length} giorni compilati dal foglio${x.data.saltati.length ? ` · ${x.data.saltati.length} già presenti` : ""}`); onChanged?.(); }
    catch (e) { toast.error(apiError(e)); } finally { setAllineando(false); }
  };
  const mesi = [...esito].sort((a, b) => b.anno - a.anno || b.mese - a.mese);
  const nDiff = mesi.reduce((a, m) => a + (m.confronto || []).filter((r) => !r.ok).length, 0);
  return (
    <>
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
                              <div className="mb-1.5 flex items-center justify-between gap-2">
                                <span className="text-[11px] text-slate-500">Clicca la matita per aprire e correggere il corrispettivo del giorno.</span>
                                {r.giorni.some((g) => g.scontrini === 0 && g.foglio > 0) && <Button size="sm" variant="outline" className="h-7 text-xs" disabled={allineando} onClick={(e) => { e.stopPropagation(); allinea(r); }} data-testid="pdp-import-allinea">{allineando ? "Compilo…" : `Usa il valore del foglio (${r.giorni.filter((g) => g.scontrini === 0 && g.foglio > 0).length} giorni mancanti)`}</Button>}
                              </div>
                              <table className="w-full text-xs">
                                <thead><tr className="text-left text-[10px] uppercase text-slate-400"><th className="py-0.5">Giorno</th><th className="py-0.5 text-right">Scontrini inseriti</th><th className="py-0.5 text-right">Foglio (RT)</th><th className="py-0.5 text-right">Differenza</th><th className="w-8" /></tr></thead>
                                <tbody>
                                  {r.giorni.map((g) => (
                                    <tr key={g.data} className="border-t border-slate-100" data-testid={`pdp-import-giorno-${g.data}`}>
                                      <td className="py-0.5">{g.data.slice(8, 10)}/{g.data.slice(5, 7)}</td>
                                      <td className="py-0.5 text-right tabular-nums">{eur(g.scontrini)}</td>
                                      <td className="py-0.5 text-right tabular-nums">{g.foglio == null ? <span className="text-slate-400">non nel foglio</span> : eur(g.foglio)}</td>
                                      <td className={`py-0.5 text-right font-semibold tabular-nums ${g.diff == null ? "text-slate-400" : "text-rose-700"}`}>{g.diff == null ? "—" : `${g.diff > 0 ? "+" : ""}${eur(g.diff)}`}</td>
                                      <td className="py-0.5 text-right"><button onClick={(e) => { e.stopPropagation(); setGiorno({ storeId: r.store_id, data: g.data }); }} className="text-slate-400 hover:text-sky-700" title="Apri corrispettivo" data-testid={`pdp-import-apri-${g.data}`}><Pencil className="h-3.5 w-3.5" /></button></td>
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
    {giorno && <GiornoDialogLoader storeId={giorno.storeId} data={giorno.data} onClose={() => setGiorno(null)} onSaved={() => { setGiorno(null); onChanged?.(); }} />}
    </>
  );
};

const GiornoDialogLoader = ({ storeId, data, onClose, onSaved }) => {
  const [riga, setRiga] = useState(null);
  useEffect(() => {
    const [anno, mese] = data.split("-");
    api.get("/contabilita/corrispettivi", { params: { store_id: storeId, anno, mese } }).then((r) => setRiga(r.data.righe.find((x) => x.data === data) || { data, vuoto: true })).catch((e) => { toast.error(apiError(e)); onClose(); });
  }, [storeId, data, onClose]);
  if (!riga) return null;
  return <GiornoDialog storeId={storeId} riga={riga} onClose={onClose} onSaved={onSaved} />;
};
