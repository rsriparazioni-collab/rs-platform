import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Repeat, Trash2, Pencil, Check, X, Plus } from "lucide-react";
import api, { apiError } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Num, eur } from "./shared";

const EMPTY = { motivo: "", importo: "", giorno: "1", riferimento: "" };

export const SpeseRicorrenti = ({ storeId, reload }) => {
  const [items, setItems] = useState([]);
  const [aperto, setAperto] = useState(false);
  const [f, setF] = useState(EMPTY);
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => api.get("/contabilita/spese-ricorrenti", { params: { store_id: storeId } }).then((r) => setItems(r.data)).catch(() => {}), [storeId]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (!f.motivo || !f.importo) return toast.error("Scrivi il motivo e l'importo");
    try { await api.post("/contabilita/spese-ricorrenti", { store_id: storeId, motivo: f.motivo, importo: parseFloat(f.importo), giorno: parseInt(f.giorno, 10) || 1, riferimento: f.riferimento }); toast.success("Spesa ricorrente salvata: verrà creata ogni mese da sola"); setF(EMPTY); load(); reload?.(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const salva = async () => {
    try { await api.put(`/contabilita/spese-ricorrenti/${edit.id}`, { store_id: storeId, motivo: edit.motivo, importo: parseFloat(edit.importo), giorno: parseInt(edit.giorno, 10) || 1, riferimento: edit.riferimento || "", attiva: edit.attiva !== false }); toast.success("Spesa ricorrente modificata"); setEdit(null); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const del = async (r) => {
    if (!window.confirm(`Non creare più "${r.motivo}" ogni mese? Le spese già create restano.`)) return;
    try { await api.delete(`/contabilita/spese-ricorrenti/${r.id}`); toast.success("Spesa ricorrente eliminata"); load(); } catch (e) { toast.error(apiError(e)); }
  };
  const toggle = async (r) => {
    try { await api.put(`/contabilita/spese-ricorrenti/${r.id}`, { ...r, attiva: !r.attiva }); load(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white" data-testid="spese-ricorrenti">
      <button type="button" onClick={() => setAperto((a) => !a)} className="flex w-full items-center justify-between px-5 py-3 text-left" data-testid="spese-ricorrenti-toggle">
        <h3 className="flex items-center gap-2 font-semibold text-slate-900"><Repeat className="h-4 w-4 text-sky-600" /> Spese fisse mensili <span className="text-xs font-normal text-slate-500">(affitto, pulizie…: create da sole ogni mese)</span></h3>
        <span className="text-xs text-slate-500">{items.length ? `${items.filter((i) => i.attiva).length} attive` : "nessuna"} {aperto ? "▲" : "▼"}</span>
      </button>
      {aperto && (
        <div className="border-t border-slate-100">
          <div className="grid gap-2 border-b border-slate-100 p-4 sm:grid-cols-[1fr_120px_90px_140px_auto]">
            <Input placeholder="Motivo (es. Affitto negozio)" value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} className="h-8" data-testid="ricorrente-motivo" />
            <Num value={f.importo} onChange={(v) => setF({ ...f, importo: v })} testid="ricorrente-importo" />
            <Input type="number" min="1" max="28" value={f.giorno} onChange={(e) => setF({ ...f, giorno: e.target.value })} className="h-8" title="Giorno del mese" data-testid="ricorrente-giorno" />
            <Input placeholder="Riferimento" value={f.riferimento} onChange={(e) => setF({ ...f, riferimento: e.target.value })} className="h-8" data-testid="ricorrente-riferimento" />
            <Button size="sm" onClick={add} data-testid="ricorrente-add"><Plus className="mr-1 h-3.5 w-3.5" /> Aggiungi</Button>
          </div>
          <table className="w-full text-sm"><tbody className="divide-y divide-slate-100">
            {items.map((r) => edit?.id === r.id ? (
              <tr key={r.id} className="bg-amber-50/60" data-testid={`ricorrente-edit-row-${r.id}`}>
                <td className="px-3 py-1.5"><Input value={edit.motivo} onChange={(e) => setEdit({ ...edit, motivo: e.target.value })} className="h-8" data-testid="ricorrente-edit-motivo" /></td>
                <td className="px-3 py-1.5"><Num value={edit.importo} onChange={(v) => setEdit({ ...edit, importo: v })} testid="ricorrente-edit-importo" /></td>
                <td className="px-3 py-1.5"><Input type="number" min="1" max="28" value={edit.giorno} onChange={(e) => setEdit({ ...edit, giorno: e.target.value })} className="h-8 w-20" data-testid="ricorrente-edit-giorno" /></td>
                <td className="px-3 py-1.5"><Input value={edit.riferimento || ""} onChange={(e) => setEdit({ ...edit, riferimento: e.target.value })} className="h-8" data-testid="ricorrente-edit-riferimento" /></td>
                <td className="whitespace-nowrap px-3 py-1.5 text-right">
                  <button onClick={salva} className="mr-2 text-emerald-600" data-testid="ricorrente-edit-save"><Check className="h-4 w-4" /></button>
                  <button onClick={() => setEdit(null)} className="text-slate-400" data-testid="ricorrente-edit-cancel"><X className="h-4 w-4" /></button>
                </td>
              </tr>
            ) : (
              <tr key={r.id} className={r.attiva ? "" : "opacity-50"} data-testid={`ricorrente-row-${r.id}`}>
                <td className="px-5 py-1.5">{r.motivo}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{eur(r.importo)}</td>
                <td className="px-3 py-1.5 text-slate-500">il {r.giorno} del mese</td>
                <td className="px-3 py-1.5 text-slate-500">{r.riferimento}</td>
                <td className="whitespace-nowrap px-3 py-1.5 text-right">
                  <button onClick={() => toggle(r)} className={`mr-3 rounded-full px-2 py-0.5 text-[11px] ${r.attiva ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`} data-testid={`ricorrente-toggle-${r.id}`}>{r.attiva ? "attiva" : "sospesa"}</button>
                  <button onClick={() => setEdit({ ...r, importo: String(r.importo), giorno: String(r.giorno) })} className="mr-2 text-slate-400 hover:text-sky-700" data-testid={`ricorrente-edit-${r.id}`}><Pencil className="h-4 w-4" /></button>
                  <button onClick={() => del(r)} className="text-slate-400 hover:text-rose-600" data-testid={`ricorrente-del-${r.id}`}><Trash2 className="h-4 w-4" /></button>
                </td>
              </tr>
            ))}
            {!items.length && <tr><td className="px-5 py-3 text-sm text-slate-400">Nessuna spesa fissa: aggiungi affitto, pulizie, canoni… e ogni mese compariranno da sole nelle spese di cassa.</td></tr>}
          </tbody></table>
        </div>
      )}
    </div>
  );
};
