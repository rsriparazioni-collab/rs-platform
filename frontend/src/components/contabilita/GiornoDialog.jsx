import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Num, eur } from "./shared";

const CAMPI = [["riparazioni", "Riparazioni"], ["merce", "Merce"], ["art74", "Art. 74"], ["contanti", "Contanti"], ["pos", "POS"], ["versati", "Versati"]];

export const GiornoDialog = ({ storeId, riga, onClose, onSaved }) => {
  const [f, setF] = useState({ riparazioni: riga.riparazioni || "", merce: riga.merce || "", art74: riga.art74 || "", contanti: riga.contanti || "", pos: riga.pos || "", versati: riga.versati || "", note: riga.note || "", fatture_dettaglio: riga.fatture_dettaglio || [] });
  const [saving, setSaving] = useState(false);
  const n = (k) => parseFloat(f[k]) || 0;
  const fatture = f.fatture_dettaglio.reduce((a, x) => a + (parseFloat(x.importo) || 0), 0);
  const totale = n("contanti") + n("pos") + fatture;
  const scontrini = n("riparazioni") + n("merce") + n("art74");
  const incassato = n("contanti") + n("pos");
  const setFatt = (i, k, v) => setF({ ...f, fatture_dettaglio: f.fatture_dettaglio.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  const salva = async () => {
    setSaving(true);
    try { await api.put(`/contabilita/corrispettivi/${storeId}/${riga.data}`, { ...f, riparazioni: n("riparazioni"), merce: n("merce"), art74: n("art74"), contanti: n("contanti"), pos: n("pos"), versati: n("versati"), fatture }); toast.success("Corrispettivo salvato"); onSaved(); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const elimina = async () => {
    try { await api.delete(`/contabilita/corrispettivi/${storeId}/${riga.data}`); toast.success("Giorno eliminato"); onSaved(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="giorno-dialog">
        <DialogHeader><DialogTitle>Corrispettivo del {riga.data.split("-").reverse().join("/")}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {CAMPI.map(([k, l]) => <label key={k} className="text-xs text-slate-500">{l}<Num value={f[k]} onChange={(v) => setF({ ...f, [k]: v })} testid={`giorno-${k}`} /></label>)}
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase text-slate-500">Fatture ({eur(fatture)})</p>
            <Button size="sm" variant="ghost" onClick={() => setF({ ...f, fatture_dettaglio: [...f.fatture_dettaglio, { numero: "", importo: "", pagamento: "pos" }] })} data-testid="giorno-add-fattura">+ fattura</Button></div>
          {f.fatture_dettaglio.map((x, i) => (
            <div key={i} className="mt-2 grid grid-cols-[1fr_1fr_1fr_auto] items-center gap-2">
              <Input placeholder="N° 133/A" value={x.numero} onChange={(e) => setFatt(i, "numero", e.target.value)} className="h-8" data-testid={`fattura-numero-${i}`} />
              <Num value={x.importo} onChange={(v) => setFatt(i, "importo", v)} testid={`fattura-importo-${i}`} />
              <select value={x.pagamento} onChange={(e) => setFatt(i, "pagamento", e.target.value)} className="h-8 rounded border border-slate-200 px-1 text-sm" data-testid={`fattura-pag-${i}`}>
                <option value="pos">POS</option><option value="contanti">Contanti</option><option value="bonifico">Bonifico</option>
              </select>
              <button onClick={() => setF({ ...f, fatture_dettaglio: f.fatture_dettaglio.filter((_, j) => j !== i) })} className="text-slate-400 hover:text-rose-600" data-testid={`fattura-del-${i}`}><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
        <Input placeholder="Note" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="giorno-note" />
        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <span>Totale (contanti + POS + fatture) <b data-testid="giorno-totale">{eur(totale)}</b></span>
          <span className={incassato && Math.abs(incassato - scontrini) > 0.01 ? "text-amber-600" : "text-slate-500"} data-testid="giorno-quadratura">Scontrini {eur(scontrini)} / incassato {eur(incassato)}{incassato && Math.abs(incassato - scontrini) > 0.01 ? " ≠" : ""}</span>
        </div>
        <div className="flex justify-between">
          {!riga.vuoto ? <Button variant="ghost" className="text-rose-600" onClick={elimina} data-testid="giorno-elimina">Elimina</Button> : <span />}
          <div className="flex gap-2"><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={salva} disabled={saving} data-testid="giorno-salva">Salva</Button></div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
