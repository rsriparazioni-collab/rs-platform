import { useState } from "react";
import { toast } from "sonner";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { eur } from "./shared";

const NATURE = { imponibile: "Imponibile", esente: "Esente (N4)", non_imponibile: "Non imponibile (N3)", esclusa: "Esclusa (N1)", non_soggetta: "Non soggetta (N2)", regime_margine: "Margine (N5)", reverse_charge: "Reverse charge (N6)", iva_altro_stato: "IVA altro Stato (N7)", forfettario: "Forfettario", da_verificare: "Da verificare" };

/* Anteprima import AdE: colonne riconosciute, righe con duplicati/anomalie, scelta righe, conferma. */
export const AdeAnteprima = ({ anteprima, centroId, anno, mese, direzione, onClose, onDone }) => {
  const [righe, setRighe] = useState(anteprima.righe.map((r) => ({ ...r, sel: !r.duplicato })));
  const [busy, setBusy] = useState(false);
  const sel = righe.filter((r) => r.sel);
  const tot = (k) => sel.reduce((a, r) => a + (r[k] || 0), 0);
  const conferma = async () => {
    setBusy(true);
    try { const r = await api.post("/contabilita/pdp/fatture/conferma", { righe: sel }, { params: { centro_id: centroId, anno, mese, direzione } }); toast.success(`${r.data.importate} fatture ${direzione} importate${r.data.duplicate ? `, ${r.data.duplicate} già presenti` : ""}`); onDone(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto" data-testid="ade-anteprima">
        <DialogHeader><DialogTitle>Anteprima import fatture {direzione} — {anteprima.file}</DialogTitle></DialogHeader>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" data-testid="ade-anteprima-colonne">
          <span className="font-semibold text-slate-800">Colonne riconosciute:</span>{Object.entries(anteprima.colonne).map(([k, v]) => <span key={k}>{k} ← <code className="rounded bg-slate-100 px-1">{v}</code></span>)}
          {!anteprima.colonne.natura && <span className="text-amber-700">natura IVA non presente nel file: i documenti a IVA zero saranno "da verificare"</span>}
        </div>
        <p className="text-sm" data-testid="ade-anteprima-riepilogo">{anteprima.n} righe · <b className="text-emerald-700">{sel.length} da importare</b> · {anteprima.duplicati} già presenti (escluse) · {anteprima.fuori_mese} fuori mese · {anteprima.con_anomalie} con note — Totale selezionate: imponibile {eur(tot("imponibile"))} · IVA {eur(tot("imposta"))} · {eur(tot("totale"))}</p>
        <div className="max-h-[50vh] overflow-auto rounded border border-slate-200">
          <table className="w-full text-xs" data-testid="ade-anteprima-table">
            <thead className="sticky top-0 bg-slate-50 text-slate-500"><tr><th className="px-2 py-1"><input type="checkbox" checked={sel.length === righe.filter((r) => !r.duplicato).length} onChange={(e) => setRighe(righe.map((r) => ({ ...r, sel: !r.duplicato && e.target.checked })))} data-testid="ade-anteprima-sel-tutti" /></th><th className="px-2 py-1 text-left">Data</th><th className="px-2 py-1 text-left">Tipo</th><th className="px-2 py-1 text-left">Numero</th><th className="px-2 py-1 text-left">Controparte</th><th className="px-2 py-1 text-right">Imponibile</th><th className="px-2 py-1 text-right">IVA</th><th className="px-2 py-1 text-right">Totale</th><th className="px-2 py-1 text-left">Natura IVA</th><th className="px-2 py-1 text-left">Note</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {righe.map((r, i) => (
                <tr key={i} className={r.duplicato ? "bg-slate-50 text-slate-400" : r.note.length ? "bg-amber-50" : ""} data-testid={`ade-anteprima-riga-${r.duplicato ? "dup" : "ok"}`}>
                  <td className="px-2 py-1"><input type="checkbox" disabled={r.duplicato} checked={r.sel} onChange={(e) => setRighe(righe.map((x, j) => (j === i ? { ...x, sel: e.target.checked } : x)))} /></td>
                  <td className="px-2 py-1">{r.data ? r.data.split("-").reverse().join("/") : "—"}</td><td className="px-2 py-1">{r.tipo}</td><td className="px-2 py-1">{r.numero}</td><td className="max-w-[200px] truncate px-2 py-1">{r.controparte}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{eur(r.imponibile)}</td><td className="px-2 py-1 text-right tabular-nums">{eur(r.imposta)}</td><td className="px-2 py-1 text-right font-medium tabular-nums">{eur(r.totale)}</td>
                  <td className="px-2 py-1">{!r.duplicato && Math.abs(r.imposta) < 0.005 && Math.abs(r.imponibile) >= 0.005 ? (
                    <select value={r.natura_iva} onChange={(e) => setRighe(righe.map((x, j) => (j === i ? { ...x, natura_iva: e.target.value } : x)))} className={`h-6 rounded border px-1 text-[11px] ${r.natura_iva === "da_verificare" ? "border-rose-300 bg-rose-50" : "border-slate-300"}`} data-testid={`ade-anteprima-natura-${i}`}>{Object.entries(NATURE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                  ) : <span className="text-slate-400">{NATURE[r.natura_iva] || r.natura_iva}</span>}</td>
                  <td className="px-2 py-1 text-amber-800">{r.duplicato ? "già importata" : r.note.join(", ")}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose} data-testid="ade-anteprima-annulla">Annulla</Button><Button onClick={conferma} disabled={busy || !sel.length} data-testid="ade-anteprima-conferma">{busy ? "Importo…" : `Importa ${sel.length} fatture`}</Button></div>
      </DialogContent>
    </Dialog>
  );
};
