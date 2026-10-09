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
  const [f, setF] = useState({ riparazioni: riga.riparazioni || "", merce: riga.merce || "", art74: riga.art74 || "", contanti: riga.contanti || "", pos: riga.pos || "", versati: riga.versati || "", non_riscosso: riga.non_riscosso || "", non_riscosso_note: riga.non_riscosso_note || "", note: riga.note || "", fatture_dettaglio: riga.fatture_dettaglio || [] });
  const [saving, setSaving] = useState(false);
  const n = (k) => parseFloat(f[k]) || 0;
  const fatture = f.fatture_dettaglio.reduce((a, x) => a + (parseFloat(x.importo) || 0), 0);
  const fattPos = f.fatture_dettaglio.filter((x) => x.pagamento === "pos").reduce((a, x) => a + (parseFloat(x.importo) || 0), 0);
  const fattCont = f.fatture_dettaglio.filter((x) => x.pagamento === "contanti").reduce((a, x) => a + (parseFloat(x.importo) || 0), 0);
  const scontrini = n("riparazioni") + n("merce") + n("art74");
  const incassato = n("contanti") + n("pos");
  const nonRiscosso = n("non_riscosso");
  const diff = scontrini - (n("contanti") - fattCont) - (n("pos") - fattPos) - nonRiscosso;
  const nonQuadra = incassato > 0 && Math.abs(diff) >= 1;
  const totale = scontrini + fatture;
  const setFatt = (i, k, v) => setF({ ...f, fatture_dettaglio: f.fatture_dettaglio.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  const salva = async () => {
    setSaving(true);
    try { await api.put(`/contabilita/corrispettivi/${storeId}/${riga.data}`, { ...f, riparazioni: n("riparazioni"), merce: n("merce"), art74: n("art74"), contanti: n("contanti"), pos: n("pos"), versati: n("versati"), non_riscosso: nonRiscosso, fatture }); toast.success(nonQuadra ? "Corrispettivo salvato · avviso quadratura inviato al negozio" : "Corrispettivo salvato"); onSaved(); }
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
          <p className="text-[11px] text-slate-500">Contanti e POS vanno inseriti con il totale del terminale/cassa (fatture comprese): le fatture pagate POS o contanti vengono scalate automaticamente nella quadratura.{fattPos || fattCont ? ` Scalate: POS ${eur(fattPos)} · contanti ${eur(fattCont)}.` : ""}</p>
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
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3" data-testid="giorno-non-riscosso-box">
          <p className="text-xs font-semibold uppercase text-amber-800">Non riscosso (es. saldo telefono con operatore, compensato da cessione credito)</p>
          <div className="mt-2 grid grid-cols-[1fr_2fr] gap-2">
            <Num value={f.non_riscosso} onChange={(v) => setF({ ...f, non_riscosso: v })} testid="giorno-non-riscosso" />
            <Input placeholder="Motivo (es. iPhone 15 WindTre, saldo da cessione credito)" value={f.non_riscosso_note} onChange={(e) => setF({ ...f, non_riscosso_note: e.target.value })} className="h-8" data-testid="giorno-non-riscosso-note" />
          </div>
        </div>
        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <span>Totale scontrinato (scontrini + fatture) <b data-testid="giorno-totale">{eur(totale)}</b></span>
          <span className={nonQuadra ? "font-medium text-amber-600" : "text-slate-500"} data-testid="giorno-quadratura">Scontrini {eur(scontrini)} / incassato {eur(incassato)}{fattPos || fattCont ? ` − fatture ${eur(fattPos + fattCont)}` : ""}{nonRiscosso ? ` + non riscosso ${eur(nonRiscosso)}` : ""}{nonQuadra ? ` ≠ (diff. ${eur(diff)})` : " ✓"}</span>
        </div>
        {nonQuadra && <p className="text-xs text-amber-700" data-testid="giorno-quadratura-avviso">Al salvataggio il negozio riceverà un WhatsApp di avviso sulla differenza.</p>}
        <div className="flex justify-between">
          {!riga.vuoto ? <Button variant="ghost" className="text-rose-600" onClick={elimina} data-testid="giorno-elimina">Elimina</Button> : <span />}
          <div className="flex gap-2"><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={salva} disabled={saving} data-testid="giorno-salva">Salva</Button></div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
